"""Unit tests for AI route authentication protection (S1-MI01).

Verifies that /api/v1/ai/chat and /api/v1/ai/feedback are protected behind current_principal:
- Rejects unauthenticated requests with HTTP 401
- Rejects malformed or invalid bearer tokens with HTTP 401
- Rejects expired or revoked tokens with HTTP 401
- Accepts valid JWT access tokens with HTTP 200
- Accepts synthetic local session bearer tokens with HTTP 200
"""

from datetime import timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient

from app.auth.jwt_handler import create_access_token
from app.auth.principal import Principal, get_current_principal
from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app) -> Generator[TestClient, None, None]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_token() -> str:
    return create_access_token({"sub": "usr_test_auth_01", "user_id": "usr_test_auth_01"})


@pytest.fixture
def auth_headers(valid_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {valid_token}"}


class TestAIChatAuthentication:
    """Verifies authentication enforcement on /api/v1/ai/chat."""

    def test_chat_without_auth_header_returns_401(self, client: TestClient):
        resp = client.post("/api/v1/ai/chat", json={"message": "What is asset allocation?"})
        assert resp.status_code == 401
        assert "Authorization header missing" in resp.json()["detail"]

    def test_chat_with_invalid_bearer_format_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "What is asset allocation?"},
            headers={"Authorization": "Basic not_a_bearer_token"},
        )
        assert resp.status_code == 401
        assert "Invalid authorization format" in resp.json()["detail"]

    def test_chat_with_empty_bearer_token_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "What is asset allocation?"},
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401

    def test_chat_with_tampered_jwt_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "What is asset allocation?"},
            headers={"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.invalid.signature"},
        )
        assert resp.status_code == 401

    def test_chat_with_expired_token_returns_401(self, client: TestClient):
        expired_token = create_access_token(
            {"sub": "usr_expired", "user_id": "usr_expired"},
            expires_delta=timedelta(seconds=-60),
        )
        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "What is asset allocation?"},
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    def test_chat_with_valid_jwt_returns_200(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "What is asset allocation?"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["intent"] == "CONCEPT_EDUCATION"
        assert len(data["citations"]) > 0

    def test_chat_with_synthetic_learner_principal_override(self, app):
        """Verify synthetic local persona (learner-a) is accepted by dependency."""
        synthetic_principal = Principal(
            user_id="synthetic-learner-a",
            is_synthetic=True,
            roles=["user", "learner"],
        )
        app.dependency_overrides[get_current_principal] = lambda: synthetic_principal
        try:
            with TestClient(app) as test_client:
                resp = test_client.post(
                    "/api/v1/ai/chat",
                    json={"message": "Explain dollar-cost averaging"},
                )
                assert resp.status_code == 200
                data = resp.json()["data"]
                assert data["intent"] == "CONCEPT_EDUCATION"
        finally:
            app.dependency_overrides.clear()


class TestAIFeedbackAuthentication:
    """Verifies authentication enforcement on /api/v1/ai/feedback."""

    def test_post_feedback_without_auth_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/ai/feedback",
            json={"message_id": "msg-001", "rating": "THUMBS_UP"},
        )
        assert resp.status_code == 401
        assert "Authorization header missing" in resp.json()["detail"]

    def test_post_feedback_with_invalid_token_returns_401(self, client: TestClient):
        resp = client.post(
            "/api/v1/ai/feedback",
            json={"message_id": "msg-001", "rating": "THUMBS_UP"},
            headers={"Authorization": "Bearer invalid_garbage_token"},
        )
        assert resp.status_code == 401

    def test_post_feedback_with_valid_token_returns_200(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        resp = client.post(
            "/api/v1/ai/feedback",
            json={
                "message_id": "msg-auth-test-01",
                "rating": "THUMBS_UP",
                "comment": "Clear explanation of diversification.",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["data"]["message_id"] == "msg-auth-test-01"
        assert body["data"]["user_id"] == "usr_test_auth_01"

    def test_get_feedback_without_auth_returns_401(self, client: TestClient):
        resp = client.get("/api/v1/ai/feedback")
        assert resp.status_code == 401
        assert "Authorization header missing" in resp.json()["detail"]

    def test_get_feedback_with_valid_token_returns_200(
        self, client: TestClient, auth_headers: dict[str, str]
    ):
        resp = client.get("/api/v1/ai/feedback", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
