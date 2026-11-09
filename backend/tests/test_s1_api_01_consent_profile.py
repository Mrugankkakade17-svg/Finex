"""Contract and behavior tests for the Sprint 1 consent/profile API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import BadRequestException
from app.main import app
from app.schemas.consent_profile import (
    SUPPORTED_CONSENT_VERSION,
    SUPPORTED_PROFILE_SCHEMA_VERSION,
)
from app.services import consent_profile_service

client = TestClient(app)
CONSENT_URL = "/api/v1/onboarding-contract/consent"
PROFILE_URL = "/api/v1/onboarding-contract/profile"
COMPLETE_URL = "/api/v1/onboarding-contract/complete"
HEADERS = {"X-Correlation-ID": "s1-contract-test-0001"}


@pytest.fixture(autouse=True)
def reset_service_stores() -> None:
    """Keep every contract scenario independent and repeatable."""
    consent_profile_service._reset_stores()
    yield
    consent_profile_service._reset_stores()


def consent_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "consent_version": SUPPORTED_CONSENT_VERSION,
        "consent_given": True,
    }
    payload.update(overrides)
    return payload


def profile_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "profile_schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
        "display_name": "Test Investor",
        "experience_level": "beginner",
    }
    payload.update(overrides)
    return payload


def complete_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "consent_version": SUPPORTED_CONSENT_VERSION,
        "profile_schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
    }
    payload.update(overrides)
    return payload


def assert_error(response, status_code: int, error_code: str) -> None:
    assert response.status_code == status_code
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == error_code
    assert body["error"]["correlationId"] == HEADERS["X-Correlation-ID"]


def test_full_onboarding_happy_path_and_normalizes_display_name() -> None:
    consent = client.post(CONSENT_URL, headers=HEADERS, json=consent_payload())
    assert consent.status_code == 201
    assert consent.json()["data"]["consent_status"] == "accepted"
    assert consent.json()["meta"]["correlationId"] == HEADERS["X-Correlation-ID"]

    profile = client.post(
        PROFILE_URL,
        headers=HEADERS,
        json=profile_payload(display_name="  Test Investor  "),
    )
    assert profile.status_code == 201
    assert profile.json()["data"] == {
        "profile_schema_version": SUPPORTED_PROFILE_SCHEMA_VERSION,
        "profile_state": "completed",
        "display_name": "Test Investor",
        "experience_level": "beginner",
        "recorded_at": profile.json()["data"]["recorded_at"],
    }

    completed = client.post(COMPLETE_URL, headers=HEADERS, json=complete_payload())
    assert completed.status_code == 200
    assert completed.json()["data"]["onboarding_completed"] is True
    assert completed.json()["data"]["fixture_mode"] is None


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (consent_payload(consent_version="consent.v999"), "UNSUPPORTED_CONSENT_VERSION"),
        (consent_payload(consent_given=False), "CONSENT_NOT_GIVEN"),
    ],
)
def test_invalid_consent_is_rejected(payload: dict[str, object], expected_code: str) -> None:
    assert_error(client.post(CONSENT_URL, headers=HEADERS, json=payload), 400, expected_code)


def test_missing_consent_field_uses_standard_validation_envelope() -> None:
    response = client.post(
        CONSENT_URL,
        headers=HEADERS,
        json={"consent_version": SUPPORTED_CONSENT_VERSION},
    )
    assert_error(response, 422, "VALIDATION_ERROR")


def test_profile_requires_consent_first() -> None:
    assert_error(
        client.post(PROFILE_URL, headers=HEADERS, json=profile_payload()),
        400,
        "CONSENT_MISSING",
    )


def test_unsupported_profile_version_is_rejected() -> None:
    client.post(CONSENT_URL, headers=HEADERS, json=consent_payload())
    assert_error(
        client.post(
            PROFILE_URL,
            headers=HEADERS,
            json=profile_payload(profile_schema_version="profile.v999"),
        ),
        400,
        "UNSUPPORTED_PROFILE_VERSION",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"display_name": ""},
        {"display_name": "   "},
        {"experience_level": "novice"},
    ],
)
def test_invalid_profile_fields_use_standard_validation_envelope(
    overrides: dict[str, object],
) -> None:
    client.post(CONSENT_URL, headers=HEADERS, json=consent_payload())
    response = client.post(PROFILE_URL, headers=HEADERS, json=profile_payload(**overrides))
    assert_error(response, 422, "VALIDATION_ERROR")


def test_complete_requires_profile() -> None:
    client.post(CONSENT_URL, headers=HEADERS, json=consent_payload())
    assert_error(
        client.post(COMPLETE_URL, headers=HEADERS, json=complete_payload()),
        400,
        "PROFILE_MISSING",
    )


def test_complete_rejects_version_drift() -> None:
    client.post(CONSENT_URL, headers=HEADERS, json=consent_payload())
    client.post(PROFILE_URL, headers=HEADERS, json=profile_payload())
    assert_error(
        client.post(
            COMPLETE_URL,
            headers=HEADERS,
            json=complete_payload(profile_schema_version="profile.v999"),
        ),
        400,
        "UNSUPPORTED_PROFILE_VERSION",
    )


def test_contract_versions_match_the_validated_local_fixture() -> None:
    fixture_contract = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "fixtures"
        / "s1_dat_01"
        / "fixture_contract_v1.json"
    )
    contract = json.loads(fixture_contract.read_text(encoding="utf-8"))
    assert SUPPORTED_CONSENT_VERSION == contract["supported_consent_version"]
    assert SUPPORTED_PROFILE_SCHEMA_VERSION == contract["supported_profile_schema_version"]


def test_seeded_fixture_data_is_local_and_complete() -> None:
    summary = consent_profile_service.seed_fixtures("s1_dat_01")
    assert summary == {
        "fixture_mode": "s1_dat_01",
        "scenarios_loaded": 5,
        "consent_records": 5,
        "profile_records": 5,
        "onboarding_records": 2,
    }


@pytest.mark.parametrize(
    ("fixture_mode", "expected_code"),
    [("disabled", "FIXTURE_MODE_DISABLED"), ("unknown", "FIXTURE_MODE_UNSUPPORTED")],
)
def test_fixture_seed_rejects_disabled_or_unknown_mode(
    fixture_mode: str, expected_code: str
) -> None:
    with pytest.raises(BadRequestException) as error:
        consent_profile_service.seed_fixtures(fixture_mode)
    assert error.value.error_code == expected_code


def test_openapi_is_the_canonical_live_contract_with_actual_status_codes() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert paths[CONSENT_URL]["post"]["responses"]["201"]
    assert paths[PROFILE_URL]["post"]["responses"]["201"]
    assert paths[COMPLETE_URL]["post"]["responses"]["200"]
    experience_schema = schema["components"]["schemas"]["ExperienceLevel"]
    assert experience_schema["enum"] == ["beginner", "intermediate", "advanced"]
