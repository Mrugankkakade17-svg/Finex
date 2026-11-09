"""
Correlation ID middleware for Finex.

Every request gets a unique ID stamped on it. This lets us trace a single
request through logs, across services, and back to the user who reported
a bug — without this, "it broke somewhere" is impossible to debug at scale.
"""

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

CORRELATION_ID_HEADER = "X-Correlation-ID"


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
        correlation_id = incoming_id if incoming_id else str(uuid.uuid4())

        # Make it available to everything downstream (routers, services,
        # exception handlers) via request.state
        request.state.correlation_id = correlation_id

        response = await call_next(request)

        # Echo it back so the caller can see/log the ID that was used
        response.headers[CORRELATION_ID_HEADER] = correlation_id

        return response
