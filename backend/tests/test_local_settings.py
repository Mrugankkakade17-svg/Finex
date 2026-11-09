"""LOCAL opt-in never makes a synthetic persona service publicly exposed."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config.settings import Settings
from app.core.exceptions import ConfigurationError
from app.main import create_app


def test_local_ttl_environment_is_integer(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_SESSION_TTL_MINUTES", "30")
    assert Settings(_env_file=None).local_session_ttl_minutes == 30


@pytest.mark.parametrize("path", [":memory:", "file:memory?mode=memory"])
def test_native_store_requires_a_real_file(path: str) -> None:
    with pytest.raises(ValidationError):
        Settings(local_db_path=path)


@pytest.mark.parametrize("value", [0, 61, True, 1.5, "not-an-integer"])
def test_local_ttl_is_bounded(value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(local_session_ttl_minutes=value)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.0.1", "::", "example.com"])
def test_local_host_must_be_loopback(host: str) -> None:
    with pytest.raises(ConfigurationError, match="loopback"):
        Settings(local_app_enabled=True, host=host)


@pytest.mark.parametrize(
    "origin",
    [
        "https://app.example.com",
        "*",
        "http://127.0.0.1:3000/path",
        "http://user:secret@localhost:3000",
        "http://localhost:invalid",
        "http://localhost:99999",
        "http://localhost:3000/?query=x",
    ],
)
def test_local_client_origin_is_explicit_and_valid(origin: str) -> None:
    with pytest.raises(ConfigurationError, match="loopback"):
        Settings(local_app_enabled=True, allowed_origins=[origin], allow_credentials=False)


def test_non_loopback_peer_and_origin_denied_before_database(tmp_path: Path) -> None:
    path = tmp_path / "not-opened.sqlite3"
    application = create_app(Settings(local_app_enabled=True, local_db_path=path))
    remote = TestClient(application, client=("192.168.1.22", 50000))
    response = remote.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert response.status_code == 403
    assert response.json()["error_code"] == "LOCAL_APPLICATION_ONLY"
    assert not path.exists()
    local = TestClient(application)
    response = local.post(
        "/api/v1/local-auth/mock-login",
        json={"alias": "learner-a"},
        headers={"Origin": "https://untrusted.example"},
    )
    assert response.status_code == 403
    assert not path.exists()


@pytest.mark.parametrize("environment", ["dev", "uat", "prod"])
def test_nonlocal_app_guard_precedes_session_and_storage(tmp_path: Path, environment: str) -> None:
    path = tmp_path / "not-opened.sqlite3"
    settings = Settings(
        app_env=environment,
        local_app_enabled=True,
        local_db_path=path,
        debug=False,
        api_base_url="https://api.finex.example",
        allowed_origins=["http://127.0.0.1:3000"],
        secret_key="s" * 32,
        llm_provider="none",
    )
    client = TestClient(create_app(settings))
    for method, endpoint, payload in [
        ("post", "local-auth/mock-login", {"alias": "learner-a"}),
        ("get", "local-auth/me", None),
        ("post", "local-auth/logout", {}),
        ("get", "local-onboarding/state", None),
        ("put", "local-onboarding/draft", {}),
        ("post", "local-onboarding/consent", {}),
        ("post", "local-onboarding/complete", {}),
    ]:
        kwargs = {"json": payload} if method != "get" else {}
        response = getattr(client, method)(f"/api/v1/{endpoint}", **kwargs)
        assert response.status_code == 403
        assert response.json()["error_code"] == "LOCAL_APPLICATION_ONLY"
    assert not path.exists()
