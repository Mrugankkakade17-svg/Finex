"""Denied requests fail closed before body parsing or local database access."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app


@pytest.mark.parametrize("mode", ["disabled", "dev", "peer", "origin"])
def test_boundary_precedes_malformed_body(tmp_path: Path, mode: str) -> None:
    path = tmp_path / "not-opened.sqlite3"
    application = create_app(
        Settings(
            local_app_enabled=mode != "disabled",
            app_env="dev" if mode == "dev" else "local",
            local_db_path=path,
        )
    )
    client = TestClient(
        application, client=("192.168.1.22", 50000) if mode == "peer" else ("127.0.0.1", 50000)
    )
    response = client.post(
        "/api/v1/local-auth/mock-login",
        content="{malformed",
        headers={
            "Content-Type": "application/json",
            "Origin": "https://remote.example" if mode == "origin" else "http://localhost:3000",
            "Host": "localhost:8000",
            "X-Forwarded-For": "127.0.0.1",
        },
    )
    assert response.status_code == 403
    assert response.json()["error_code"] == "LOCAL_APPLICATION_ONLY"
    assert not path.exists()


@pytest.mark.parametrize(
    "incoming", ["x" * 129, "an-email@example.com", "unsafe space", "<script>"]
)
def test_invalid_correlation_replaced_before_echo(tmp_path: Path, incoming: str) -> None:
    client = TestClient(create_app(Settings(local_db_path=tmp_path / "unused.sqlite3")))
    response = client.get("/api/v1/local-onboarding/state", headers={"X-Correlation-ID": incoming})
    safe = response.headers["X-Correlation-ID"]
    assert safe != incoming
    assert len(safe) == 36
    assert response.json()["error"]["correlationId"] == safe


def test_local_field_errors_do_not_reflect_arbitrary_body_keys(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(local_app_enabled=True, local_db_path=tmp_path / "keys.sqlite3"))
    )
    sensitive_key = "this-is-not-an-approved-field-name"
    response = client.post(
        "/api/v1/local-auth/mock-login", json={"alias": "learner-a", sensitive_key: "value"}
    )
    assert response.status_code == 422
    assert sensitive_key not in response.text


@pytest.mark.parametrize("malformed", [False, True])
def test_correlation_does_not_reflect_embedded_or_malformed_bearer(
    tmp_path: Path, malformed: bool
) -> None:
    client = TestClient(
        create_app(Settings(local_app_enabled=True, local_db_path=tmp_path / "trace.sqlite3"))
    )
    login = client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    headers = {
        "Authorization": "Bearer " + token + (" extra" if malformed else ""),
        "X-Correlation-ID": token if malformed else "trace." + token,
    }
    response = client.get("/api/v1/local-onboarding/state", headers=headers)
    assert response.status_code == (401 if malformed else 200)
    # Do not let a failing regression print the generated credential itself.
    leaked_body = token in response.text
    leaked_header = token in response.headers["X-Correlation-ID"]
    assert leaked_body is False
    assert leaked_header is False


def test_safe_diagnostic_id_preserved_with_bearer(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(local_app_enabled=True, local_db_path=tmp_path / "safe-trace.sqlite3"))
    )
    login = client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert login.status_code == 200
    headers = {
        "Authorization": "Bearer " + login.json()["data"]["access_token"],
        "X-Correlation-ID": "s1-review-diagnostic-001",
    }
    response = client.get("/api/v1/local-onboarding/state", headers=headers)
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "s1-review-diagnostic-001"


@pytest.mark.parametrize("prefix", ["", "Bearer", "Bearer:", "Bearer=", "Bearer,"])
def test_single_part_malformed_authorization_is_not_a_trace(tmp_path: Path, prefix: str) -> None:
    client = TestClient(
        create_app(
            Settings(local_app_enabled=True, local_db_path=tmp_path / "single-trace.sqlite3")
        )
    )
    login = client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert login.status_code == 200
    token = login.json()["data"]["access_token"]
    response = client.get(
        "/api/v1/local-auth/me",
        headers={"Authorization": prefix + token, "X-Correlation-ID": "trace." + token},
    )
    assert response.status_code == 401
    leaked_body = token in response.text
    leaked_header = token in response.headers["X-Correlation-ID"]
    assert leaked_body is False
    assert leaked_header is False
