import pytest

from app.services import user_service


@pytest.fixture(autouse=True)
def reset_users():
    user_service.fake_users = [
        {
            "user_id": 1,
            "email": "john@finex.com",
            "name": "John Doe",
            "is_active": True,
            "password_hash": "",
        },
        {
            "user_id": 2,
            "email": "jane@finex.com",
            "name": "Jane Smith",
            "is_active": True,
            "password_hash": "",
        },
    ]
    user_service.next_id = 3


def test_get_all_users():
    users = user_service.get_all_users()

    assert len(users) == 2
    assert users[0]["email"] == "john@finex.com"
    assert users[1]["email"] == "jane@finex.com"


def test_get_user_by_id():
    user = user_service.get_user_by_id(1)

    assert user["user_id"] == 1
    assert user["name"] == "John Doe"
    assert user["is_active"] is True


def test_get_user_by_id_not_found():
    with pytest.raises(Exception):
        user_service.get_user_by_id(999)


def test_create_user():
    user = user_service.create_user(
        email="new@finex.com",
        password="password123",
        name="New User",
    )

    assert user["user_id"] == 3
    assert user["email"] == "new@finex.com"
    assert user["name"] == "New User"
    assert user["is_active"] is True


def test_create_duplicate_user():
    with pytest.raises(Exception):
        user_service.create_user(
            email="john@finex.com",
            password="password123",
            name="Duplicate",
        )


def test_update_user():
    user = user_service.update_user(
        1,
        {
            "name": "Updated Name",
            "is_active": False,
        },
    )

    assert user["user_id"] == 1
    assert user["name"] == "Updated Name"
    assert user["is_active"] is False


def test_update_user_not_found():
    with pytest.raises(Exception):
        user_service.update_user(
            999,
            {"name": "Unknown"},
        )


def test_delete_user():
    user_service.delete_user(1)

    with pytest.raises(Exception):
        user_service.get_user_by_id(1)


def test_delete_user_not_found():
    with pytest.raises(Exception):
        user_service.delete_user(999)
