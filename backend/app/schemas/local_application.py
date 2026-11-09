"""Strict local.v1 DTOs: synthetic user identity, minimal profile and consent."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.schemas.consent_profile import ExperienceLevel


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class LocalLoginRequest(StrictRequest):
    alias: str = Field(min_length=1, max_length=32)


class LocalLogoutRequest(StrictRequest):
    pass


class LocalDraftRequest(StrictRequest):
    profile_schema_version: str
    display_name: str | None
    experience_level: Literal["beginner", "intermediate", "advanced"] | None

    @field_validator("display_name")
    @classmethod
    def normalized_label(cls, value: str | None) -> str | None:
        normalized = value.strip() if value is not None else None
        if normalized is not None and len(normalized) > 80:
            raise ValueError("Display label exceeds the allowed length.")
        return normalized


class LocalConsentRequest(StrictRequest):
    consent_version: str
    consent_given: StrictBool


class LocalCompletionRequest(StrictRequest):
    consent_version: str
    profile_schema_version: str


class LocalScope(BaseModel):
    scope: Literal["local_educational_application"] = "local_educational_application"
    contract_version: Literal["local.v1"] = "local.v1"


class LocalUserResponse(BaseModel):
    id: str
    alias: Literal["learner-a", "learner-b"]


class LocalLoginResponse(LocalScope):
    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_at: str
    user: LocalUserResponse


class LocalMeResponse(LocalScope):
    user: LocalUserResponse


class LocalLogoutResponse(LocalScope):
    signed_out: Literal[True] = True


class LocalConsentState(BaseModel):
    accepted: bool
    version: str
    recorded_at: str


class LocalDraftState(BaseModel):
    display_name: str | None
    experience_level: ExperienceLevel | None
    updated_at: str | None


class LocalOnboardingState(LocalScope):
    profile_schema_version: str
    consent_version: str
    consent: LocalConsentState | None
    draft: LocalDraftState
    onboarding_completed: bool
    completed_at: str | None
