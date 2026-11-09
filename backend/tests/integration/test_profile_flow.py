"""
Integration tests for the Profile API.

These tests exercise the real router -> service -> repository flow.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.repositories.user_repository import UserRepository

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_user_repository(monkeypatch):
    fresh_repo = UserRepository()

    monkeypatch.setattr(
        "app.services.auth_service.user_repository",
        fresh_repo,
    )

    monkeypatch.setattr(
        "app.services.profile_service.user_repository",
        fresh_repo,
    )

    monkeypatch.setattr(
        "app.routers.users.user_repository",
        fresh_repo,
    )


def google_login(email: str, name: str):
    response = client.post(
        "/api/v1/auth/google/callback",
        json={
            "id_token": f"mock:{email}:{name}",
        },
    )

    assert response.status_code == 200

    return response.json()["data"]


class TestProfileFlow:
    def test_get_profile_authenticated(self):
        tokens = google_login(
            "profile_flow@finex.com",
            "Profile Flow User",
        )

        response = client.get(
            "/api/v1/users/me/profile",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True

        profile = body["data"]

        assert profile["user_id"] is not None
        assert profile["email"] == "profile_flow@finex.com"
        assert profile["name"] == "Profile Flow User"
        assert "risk_profile" in profile

    def test_update_profile_authenticated(self):
        tokens = google_login(
            "profile_update@finex.com",
            "Original Name",
        )

        response = client.put(
            "/api/v1/users/me/profile",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            json={
                "name": "Updated Name",
            },
        )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True

        profile = body["data"]

        assert profile["name"] == "Updated Name"
        assert profile["email"] == "profile_update@finex.com"

    def test_get_profile_without_token(self):
        response = client.get("/api/v1/users/me/profile")

        assert response.status_code == 403

    def test_update_profile_without_token(self):
        response = client.put(
            "/api/v1/users/me/profile",
            json={
                "name": "Unauthorized",
            },
        )

        assert response.status_code == 403

    def test_get_profile_with_invalid_token(self):
        response = client.get(
            "/api/v1/users/me/profile",
            headers={
                "Authorization": "Bearer invalid-token",
            },
        )

        assert response.status_code == 401
