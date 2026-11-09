"""Final acceptance: local consent/profile to educational risk; no deployed bypass."""

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.fixtures.s2_dat_01 import S2Dat01FixtureProvider
from app.main import create_app
from app.services import consent_profile_service

VALID = [row for row in S2Dat01FixtureProvider().list_fixtures() if row["kind"] == "valid"]
S1 = "/api/v1/onboarding-contract"
CONSENT = {"consent_version": "consent.v1", "consent_given": True}
PROFILE = {
    "profile_schema_version": "profile.v1",
    "display_name": "Local Tester",
    "experience_level": "beginner",
}
COMPLETE = {"consent_version": "consent.v1", "profile_schema_version": "profile.v1"}


@pytest.mark.parametrize("fixture", VALID, ids=[row["case_id"] for row in VALID])
def test_synthetic_onboarding_to_every_valid_risk_vector(fixture):
    client = TestClient(create_app(Settings(app_env="local", _env_file=None)))
    headers = {"X-Correlation-ID": "journey-" + fixture["case_id"]}
    assert client.post(S1 + "/consent", json=CONSENT, headers=headers).status_code == 201
    assert client.post(S1 + "/profile", json=PROFILE, headers=headers).status_code == 201
    assert client.post(S1 + "/complete", json=COMPLETE, headers=headers).status_code == 200
    response = client.post(
        "/api/v1/risk-contract/assessments", json=fixture["request"], headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["correlationId"] == headers["X-Correlation-ID"]
    assert body["data"]["assessment"]["composite_score"] == fixture["expected"]["composite_score"]
    assert body["data"]["persisted"] is False
    assert "Local Tester" not in response.text
    assert "not individualized" in body["data"]["explanation"]["limitation"]


@pytest.mark.parametrize("environment", ["dev", "uat", "prod"])
@pytest.mark.parametrize(
    "path,payload", [("consent", CONSENT), ("profile", PROFILE), ("complete", COMPLETE)]
)
def test_unauthenticated_onboarding_pilot_is_not_deployable(environment, path, payload):
    settings = Settings(
        app_env=environment,
        debug=False,
        fixture_mode="disabled",
        llm_provider="none",
        api_base_url="https://api.example.invalid",
        secret_key="s" * 32,
        allowed_origins=["https://app.example.invalid"],
        _env_file=None,
    )
    client = TestClient(create_app(settings))
    response = client.post(S1 + "/" + path, json=payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "LOCAL_PILOT_ONLY"
    assert "Local Tester" not in response.text


def test_onboarding_uses_its_application_settings_not_global_cache(monkeypatch):
    seen = []
    original = consent_profile_service.capture_consent

    def capture(**values):
        seen.append(values["fixture_mode"])
        return original(**values)

    monkeypatch.setattr(consent_profile_service, "capture_consent", capture)
    settings = Settings(app_env="local", fixture_mode="s1_dat_01", _env_file=None)
    client = TestClient(create_app(settings))
    assert client.post(S1 + "/consent", json=CONSENT).status_code == 201
    assert seen == ["s1_dat_01"]
