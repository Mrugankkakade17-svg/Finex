from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.core.middleware import CorrelationIdMiddleware
from app.repositories.user_repository import UserRepository
from app.routers.profile import router
from app.services import profile_service

app = FastAPI()

app.add_middleware(CorrelationIdMiddleware)

app.include_router(router)


def fake_current_user():
    return {
        "user_id": 1,
        "email": "profile@finex.com",
    }


app.dependency_overrides[get_current_user] = fake_current_user


# Use a fresh repository for this test module
test_user_repository = UserRepository()

test_user_repository.create_user(
    name="Profile User",
    email="profile@finex.com",
    hashed_password="test-hash",
)


# Make the profile service use the same repository
profile_service.user_repository = test_user_repository


client = TestClient(app)


def test_get_profile_endpoint():
    response = client.get("/api/v1/users/me/profile")

    assert response.status_code == 200

    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]


def test_update_profile_endpoint():
    response = client.put(
        "/api/v1/users/me/profile",
        json={
            "name": "Updated Profile",
            "risk_profile": "moderate",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"]
