"""Versioned Sprint 1 consent, profile, and onboarding contract.

The contract deliberately captures only educational consent and a minimal,
non-sensitive onboarding profile.  It does not accept credentials, financial
account data, or risk-assessment answers.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator

SUPPORTED_CONSENT_VERSION = "consent.v1"
SUPPORTED_PROFILE_SCHEMA_VERSION = "profile.v1"


class ConsentStatus(str, Enum):
    """Consent lifecycle values exposed to API clients."""

    ACCEPTED = "accepted"
    REVOKED = "revoked"
    CHANGED = "changed"


class ProfileState(str, Enum):
    """Profile progress values shared with the local fixture contract."""

    NEW = "new"
    PARTIAL_DRAFT = "partial-draft"
    COMPLETED = "completed"
    VALIDATION_FAILURE = "validation-failure"


class ExperienceLevel(str, Enum):
    """Small, stable enumeration for the Sprint 1 pilot."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ConsentRequest(BaseModel):
    """Capture a user's agreement to the current educational consent text."""

    consent_version: str = Field(
        description="Consent contract version the client is agreeing to.",
        examples=[SUPPORTED_CONSENT_VERSION],
    )
    consent_given: bool = Field(
        description="Whether the user accepted the educational consent. Must be true."
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"consent_version": SUPPORTED_CONSENT_VERSION, "consent_given": True}]
        }
    }


class ProfileRequest(BaseModel):
    """Minimal, non-sensitive profile collected after consent."""

    profile_schema_version: str = Field(
        description="Profile schema version the client payload conforms to.",
        examples=[SUPPORTED_PROFILE_SCHEMA_VERSION],
    )
    display_name: str = Field(
        min_length=1,
        max_length=80,
        description="Non-sensitive display label; not a legal name or identifier.",
    )
    experience_level: ExperienceLevel = Field(
        description="Self-declared investing experience for educational tailoring."
    )

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        """Reject whitespace-only values and avoid persisting accidental padding."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("display_name must not be blank")
        return normalized

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "profile_schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
                    "display_name": "Test Investor",
                    "experience_level": "beginner",
                }
            ]
        }
    }


class OnboardingCompleteRequest(BaseModel):
    """Confirm the versions accepted before marking onboarding complete."""

    consent_version: str = Field(examples=[SUPPORTED_CONSENT_VERSION])
    profile_schema_version: str = Field(examples=[SUPPORTED_PROFILE_SCHEMA_VERSION])


class ConsentResponse(BaseModel):
    """Safe result of a consent capture."""

    consent_version: str
    consent_status: ConsentStatus
    recorded_at: str = Field(description="ISO-8601 UTC timestamp.")


class ProfileResponse(BaseModel):
    """Safe result of a profile submission."""

    profile_schema_version: str
    profile_state: ProfileState
    display_name: str
    experience_level: ExperienceLevel
    recorded_at: str = Field(description="ISO-8601 UTC timestamp.")


class OnboardingCompleteResponse(BaseModel):
    """Safe completion signal; it deliberately omits the internal user id."""

    onboarding_completed: bool
    consent_version: str
    profile_schema_version: str
    fixture_mode: str | None = Field(
        default=None,
        description="Active local fixture mode, otherwise null.",
    )
    recorded_at: str = Field(description="ISO-8601 UTC timestamp.")
