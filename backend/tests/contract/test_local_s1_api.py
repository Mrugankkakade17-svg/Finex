"""Persistent LOCAL S1 contract; the old anonymous pilots are not this API."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app

AUTH = "/api/v1/local-auth"
ONBOARDING = "/api/v1/local-onboarding"
PROFILE = {
    "profile_schema_version": "profile.v1",
    "display_name": "Test learner",
    "experience_level": "beginner",
}
CONSENT = {"consent_version": "consent.v1", "consent_given": True}
COMPLETE = {"consent_version": "consent.v1", "profile_schema_version": "profile.v1"}


class TestClock:
    __test__ = False

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    application = create_app(
        Settings(local_app_enabled=True, local_db_path=tmp_path / "s1.sqlite3")
    )
    application.state.local_clock = TestClock()
    return TestClient(application)


def login(client: TestClient, alias: str = "learner-a") -> dict[str, str]:
    response = client.post(f"{AUTH}/mock-login", json={"alias": alias})
    assert response.status_code == 200
    result = response.json()
    assert result["data"]["scope"] == "local_educational_application"
    assert result["data"]["contract_version"] == "local.v1"
    assert result["data"]["token_type"] == "Bearer"
    assert result["meta"]["dataStatus"] == "CACHED"
    return {"Authorization": f"Bearer {result['data']['access_token']}"}


def assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status
    body = response.json()
    assert body["success"] is False
    assert body["error_code"] == code
    assert body["error"]["code"] == code
    assert body["error"]["correlationId"]


def state(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.get(f"{ONBOARDING}/state", headers=headers)
    assert response.status_code == 200
    assert response.json()["meta"]["dataStatus"] == "CACHED"
    return response.json()["data"]


def finish(client: TestClient, headers: dict[str, str]) -> dict:
    assert client.put(f"{ONBOARDING}/draft", headers=headers, json=PROFILE).status_code == 200
    assert client.post(f"{ONBOARDING}/consent", headers=headers, json=CONSENT).status_code == 200
    response = client.post(f"{ONBOARDING}/complete", headers=headers, json=COMPLETE)
    assert response.status_code == 200
    return response.json()["data"]


def test_login_and_initial_state(client: TestClient) -> None:
    headers = login(client)
    me = client.get(f"{AUTH}/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["data"]["user"]["alias"] == "learner-a"
    assert state(client, headers) == {
        "scope": "local_educational_application",
        "contract_version": "local.v1",
        "profile_schema_version": "profile.v1",
        "consent_version": "consent.v1",
        "consent": None,
        "draft": {"display_name": None, "experience_level": None, "updated_at": None},
        "onboarding_completed": False,
        "completed_at": None,
    }


@pytest.mark.parametrize(
    "credential", [None, "Bearer invalid", "Basic abc", "Bearer", "Bearer a b", "Bearer "]
)
def test_session_required(client: TestClient, credential: str | None) -> None:
    headers = {"Authorization": credential} if credential else {}
    assert_error(client.get(f"{ONBOARDING}/state", headers=headers), 401, "SESSION_INVALID")


def test_query_token_is_not_authentication(client: TestClient) -> None:
    assert_error(client.get(f"{AUTH}/me?access_token=not-a-credential"), 401, "SESSION_INVALID")


def test_unknown_alias_and_identity_injection(client: TestClient) -> None:
    assert_error(
        client.post(f"{AUTH}/mock-login", json={"alias": "someone"}), 422, "UNKNOWN_LOCAL_ALIAS"
    )
    assert_error(
        client.post(f"{AUTH}/mock-login", json={"alias": "learner-a", "owner_id": "b"}),
        422,
        "VALIDATION_ERROR",
    )


def test_two_personas_and_trace_header_do_not_select_owner(client: TestClient) -> None:
    first = login(client)
    second = login(client, "learner-b")
    first["X-Correlation-ID"] = "same-client-controlled-trace"
    second["X-Correlation-ID"] = "same-client-controlled-trace"
    assert client.put(f"{ONBOARDING}/draft", headers=first, json=PROFILE).status_code == 200
    assert state(client, first)["draft"]["display_name"] == "Test learner"
    assert state(client, second)["draft"]["display_name"] is None
    assert_error(
        client.put(
            f"{ONBOARDING}/draft", headers=second, json={**PROFILE, "owner_id": "learner-a"}
        ),
        422,
        "VALIDATION_ERROR",
    )


def test_partial_draft_is_saved_but_never_complete(client: TestClient) -> None:
    headers = login(client)
    draft = {**PROFILE, "display_name": "   ", "experience_level": None}
    response = client.put(f"{ONBOARDING}/draft", headers=headers, json=draft)
    assert response.status_code == 200
    assert response.json()["data"]["draft"]["display_name"] == ""
    assert response.json()["data"]["onboarding_completed"] is False
    assert_error(
        client.post(f"{ONBOARDING}/complete", headers=headers, json=COMPLETE),
        409,
        "CONSENT_REQUIRED",
    )
    client.post(f"{ONBOARDING}/consent", headers=headers, json=CONSENT)
    assert_error(
        client.post(f"{ONBOARDING}/complete", headers=headers, json=COMPLETE),
        409,
        "PROFILE_INCOMPLETE",
    )


def test_first_all_null_draft_records_save_time(client: TestClient) -> None:
    headers = login(client)
    response = client.put(
        f"{ONBOARDING}/draft",
        headers=headers,
        json={**PROFILE, "display_name": None, "experience_level": None},
    )
    assert response.status_code == 200
    assert response.json()["data"]["draft"]["updated_at"] is not None
    assert response.json()["data"]["onboarding_completed"] is False


@pytest.mark.parametrize(
    "change",
    [
        {"experience_level": "invalid"},
        {"display_name": "x" * 81},
        {"owner_id": "learner-b"},
        {"display_name": 123},
    ],
)
def test_invalid_draft_is_not_saved(client: TestClient, change: dict) -> None:
    headers = login(client)
    assert_error(
        client.put(f"{ONBOARDING}/draft", headers=headers, json={**PROFILE, **change}),
        422,
        "VALIDATION_ERROR",
    )
    assert state(client, headers)["draft"]["updated_at"] is None


def test_draft_required_fields_and_trimmed_limit(client: TestClient) -> None:
    headers = login(client)
    assert_error(
        client.put(
            f"{ONBOARDING}/draft",
            headers=headers,
            json={"profile_schema_version": "profile.v1", "display_name": "x"},
        ),
        422,
        "VALIDATION_ERROR",
    )
    response = client.put(
        f"{ONBOARDING}/draft",
        headers=headers,
        json={**PROFILE, "display_name": "  " + "x" * 80 + "  "},
    )
    assert response.status_code == 200
    assert response.json()["data"]["draft"]["display_name"] == "x" * 80


@pytest.mark.parametrize(
    ("route", "method", "payload", "code"),
    [
        (
            "draft",
            "put",
            {**PROFILE, "profile_schema_version": "profile.v2"},
            "PROFILE_VERSION_MISMATCH",
        ),
        (
            "consent",
            "post",
            {**CONSENT, "consent_version": "consent.v2"},
            "CONSENT_VERSION_MISMATCH",
        ),
        (
            "complete",
            "post",
            {**COMPLETE, "profile_schema_version": "profile.v2"},
            "PROFILE_VERSION_MISMATCH",
        ),
        (
            "complete",
            "post",
            {**COMPLETE, "consent_version": "consent.v2"},
            "CONSENT_VERSION_MISMATCH",
        ),
    ],
)
def test_version_drift(
    client: TestClient, route: str, method: str, payload: dict, code: str
) -> None:
    headers = login(client)
    assert_error(
        getattr(client, method)(f"{ONBOARDING}/{route}", headers=headers, json=payload), 409, code
    )


def test_completion_repeats_and_profile_invalidation(client: TestClient) -> None:
    headers = login(client)
    completed = finish(client, headers)
    assert completed["onboarding_completed"] is True
    clock = client.app.state.local_clock
    clock.now += timedelta(minutes=1)
    repeat = client.post(f"{ONBOARDING}/complete", headers=headers, json=COMPLETE).json()["data"]
    assert repeat["completed_at"] == completed["completed_at"]
    assert (
        client.put(f"{ONBOARDING}/draft", headers=headers, json=PROFILE).json()["data"][
            "completed_at"
        ]
        == completed["completed_at"]
    )
    changed = client.put(
        f"{ONBOARDING}/draft", headers=headers, json={**PROFILE, "display_name": "Changed label"}
    ).json()["data"]
    assert changed["onboarding_completed"] is False
    assert changed["completed_at"] is None


def test_withdrawal_and_reacceptance_do_not_restore_completion(client: TestClient) -> None:
    headers = login(client)
    completed = finish(client, headers)
    same = client.post(f"{ONBOARDING}/consent", headers=headers, json=CONSENT).json()["data"]
    assert same["completed_at"] == completed["completed_at"]
    revoked = client.post(
        f"{ONBOARDING}/consent", headers=headers, json={**CONSENT, "consent_given": False}
    ).json()["data"]
    assert revoked["consent"]["accepted"] is False
    assert revoked["onboarding_completed"] is False
    assert_error(
        client.post(f"{ONBOARDING}/complete", headers=headers, json=COMPLETE),
        409,
        "CONSENT_REQUIRED",
    )
    accepted = client.post(f"{ONBOARDING}/consent", headers=headers, json=CONSENT).json()["data"]
    assert accepted["consent"]["accepted"] is True
    assert accepted["onboarding_completed"] is False


@pytest.mark.parametrize("decision", ["true", 1, None])
def test_consent_boolean_is_not_coerced(client: TestClient, decision: object) -> None:
    headers = login(client)
    assert_error(
        client.post(
            f"{ONBOARDING}/consent", headers=headers, json={**CONSENT, "consent_given": decision}
        ),
        422,
        "VALIDATION_ERROR",
    )
    assert state(client, headers)["consent"] is None


def test_logout_is_server_revocation_and_relogin_restores_data(client: TestClient) -> None:
    headers = login(client)
    completed = finish(client, headers)
    assert_error(
        client.post(f"{AUTH}/logout", headers=headers, json={"owner_id": "other"}),
        422,
        "VALIDATION_ERROR",
    )
    response = client.post(f"{AUTH}/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["data"]["signed_out"] is True
    assert_error(client.get(f"{AUTH}/me", headers=headers), 401, "SESSION_INVALID")
    new_headers = login(client)
    assert state(client, new_headers)["completed_at"] == completed["completed_at"]


def test_expiry_is_enforced(client: TestClient) -> None:
    headers = login(client)
    client.app.state.local_clock.now += timedelta(minutes=30)
    assert_error(client.get(f"{AUTH}/me", headers=headers), 401, "SESSION_INVALID")


def test_default_disabled_has_no_database_side_effect(tmp_path: Path) -> None:
    path = tmp_path / "disabled.sqlite3"
    client = TestClient(create_app(Settings(local_db_path=path)))
    assert_error(
        client.post(f"{AUTH}/mock-login", json={"alias": "learner-a"}),
        403,
        "LOCAL_APPLICATION_ONLY",
    )
    assert not path.exists()
