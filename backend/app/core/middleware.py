"""
Correlation ID middleware for Finex.

Every request gets a unique ID stamped on it. This lets us trace a single
request through logs, across services, and back to the user who reported
a bug — without this, "it broke somewhere" is impossible to debug at scale.
"""

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.local_boundary import require_local_application, require_local_legacy_auth
from app.core.exceptions import FinExException
from app.core.responses import APIResponse

CORRELATION_ID_HEADER = "X-Correlation-ID"
SAFE_CORRELATION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z", flags=re.ASCII)
LOCAL_CREDENTIAL_WINDOW = re.compile(r"(?=([A-Za-z0-9_-]{43}))", flags=re.ASCII)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Attaches a correlation ID to every request.

    - If the caller (frontend, another service) already sent an
      X-Correlation-ID header, we reuse it — this lets a request be traced
      across multiple services with the same ID.
    - Otherwise, we generate a fresh UUID.
    - We store it on `request.state.correlation_id` so route handlers and
      exception handlers can read it.
    - We also echo it back in the response header, so the frontend can log
      it and reference it if they report a bug.
    """

    async def dispatch(self, request: Request, call_next):
        incoming_id = request.headers.get(CORRELATION_ID_HEADER)
        correlation_id = str(uuid.uuid4())
        if incoming_id and SAFE_CORRELATION.fullmatch(incoming_id):
            authorization = request.headers.get("Authorization", "")
            credential = authorization.split(maxsplit=2)
            # Preserve generic/legacy credential redaction even for malformed headers.
            candidate = (
                credential[1] if len(credential) >= 2 else (credential[0] if credential else "")
            )
            if len(credential) == 1 and candidate.lower().startswith("bearer"):
                candidate = candidate[6:]
            # Scan at most 86 overlapping windows of a <=128-character safe ID,
            # not an unbounded header. Local bearer tokens have 43 URL-safe characters;
            # checking raw Authorization catches joined schemes and arbitrary separators.
            is_credential = bool(
                (candidate and candidate in incoming_id)
                or any(
                    match.group(1) in authorization
                    for match in LOCAL_CREDENTIAL_WINDOW.finditer(incoming_id)
                )
            )
            if not is_credential:
                correlation_id = incoming_id

        # Make it available to everything downstream (routers, services,
        # exception handlers) via request.state
        request.state.correlation_id = correlation_id

        response = await call_next(request)

        # Echo it back so the caller can see/log the ID that was used
        response.headers[CORRELATION_ID_HEADER] = correlation_id

        return response


class LocalApplicationBoundaryMiddleware(BaseHTTPMiddleware):
    """Check exposure before FastAPI reads/parses a body or resolves storage."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        legacy_prefixes = (
            "/api/v1/auth",
            "/api/v1/users",
            "/api/v1/onboarding",
            "/api/v1/risk",
            "/api/v1/onboarding-contract",
            "/api/v1/risk-contract",
        )
        try:
            if path.startswith("/api/v1/local-"):
                require_local_application(request)
            elif any(path == prefix or path.startswith(prefix + "/") for prefix in legacy_prefixes):
                require_local_legacy_auth(request)
        except FinExException as exc:
            return APIResponse.error(
                message=exc.message,
                error_code=exc.error_code,
                status_code=exc.status_code,
                correlation_id=request.state.correlation_id,
            )
        return await call_next(request)
