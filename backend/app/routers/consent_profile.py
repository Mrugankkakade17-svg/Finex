"""HTTP boundary for the versioned Sprint 1 onboarding contract."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from app.config.settings import AppEnv
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.schemas.consent_profile import (
    ConsentRequest,
    ConsentResponse,
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
    ProfileRequest,
    ProfileResponse,
)
from app.schemas.envelope import ErrorEnvelope, SuccessEnvelope
from app.services import consent_profile_service


def require_local_onboarding_pilot(request: Request) -> None:
    """A transient trace ID is not deployed user authentication or consent."""
    if request.app.state.settings.app_env != AppEnv.LOCAL:
        raise FinExException(
            message="This onboarding pilot is available only in local development.",
            error_code="LOCAL_PILOT_ONLY",
            status_code=403,
        )


router = APIRouter(
    prefix="/api/v1/onboarding-contract",
    tags=["Onboarding contract"],
    dependencies=[Depends(require_local_onboarding_pilot)],
)


def _pilot_user_id(request: Request) -> str:
    """Derive a transient, non-sensitive pilot identity from the trace id.

    Sprint 1 deliberately has no identity-provider integration.  Binding to a
    real authenticated user belongs to a later, separately reviewed story.
    """
    return f"pilot_{request.state.correlation_id}"


@router.post(
    "/consent",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessEnvelope[ConsentResponse],
    summary="Capture educational consent",
    response_description="Consent recorded in the FinEx v1 response envelope.",
    responses={
        400: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
    },
)
def capture_consent(request: Request, payload: ConsentRequest) -> JSONResponse:
    """Validate and record a consent decision."""
    result = consent_profile_service.capture_consent(
        user_id=_pilot_user_id(request),
        consent_version=payload.consent_version,
        consent_given=payload.consent_given,
        fixture_mode=request.app.state.settings.fixture_mode,
    )
    return APIResponse.success(
        message="Consent recorded",
        data=result.model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/profile",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessEnvelope[ProfileResponse],
    summary="Submit a minimal onboarding profile",
    response_description="Profile recorded in the FinEx v1 response envelope.",
    responses={
        400: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
    },
)
def submit_profile(request: Request, payload: ProfileRequest) -> JSONResponse:
    """Record an allowed profile only after consent is present."""
    result = consent_profile_service.submit_profile(
        user_id=_pilot_user_id(request),
        profile_schema_version=payload.profile_schema_version,
        display_name=payload.display_name,
        experience_level=payload.experience_level,
        fixture_mode=request.app.state.settings.fixture_mode,
    )
    return APIResponse.success(
        message="Profile recorded",
        data=result.model_dump(mode="json"),
        status_code=status.HTTP_201_CREATED,
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/complete",
    response_model=SuccessEnvelope[OnboardingCompleteResponse],
    summary="Complete onboarding",
    response_description="Onboarding completion signal in the FinEx v1 response envelope.",
    responses={
        400: {"model": ErrorEnvelope},
        403: {"model": ErrorEnvelope},
        422: {"model": ErrorEnvelope},
    },
)
def complete_onboarding(request: Request, payload: OnboardingCompleteRequest) -> JSONResponse:
    """Complete onboarding after both prerequisite records are present."""
    result = consent_profile_service.complete_onboarding(
        user_id=_pilot_user_id(request),
        consent_version=payload.consent_version,
        profile_schema_version=payload.profile_schema_version,
        fixture_mode=request.app.state.settings.fixture_mode,
    )
    return APIResponse.success(
        message="Onboarding completed",
        data=result.model_dump(mode="json"),
        correlation_id=request.state.correlation_id,
    )
