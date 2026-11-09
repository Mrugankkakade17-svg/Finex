from unittest.mock import patch

import pytest

from app.core.exceptions import BadRequestException, UnauthorizedException
from app.models.user import UserModel
from app.services import auth_service


def make_user():
    return UserModel(
        id=1,
        name="Test User",
        email="test@finex.com",
        hashed_password="hashed_password",
        created_at=None,
        updated_at=None,
        is_active=True,
        role="user",
        risk_profile=None,
    )


def test_register_success():
    user = make_user()

    with (
        patch.object(auth_service.user_repository, "get_user_by_email", return_value=None),
        patch.object(auth_service.user_repository, "create_user", return_value=user),
        patch.object(auth_service, "hash_password", return_value="hashed"),
        patch.object(auth_service, "create_access_token", return_value="access-token"),
        patch.object(auth_service, "create_refresh_token", return_value="refresh-token"),
    ):
        result = auth_service.register(
            name="Test User",
            email="test@finex.com",
            password="password123",
        )

    assert result["access_token"] == "access-token"
    assert result["refresh_token"] == "refresh-token"
    assert result["token_type"] == "bearer"


def test_register_duplicate_email():
    user = make_user()

    with patch.object(
        auth_service.user_repository,
        "get_user_by_email",
        return_value=user,
    ):
        with pytest.raises(BadRequestException):
            auth_service.register(
                name="Test User",
                email="test@finex.com",
                password="password123",
            )


def test_login_success():
    user = make_user()

    with (
        patch.object(auth_service.user_repository, "get_user_by_email", return_value=user),
        patch.object(auth_service, "verify_password", return_value=True),
        patch.object(auth_service, "create_access_token", return_value="access-token"),
        patch.object(auth_service, "create_refresh_token", return_value="refresh-token"),
    ):
        result = auth_service.login(
            email="test@finex.com",
            password="password123",
        )

    assert result["access_token"] == "access-token"
    assert result["refresh_token"] == "refresh-token"
    assert result["token_type"] == "bearer"


def test_login_user_not_found():
    with patch.object(
        auth_service.user_repository,
        "get_user_by_email",
        return_value=None,
    ):
        with pytest.raises(UnauthorizedException):
            auth_service.login(
                email="unknown@finex.com",
                password="password123",
            )


def test_login_wrong_password():
    user = make_user()

    with (
        patch.object(auth_service.user_repository, "get_user_by_email", return_value=user),
        patch.object(auth_service, "verify_password", return_value=False),
    ):
        with pytest.raises(UnauthorizedException):
            auth_service.login(
                email="test@finex.com",
                password="wrong-password",
            )


def test_get_current_user_invalid_token():
    with patch.object(auth_service, "decode_token", return_value=None):
        with pytest.raises(UnauthorizedException):
            auth_service.get_current_user("invalid-token")


def test_get_current_user_wrong_token_type():
    with patch.object(
        auth_service,
        "decode_token",
        return_value={
            "sub": "test@finex.com",
            "user_id": 1,
            "type": "refresh",
        },
    ):
        with pytest.raises(UnauthorizedException):
            auth_service.get_current_user("refresh-token")


def test_get_current_user_success():
    payload = {
        "sub": "test@finex.com",
        "user_id": 1,
        "type": "access",
    }

    with patch.object(
        auth_service,
        "decode_token",
        return_value=payload,
    ):
        result = auth_service.get_current_user("access-token")

    assert result == payload


def test_refresh_invalid_token():
    with patch.object(auth_service, "decode_token", return_value=None):
        with pytest.raises(UnauthorizedException):
            auth_service.refresh("invalid-token")


def test_refresh_wrong_token_type():
    with patch.object(
        auth_service,
        "decode_token",
        return_value={
            "sub": "test@finex.com",
            "user_id": 1,
            "type": "access",
        },
    ):
        with pytest.raises(UnauthorizedException):
            auth_service.refresh("access-token")


def test_refresh_success():
    payload = {
        "sub": "test@finex.com",
        "user_id": 1,
        "type": "refresh",
    }

    with (
        patch.object(auth_service, "decode_token", return_value=payload),
        patch.object(
            auth_service,
            "create_access_token",
            return_value="new-access-token",
        ),
    ):
        result = auth_service.refresh("refresh-token")

    assert result == {
        "access_token": "new-access-token",
        "token_type": "bearer",
    }


def test_logout():
    result = auth_service.logout()
    assert result == {}
