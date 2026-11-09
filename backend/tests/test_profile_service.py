import pytest

from app.repositories.user_repository import UserRepository
from app.services import profile_service


@pytest.fixture
def fresh_repository(monkeypatch):
    repository = UserRepository()

    monkeypatch.setattr(
        "app.services.profile_service.user_repository",
        repository,
    )

    return repository


def test_get_profile(fresh_repository):
    user = fresh_repository.create_user(
        name="Profile User",
        email="profile@finex.com",
        hashed_password="hashed123",
    )

    profile = profile_service.get_profile(user.id)

    assert profile["user_id"] == user.id
    assert profile["name"] == "Profile User"
    assert profile["email"] == "profile@finex.com"
    assert profile["risk_profile"] is None


def test_update_profile(fresh_repository):
    user = fresh_repository.create_user(
        name="Old Name",
        email="updateprofile@finex.com",
        hashed_password="hashed123",
    )

    profile = profile_service.update_profile(
        user.id,
        {
            "name": "New Name",
            "risk_profile": "moderate",
        },
    )

    assert profile["user_id"] == user.id
    assert profile["name"] == "New Name"
    assert profile["email"] == "updateprofile@finex.com"
    assert profile["risk_profile"] == "moderate"
