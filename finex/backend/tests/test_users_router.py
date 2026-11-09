"""
Tests for /api/v1/users endpoints.
Uses user_repository monkeypatching (new pattern — repository layer, not service layer).
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.repositories.user_repository import UserRepository
from app.routers.users import router

app = FastAPI()
app.include_router(router)


def fake_current_user():
    return {
        "user_id": 1,
        "email": "test@finex.com",
    }


app.dependency_overrides[get_current_user] = fake_current_user

client = TestClient(app)


def test_get_users(monkeypatch):
    fresh_repo = UserRepository()
    fresh_repo.create_user("Test User", "test@finex.com", "hashed")
    monkeypatch.setattr("app.routers.users.user_repository", fresh_repo)

    response = client.get("/api/v1/users")
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]
    assert len(body["data"]) == 1
    assert body["data"][0]["email"] == "test@finex.com"
    assert body["data"][0]["name"] == "Test User"


def test_get_user(monkeypatch):
    fresh_repo = UserRepository()
    fresh_repo.create_user("Test User", "test@finex.com", "hashed")
    monkeypatch.setattr("app.routers.users.user_repository", fresh_repo)

    response = client.get("/api/v1/users/1")
    assert response.status_code == 200

    body = response.json()
    assert "data" in body
    assert "meta" in body
    assert body["meta"]["apiVersion"] == "v1"
    assert body["data"]["email"] == "test@finex.com"
    assert body["data"]["name"] == "Test User"
    assert body["data"]["id"] == 1
