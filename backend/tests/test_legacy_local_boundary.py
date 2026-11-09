"""Existing LOCAL JWT examples remain compatibility, never deployed identity."""

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app


@pytest.mark.parametrize("environment", ["dev", "uat", "prod"])
def test_legacy_identity_routes_fail_closed_nonlocal(environment: str) -> None:
    settings = Settings(
        app_env=environment,
        debug=False,
        api_base_url="https://api.finex.example",
        allowed_origins=["https://app.finex.example"],
        secret_key="s" * 32,
        llm_provider="none",
    )
    client = TestClient(create_app(settings))
    for method, path in [
        ("post", "/api/v1/auth/register"),
        ("post", "/api/v1/auth/login"),
        ("get", "/api/v1/auth/me"),
        ("post", "/api/v1/auth/refresh"),
        ("post", "/api/v1/auth/logout"),
        ("post", "/api/v1/auth/google/callback"),
        ("get", "/api/v1/users"),
        ("get", "/api/v1/users/1"),
        ("get", "/api/v1/users/me/profile"),
        ("post", "/api/v1/onboarding/complete"),
    ]:
        kwargs = {"content": "{malformed", "headers": {"Content-Type": "application/json"}}
        response = getattr(client, method)(path, **kwargs) if method == "post" else client.get(path)
        assert response.status_code == 403
        assert response.json()["error_code"] == "LOCAL_PILOT_ONLY"


def test_legacy_user_endpoints_do_not_expose_other_users() -> None:
    client = TestClient(create_app(Settings()))
    tokens = []
    for name, email in [("Synthetic A", "a@example.com"), ("Synthetic B", "b@example.com")]:
        response = client.post(
            "/api/v1/auth/register", json={"name": name, "email": email, "password": "Testing@123"}
        )
        assert response.status_code == 200
        tokens.append(response.json()["data"]["access_token"])
    headers = {"Authorization": f"Bearer {tokens[0]}"}
    users = client.get("/api/v1/users", headers=headers).json()["data"]
    assert len(users) == 1
    assert users[0]["email"] == "a@example.com"
    response = client.get("/api/v1/users/2", headers=headers)
    assert response.status_code == 404
    assert "b@example.com" not in response.text
    assert client.get("/api/v1/users/1", headers=headers).status_code == 200


def test_new_opaque_session_is_not_legacy_jwt(tmp_path) -> None:
    client = TestClient(
        create_app(Settings(local_app_enabled=True, local_db_path=tmp_path / "opaque.sqlite3"))
    )
    response = client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['data']['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
