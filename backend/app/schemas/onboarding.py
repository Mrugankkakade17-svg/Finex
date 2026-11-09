from pydantic import BaseModel, Field


class OnboardingCompleteRequest(BaseModel):
    consent_given: bool = Field(
        ...,
        description="Whether the user has accepted the required onboarding consent.",
    )


class OnboardingCompleteResponse(BaseModel):
    user_id: int
    onboarding_completed: bool
    consent_given: bool
