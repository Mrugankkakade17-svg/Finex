"""
Unit tests for UserRepository

Tests CRUD and Google OAuth user management using a fresh repository per test.
"""

import pytest

from app.models.user import UserModel
from app.repositories.user_repository import UserRepository


@pytest.fixture
def repo():
    """A fresh in-memory repository for each test."""
    return UserRepository()


class TestCreateUser:
    def test_creates_user_with_correct_fields(self, repo):
        user = repo.create_user("Alice", "alice@finex.com", "hashed_pw")
        assert user.id == 1
        assert user.name == "Alice"
        assert user.email == "alice@finex.com"
        assert user.hashed_password == "hashed_pw"
        assert user.is_active is True
        assert user.role == "user"

    def test_increments_id_for_each_user(self, repo):
        user1 = repo.create_user("Alice", "alice@finex.com", "pw1")
        user2 = repo.create_user("Bob", "bob@finex.com", "pw2")
        assert user1.id == 1
        assert user2.id == 2

    def test_returns_user_model_instance(self, repo):
        user = repo.create_user("Alice", "alice@finex.com", "pw")
        assert isinstance(user, UserModel)


class TestGetUserByEmail:
    def test_returns_user_when_found(self, repo):
        repo.create_user("Alice", "alice@finex.com", "pw")
        user = repo.get_user_by_email("alice@finex.com")
        assert user is not None
        assert user.email == "alice@finex.com"

    def test_returns_none_when_not_found(self, repo):
        assert repo.get_user_by_email("nobody@finex.com") is None

    def test_case_sensitive_email_lookup(self, repo):
        repo.create_user("Alice", "alice@finex.com", "pw")
        assert repo.get_user_by_email("ALICE@FINEX.COM") is None


class TestGetUserById:
    def test_returns_user_when_found(self, repo):
        created = repo.create_user("Alice", "alice@finex.com", "pw")
        user = repo.get_user_by_id(created.id)
        assert user is not None
        assert user.id == created.id

    def test_returns_none_for_missing_id(self, repo):
        assert repo.get_user_by_id(999) is None


class TestGetOrCreateGoogleUser:
    def test_creates_new_google_user(self, repo):
        user = repo.get_or_create_google_user(
            google_id="gid_123",
            email="alice@finex.com",
            name="Alice Smith",
            picture="https://example.com/pic.jpg",
        )
        assert user.id == 1
        assert user.email == "alice@finex.com"
        assert user.google_id == "gid_123"
        assert user.picture == "https://example.com/pic.jpg"

    def test_returns_existing_google_user_on_second_call(self, repo):
        user1 = repo.get_or_create_google_user("gid_123", "alice@finex.com", "Alice")
        user2 = repo.get_or_create_google_user("gid_123", "alice@finex.com", "Alice")
        assert user1.id == user2.id

    def test_does_not_create_duplicate_users(self, repo):
        repo.get_or_create_google_user("gid_123", "alice@finex.com", "Alice")
        repo.get_or_create_google_user("gid_123", "alice@finex.com", "Alice")
        assert len(repo.list_users()) == 1

    def test_links_google_to_existing_email_password_user(self, repo):
        """If email already exists (password user), link google_id without creating duplicate."""
        password_user = repo.create_user("Alice", "alice@finex.com", "hashed_pw")
        google_user = repo.get_or_create_google_user(
            google_id="gid_new",
            email="alice@finex.com",
            name="Alice",
        )
        assert google_user.id == password_user.id
        assert google_user.google_id == "gid_new"
        assert len(repo.list_users()) == 1

    def test_google_user_has_empty_password(self, repo):
        user = repo.get_or_create_google_user("gid_123", "alice@finex.com", "Alice")
        assert user.hashed_password == ""


class TestUpdateUser:
    def test_updates_allowed_fields(self, repo):
        user = repo.create_user("Alice", "alice@finex.com", "pw")
        updated = repo.update_user(user.id, {"name": "Alice Updated"})
        assert updated.name == "Alice Updated"

    def test_returns_none_for_missing_user(self, repo):
        result = repo.update_user(999, {"name": "Ghost"})
        assert result is None


class TestDeleteUser:
    def test_deletes_existing_user(self, repo):
        user = repo.create_user("Alice", "alice@finex.com", "pw")
        result = repo.delete_user(user.id)
        assert result is True
        assert repo.get_user_by_id(user.id) is None

    def test_returns_false_for_missing_user(self, repo):
        assert repo.delete_user(999) is False
