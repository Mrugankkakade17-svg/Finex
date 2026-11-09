from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.core.responses import APIResponse
from app.schemas.onboarding import (
    OnboardingCompleteRequest,
    OnboardingCompleteResponse,
)
from app.services import onboarding_service

router = APIRouter(
    prefix="/api/v1/onboarding",
    tags=["Onboarding"],
)


@router.post("/complete")
def complete_onboarding(
    request: Request,
    payload: OnboardingCompleteRequest,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]

    result = onboarding_service.complete_onboarding(
        user_id=user_id,
        consent_given=payload.consent_given,
    )

    response = OnboardingCompleteResponse(**result)

    return APIResponse.success(
        message="Onboarding completed successfully",
        data=response.model_dump(),
        correlation_id=request.state.correlation_id,
    )
