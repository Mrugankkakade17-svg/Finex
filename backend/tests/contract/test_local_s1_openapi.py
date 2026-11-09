"""Local application documentation must not change its fail-closed runtime gates."""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app

AUTH = "/api/v1/local-auth"
ONBOARDING = "/api/v1/local-onboarding"
OPERATIONS = {
    (f"{AUTH}/mock-login", "post"),
    (f"{AUTH}/me", "get"),
    (f"{AUTH}/logout", "post"),
    (f"{ONBOARDING}/state", "get"),
    (f"{ONBOARDING}/draft", "put"),
    (f"{ONBOARDING}/consent", "post"),
    (f"{ONBOARDING}/complete", "post"),
}


def application(tmp_path: Path, *, enabled: bool = True):
    options: dict[str, Any] = {
        "_env_file": None,
        "local_app_enabled": enabled,
        "local_db_path": tmp_path / "local.sqlite3",
        "llm_provider": "none",
        "market_data_provider": "mock",
        "allow_credentials": False,
    }
    return create_app(Settings(**options))


def test_all_seven_local_operations_are_documented(tmp_path: Path) -> None:
    spec = application(tmp_path).openapi()
    actual = {
        (path, method)
        for path, methods in spec["paths"].items()
        if path.startswith((AUTH, ONBOARDING))
        for method in methods
    }
    assert actual == OPERATIONS


def test_six_protected_operations_declare_http_bearer_without_secured_login(tmp_path: Path) -> None:
    spec = application(tmp_path).openapi()
    schemes = spec["components"]["securitySchemes"]
    assert "LocalApplicationBearer" in schemes
    assert schemes["LocalApplicationBearer"]["type"] == "http"
    assert schemes["LocalApplicationBearer"]["scheme"] == "bearer"
    assert "JWT" not in schemes["LocalApplicationBearer"].get("bearerFormat", "")
    for path, method in OPERATIONS:
        security = spec["paths"][path][method].get("security", [])
        assert security == (
            [] if path.endswith("/mock-login") else [{"LocalApplicationBearer": []}]
        )


def test_documented_local_failures_include_runtime_401_403_and_409(tmp_path: Path) -> None:
    spec = application(tmp_path).openapi()
    for path, method in OPERATIONS:
        responses = spec["paths"][path][method]["responses"]
        assert {"401", "403", "409", "422", "503"} <= set(responses)


def test_nullable_draft_fields_are_required_full_replacement_not_optional(tmp_path: Path) -> None:
    schemas = application(tmp_path).openapi()["components"]["schemas"]
    for name, fields in {
        "LocalDraftRequest": {"display_name", "experience_level"},
        "LocalDraftState": {"display_name", "experience_level", "updated_at"},
        "LocalOnboardingState": {"consent", "completed_at"},
    }.items():
        schema = schemas[name]
        assert fields <= set(schema["required"])
        for field in fields:
            assert {"type": "null"} in schema["properties"][field]["anyOf"]
    request = schemas["LocalDraftRequest"]
    assert "profile_schema_version" in request["required"]
    assert request["additionalProperties"] is False
    assert schemas["LocalConsentRequest"]["properties"]["consent_given"]["type"] == "boolean"


@pytest.mark.parametrize("header", [None, "Basic synthetic", "Bearer", "Bearer invalid extra"])
def test_security_documentation_preserves_missing_or_malformed_bearer_401(
    tmp_path: Path, header: str | None
) -> None:
    headers = {} if header is None else {"Authorization": header}
    with TestClient(application(tmp_path)) as client:
        response = client.get(f"{ONBOARDING}/state", headers=headers)
    assert response.status_code == 401
    assert response.json()["error_code"] == "SESSION_INVALID"
    assert not (tmp_path / "local.sqlite3").exists()


def test_disabled_boundary_precedes_body_parsing_or_security_and_creates_no_db(
    tmp_path: Path,
) -> None:
    with TestClient(application(tmp_path, enabled=False)) as client:
        response = client.post(
            f"{AUTH}/mock-login", content="{malformed", headers={"Content-Type": "application/json"}
        )
        protected = client.get(f"{AUTH}/me", headers={"Authorization": "Basic invalid"})
    assert response.status_code == protected.status_code == 403
    assert response.json()["error_code"] == "LOCAL_APPLICATION_ONLY"
    assert protected.json()["error_code"] == "LOCAL_APPLICATION_ONLY"
    assert not (tmp_path / "local.sqlite3").exists()


def test_security_documentation_preserves_business_409_and_strict_nullable_422(
    tmp_path: Path,
) -> None:
    with TestClient(application(tmp_path)) as client:
        login = client.post(f"{AUTH}/mock-login", json={"alias": "learner-a"})
        assert login.status_code == 200
        token = login.json()["data"]["access_token"]
        headers = {"Authorization": "Bearer " + token}
        prerequisite = client.post(
            f"{ONBOARDING}/complete",
            json={"consent_version": "consent.v1", "profile_schema_version": "profile.v1"},
            headers=headers,
        )
        version = client.put(
            f"{ONBOARDING}/draft",
            json={
                "profile_schema_version": "profile.future",
                "display_name": None,
                "experience_level": None,
            },
            headers=headers,
        )
        missing = client.put(
            f"{ONBOARDING}/draft", json={"profile_schema_version": "profile.v1"}, headers=headers
        )
        nullable = client.put(
            f"{ONBOARDING}/draft",
            json={
                "profile_schema_version": "profile.v1",
                "display_name": None,
                "experience_level": None,
            },
            headers=headers,
        )
    assert prerequisite.status_code == version.status_code == 409
    assert prerequisite.json()["error_code"] == "CONSENT_REQUIRED"
    assert version.json()["error_code"] == "PROFILE_VERSION_MISMATCH"
    assert missing.status_code == 422
    assert missing.json()["error_code"] == "VALIDATION_ERROR"
    assert nullable.status_code == 200
    assert nullable.json()["data"]["draft"]["updated_at"] is not None
