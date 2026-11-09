"""Owned saved-risk boundary; never upgrades a compatibility pilot into history."""

from threading import Lock
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse

from app.auth.local_boundary import require_local_application
from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.domain.local_application import LocalStoreUnavailable
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore
from app.ports.local_risk_store import LocalRiskStore
from app.routers.local_application import local_bearer
from app.schemas.envelope import ErrorEnvelope, SuccessEnvelope
from app.schemas.local_risk import (
    UUID4_PATTERN,
    LocalRiskDraft,
    LocalRiskHistory,
    LocalRiskInput,
    LocalRiskQuestionnaire,
    LocalRiskScope,
    LocalRiskSubmitRequest,
    LocalSavedRiskAssessment,
)
from app.services.local_authorization import validate_token
from app.services.local_risk_service import LocalRiskService

ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorEnvelope} for code in (400, 401, 403, 404, 409, 422, 503)
}


def storage_unavailable() -> FinExException:
    return FinExException(
        message="Local storage is unavailable. Nothing was confirmed saved; please retry.",
        error_code="LOCAL_STORE_UNAVAILABLE",
        status_code=503,
    )


def get_local_risk_service(
    request: Request,
    token: str = Depends(local_bearer),
    _: None = Depends(require_local_application),
) -> LocalRiskService:
    # A malformed credential must not trigger lazy store construction or DI failures.
    validate_token(token)
    state = request.app.state
    lock: Lock = state.local_risk_service_lock
    with lock:
        if state.local_risk_service is None:
            settings: Settings = state.settings
            store: LocalRiskStore | None = state.local_risk_store
            if store is None:
                if (
                    state.local_application_store is not None
                    or state.local_portfolio_store is not None
                    or state.local_foundation_store is not None
                ):
                    # Do not guess injected S1 capabilities or use a different database.
                    raise storage_unavailable()
                store = SQLiteLocalRiskStore(settings.local_db_path)
            service = (
                LocalRiskService(store, state.local_clock)
                if state.local_clock is not None
                else LocalRiskService(store)
            )
            state.local_risk_service = service
        service = state.local_risk_service
    return service


def respond(
    request: Request, operation: Callable[[], LocalRiskScope], message: str
) -> JSONResponse:
    try:
        result = operation()
    except LocalStoreUnavailable:
        raise storage_unavailable() from None
    data_as_of = None
    if isinstance(result, LocalSavedRiskAssessment):
        data_as_of = result.created_at
    elif isinstance(result, LocalRiskDraft):
        data_as_of = result.updated_at
    return APIResponse.success(
        message=message,
        data=result.model_dump(mode="json"),
        correlation_id=request.state.correlation_id,
        data_status="CACHED",
        data_as_of=data_as_of,
    )


router = APIRouter(
    prefix="/api/v1/local-risk",
    tags=["Persistent local risk"],
    dependencies=[Depends(require_local_application)],
)


@router.get(
    "/questionnaire", response_model=SuccessEnvelope[LocalRiskQuestionnaire], responses=ERRORS
)
def questionnaire(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalRiskService = Depends(get_local_risk_service),
) -> JSONResponse:
    return respond(request, lambda: service.questionnaire(token), "Approved risk questionnaire")


@router.get("/draft", response_model=SuccessEnvelope[LocalRiskDraft], responses=ERRORS)
def draft(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalRiskService = Depends(get_local_risk_service),
) -> JSONResponse:
    return respond(request, lambda: service.draft(token), "Owned risk draft")


@router.put("/draft", response_model=SuccessEnvelope[LocalRiskDraft], responses=ERRORS)
def save_draft(
    request: Request,
    payload: LocalRiskInput,
    token: str = Depends(local_bearer),
    service: LocalRiskService = Depends(get_local_risk_service),
) -> JSONResponse:
    return respond(request, lambda: service.save_draft(token, payload), "Risk draft saved")


@router.post(
    "/assessments", response_model=SuccessEnvelope[LocalSavedRiskAssessment], responses=ERRORS
)
def submit(
    request: Request,
    payload: LocalRiskSubmitRequest,
    token: str = Depends(local_bearer),
    service: LocalRiskService = Depends(get_local_risk_service),
) -> JSONResponse:
    return respond(request, lambda: service.submit(token, payload), "Risk assessment saved")


@router.get("/assessments", response_model=SuccessEnvelope[LocalRiskHistory], responses=ERRORS)
def history(
    request: Request,
    limit: Annotated[
        str,
        Query(
            pattern=r"^(?:[1-9]|[1-4][0-9]|50)$",
            min_length=1,
            max_length=2,
            description="Canonical decimal page size, 1 through 50; defaults to 20.",
        ),
    ] = "20",
    before: Annotated[
        str | None,
        Query(
            pattern=r"^[1-9][0-9]*$",
            min_length=1,
            max_length=19,
            description="Exclusive insertion cursor, 1 through 9223372036854775807.",
        ),
    ] = None,
    token: str = Depends(local_bearer),
    service: LocalRiskService = Depends(get_local_risk_service),
) -> JSONResponse:
    cursor = int(before) if before is not None else None
    if cursor is not None and cursor > 9223372036854775807:
        raise FinExException(
            message="Request validation failed", error_code="VALIDATION_ERROR", status_code=422
        )
    return respond(
        request,
        lambda: service.history(token, before=cursor, limit=int(limit)),
        "Owned risk assessment history",
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=SuccessEnvelope[LocalSavedRiskAssessment],
    responses=ERRORS,
)
def assessment(
    request: Request,
    assessment_id: Annotated[str, Path(pattern=UUID4_PATTERN, min_length=36, max_length=36)],
    token: str = Depends(local_bearer),
    service: LocalRiskService = Depends(get_local_risk_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.assessment(token, assessment_id), "Owned saved risk assessment"
    )
