"""In-memory implementation of the versioned Sprint 1 onboarding contract.

This is a deliberately bounded local adapter.  The API only depends on this
service boundary, so a future persistent implementation can replace it without
changing React or Flutter clients.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import BadRequestException
from app.fixtures.s1_dat_01 import FixtureValidationError, resolve_fixture_provider
from app.schemas.consent_profile import (
    SUPPORTED_CONSENT_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSION,
    ConsentResponse,
    ConsentStatus,
    ExperienceLevel,
    OnboardingCompleteResponse,
    ProfileResponse,
    ProfileState,
)

_consent_store: dict[str, dict[str, Any]] = {}
_profile_store: dict[str, dict[str, Any]] = {}
_onboarding_store: dict[str, dict[str, Any]] = {}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _reset_stores() -> None:
    """Clear ephemeral state.  Exposed only for deterministic tests."""
    _consent_store.clear()
    _profile_store.clear()
    _onboarding_store.clear()


def _validate_fixture_mode(fixture_mode: str) -> None:
    """Reject an unsupported fixture selection rather than silently ignoring it."""
    try:
        resolve_fixture_provider(fixture_mode)
    except ValueError as error:
        raise BadRequestException(
            message=str(error),
            error_code="FIXTURE_MODE_UNSUPPORTED",
        ) from error


def capture_consent(
    *,
    user_id: str,
    consent_version: str,
    consent_given: bool,
    fixture_mode: str = "disabled",
) -> ConsentResponse:
    """Record accepted educational consent for one transient pilot user."""
    _validate_fixture_mode(fixture_mode)
    if consent_version != SUPPORTED_CONSENT_VERSION:
        raise BadRequestException(
            message=(
                f"Unsupported consent version '{consent_version}'. Supported version is "
                f"'{SUPPORTED_CONSENT_VERSION}'."
            ),
            error_code="UNSUPPORTED_CONSENT_VERSION",
        )
    if not consent_given:
        raise BadRequestException(
            message="Consent must be accepted to proceed with onboarding.",
            error_code="CONSENT_NOT_GIVEN",
        )

    recorded_at = _utc_now_iso()
    _consent_store[user_id] = {
        "user_id": user_id,
        "consent_version": consent_version,
        "consent_status": ConsentStatus.ACCEPTED.value,
        "recorded_at": recorded_at,
    }
    return ConsentResponse(
        consent_version=consent_version,
        consent_status=ConsentStatus.ACCEPTED,
        recorded_at=recorded_at,
    )


def submit_profile(
    *,
    user_id: str,
    profile_schema_version: str,
    display_name: str,
    experience_level: ExperienceLevel,
    fixture_mode: str = "disabled",
) -> ProfileResponse:
    """Record a profile only after valid consent has been captured."""
    _validate_fixture_mode(fixture_mode)
    if profile_schema_version != SUPPORTED_PROFILE_SCHEMA_VERSION:
        raise BadRequestException(
            message=(
                f"Unsupported profile schema version '{profile_schema_version}'. Supported "
                f"version is '{SUPPORTED_PROFILE_SCHEMA_VERSION}'."
            ),
            error_code="UNSUPPORTED_PROFILE_VERSION",
        )
    consent_record = _consent_store.get(user_id)
    if not consent_record or consent_record.get("consent_status") != ConsentStatus.ACCEPTED.value:
        raise BadRequestException(
            message="User must capture consent before submitting a profile.",
            error_code="CONSENT_MISSING",
        )

    recorded_at = _utc_now_iso()
    _profile_store[user_id] = {
        "user_id": user_id,
        "profile_schema_version": profile_schema_version,
        "profile_state": ProfileState.COMPLETED.value,
        "display_name": display_name,
        "experience_level": experience_level.value,
        "recorded_at": recorded_at,
    }
    return ProfileResponse(
        profile_schema_version=profile_schema_version,
        profile_state=ProfileState.COMPLETED,
        display_name=display_name,
        experience_level=experience_level,
        recorded_at=recorded_at,
    )


def complete_onboarding(
    *,
    user_id: str,
    consent_version: str,
    profile_schema_version: str,
    fixture_mode: str = "disabled",
) -> OnboardingCompleteResponse:
    """Mark a local onboarding journey complete after consent and profile exist."""
    _validate_fixture_mode(fixture_mode)
    if consent_version != SUPPORTED_CONSENT_VERSION:
        raise BadRequestException(
            message=(
                f"Unsupported consent version '{consent_version}'. Supported version is "
                f"'{SUPPORTED_CONSENT_VERSION}'."
            ),
            error_code="UNSUPPORTED_CONSENT_VERSION",
        )
    if profile_schema_version != SUPPORTED_PROFILE_SCHEMA_VERSION:
        raise BadRequestException(
            message=(
                f"Unsupported profile schema version '{profile_schema_version}'. Supported "
                f"version is '{SUPPORTED_PROFILE_SCHEMA_VERSION}'."
            ),
            error_code="UNSUPPORTED_PROFILE_VERSION",
        )
    consent_record = _consent_store.get(user_id)
    if not consent_record or consent_record.get("consent_status") != ConsentStatus.ACCEPTED.value:
        raise BadRequestException(
            message="Consent must be captured before completing onboarding.",
            error_code="CONSENT_MISSING",
        )
    if user_id not in _profile_store:
        raise BadRequestException(
            message="Profile must be submitted before completing onboarding.",
            error_code="PROFILE_MISSING",
        )

    recorded_at = _utc_now_iso()
    _onboarding_store[user_id] = {
        "user_id": user_id,
        "onboarding_completed": True,
        "consent_version": consent_version,
        "profile_schema_version": profile_schema_version,
        "recorded_at": recorded_at,
    }
    return OnboardingCompleteResponse(
        onboarding_completed=True,
        consent_version=consent_version,
        profile_schema_version=profile_schema_version,
        fixture_mode=fixture_mode if fixture_mode != "disabled" else None,
        recorded_at=recorded_at,
    )


def seed_fixtures(fixture_mode: str) -> dict[str, int | str]:
    """Load the validated, synthetic S1-DAT-01 fixture records for local tests."""
    try:
        provider = resolve_fixture_provider(fixture_mode)
    except ValueError as error:
        raise BadRequestException(
            message=str(error),
            error_code="FIXTURE_MODE_UNSUPPORTED",
        ) from error
    if provider is None:
        raise BadRequestException(
            message="Fixture mode is disabled.",
            error_code="FIXTURE_MODE_DISABLED",
        )
    try:
        records_document = provider.reset_and_seed()
    except FixtureValidationError as error:
        raise BadRequestException(
            message=f"Local fixture contract is invalid: {error}",
            error_code="FIXTURE_CONTRACT_INVALID",
        ) from error

    scenarios = records_document.get("records", {}).get("scenarios", [])
    if not isinstance(scenarios, list):
        raise BadRequestException(
            message="Local fixture contract contains invalid scenarios.",
            error_code="FIXTURE_CONTRACT_INVALID",
        )

    _reset_stores()
    for scenario in scenarios:
        user_id = scenario["user_id"]
        _consent_store[user_id] = scenario["consent"]
        _profile_store[user_id] = scenario["profile"]
        if scenario["onboarding"].get("completed"):
            _onboarding_store[user_id] = {
                "user_id": user_id,
                "onboarding_completed": True,
                "consent_version": scenario["consent"]["consent_version"],
                "profile_schema_version": scenario["profile"]["profile_schema_version"],
                "recorded_at": scenario["onboarding"]["recorded_at"],
            }

    return {
        "fixture_mode": fixture_mode,
        "scenarios_loaded": len(scenarios),
        "consent_records": len(_consent_store),
        "profile_records": len(_profile_store),
        "onboarding_records": len(_onboarding_store),
    }
