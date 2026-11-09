"""Loopback-only opt-in application API, isolated from compatibility pilots."""

from threading import Lock
from typing import Any, Callable

from fastapi import APIRouter, Body, Depends, Request, Security
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.auth.local_boundary import require_local_application
from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.domain.local_application import LocalStoreUnavailable
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.schemas.envelope import ErrorEnvelope, SuccessEnvelope
from app.schemas.local_application import (
    LocalCompletionRequest,
    LocalConsentRequest,
    LocalDraftRequest,
    LocalLoginRequest,
    LocalLoginResponse,
    LocalLogoutRequest,
    LocalLogoutResponse,
    LocalMeResponse,
    LocalOnboardingState,
)
from app.services.local_application_service import (
    LocalApplicationService,
    session_invalid,
    user_response,
)
from app.services.local_authorization import validate_token

ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorEnvelope} for code in (401, 403, 409, 422, 503)
}
local_http_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="LocalApplicationBearer",
    description=(
        "Opaque, memory-only session from opted-in loopback synthetic sign-in. "
        "Not a JWT, verified identity, remote authentication, or a cookie."
    ),
)


def get_local_service(
    request: Request, _: None = Depends(require_local_application)
) -> LocalApplicationService:
    state = request.app.state
    # One construction per application, without touching the DB until a guarded operation.
    lock: Lock = state.local_service_lock
    with lock:
        if state.local_application_service is None:
            settings: Settings = state.settings
            store = state.local_application_store
            if store is None:
                if (
                    state.local_risk_store is not None
                    or state.local_portfolio_store is not None
                    or state.local_foundation_store is not None
                ):
                    # Do not create S1 identities in a different fallback database.
                    raise FinExException(
                        message="Local storage is unavailable. Nothing was confirmed saved; "
                        "please retry.",
                        error_code="LOCAL_STORE_UNAVAILABLE",
                        status_code=503,
                    )
                store = SQLiteLocalApplicationStore(settings.local_db_path)
            if state.local_clock is not None:
                service = LocalApplicationService(
                    store, state.local_clock, settings.local_session_ttl_minutes
                )
            else:
                service = LocalApplicationService(
                    store, session_ttl_minutes=settings.local_session_ttl_minutes
                )
            state.local_application_service = service
        service = state.local_application_service
    return service


def local_bearer(
    request: Request,
    _: None = Depends(require_local_application),
    _documented_bearer: HTTPAuthorizationCredentials | None = Security(local_http_bearer),
) -> str:
    # Security documents the six protected operations. Keep the accepted strict
    # parser and SESSION_INVALID 401 rather than HTTPBearer's default 403.
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise session_invalid()
    validate_token(parts[1])
    return parts[1]


def respond(request: Request, operation: Callable[[], BaseModel], message: str) -> JSONResponse:
    try:
        result = operation()
    except LocalStoreUnavailable:
        raise FinExException(
            message="Local storage is unavailable. Nothing was confirmed saved; please retry.",
            error_code="LOCAL_STORE_UNAVAILABLE",
            status_code=503,
        ) from None
    return APIResponse.success(
        message=message,
        data=result.model_dump(mode="json"),
        correlation_id=request.state.correlation_id,
        data_status="CACHED",
    )


router = APIRouter(
    tags=["Persistent local application"], dependencies=[Depends(require_local_application)]
)


@router.post(
    "/api/v1/local-auth/mock-login",
    response_model=SuccessEnvelope[LocalLoginResponse],
    responses=ERRORS,
)
def login(
    request: Request,
    payload: LocalLoginRequest,
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    return respond(request, lambda: service.login(payload.alias), "Synthetic local sign-in")


@router.get(
    "/api/v1/local-auth/me", response_model=SuccessEnvelope[LocalMeResponse], responses=ERRORS
)
def me(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: LocalMeResponse(user=user_response(service.me(token))),
        "Local session validated",
    )


@router.post(
    "/api/v1/local-auth/logout",
    response_model=SuccessEnvelope[LocalLogoutResponse],
    responses=ERRORS,
)
def logout(
    request: Request,
    payload: LocalLogoutRequest | None = Body(default=None),
    token: str = Depends(local_bearer),
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    def operation() -> LocalLogoutResponse:
        service.logout(token)
        return LocalLogoutResponse()

    return respond(request, operation, "Local session revoked")


@router.get(
    "/api/v1/local-onboarding/state",
    response_model=SuccessEnvelope[LocalOnboardingState],
    responses=ERRORS,
)
def state(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    return respond(request, lambda: service.state(token), "Owned onboarding state")


@router.put(
    "/api/v1/local-onboarding/draft",
    response_model=SuccessEnvelope[LocalOnboardingState],
    responses=ERRORS,
)
def draft(
    request: Request,
    payload: LocalDraftRequest,
    token: str = Depends(local_bearer),
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    return respond(request, lambda: service.draft(token, payload), "Profile draft saved")


@router.post(
    "/api/v1/local-onboarding/consent",
    response_model=SuccessEnvelope[LocalOnboardingState],
    responses=ERRORS,
)
def consent(
    request: Request,
    payload: LocalConsentRequest,
    token: str = Depends(local_bearer),
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    return respond(request, lambda: service.consent(token, payload), "Consent decision recorded")


@router.post(
    "/api/v1/local-onboarding/complete",
    response_model=SuccessEnvelope[LocalOnboardingState],
    responses=ERRORS,
)
def complete(
    request: Request,
    payload: LocalCompletionRequest,
    token: str = Depends(local_bearer),
    service: LocalApplicationService = Depends(get_local_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.complete(token, payload.consent_version, payload.profile_schema_version),
        "Owned onboarding completed",
    )
