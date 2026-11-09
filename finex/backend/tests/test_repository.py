from app.repositories.user_repository import UserRepository


def test_create_user():
    repo = UserRepository()

    user = repo.create_user(
        name="Test",
        email="test@finex.com",
        hashed_password="hashed123",
    )

    assert user.id == 1
    assert user.name == "Test"
    assert user.email == "test@finex.com"


def test_find_user_by_email():
    repo = UserRepository()

    repo.create_user(
        name="Find Me",
        email="find@finex.com",
        hashed_password="hashed",
    )

    found = repo.get_user_by_email("find@finex.com")

    assert found is not None
    assert found.name == "Find Me"


def test_find_user_not_found():
    repo = UserRepository()

    found = repo.get_user_by_email("nobody@finex.com")

    assert found is None


def test_find_user_by_id():
    repo = UserRepository()

    user = repo.create_user(
        name="Find By ID",
        email="id@finex.com",
        hashed_password="hashed",
    )

    found = repo.get_user_by_id(user.id)

    assert found is not None
    assert found.id == user.id
    assert found.name == "Find By ID"


def test_find_user_by_id_not_found():
    repo = UserRepository()

    found = repo.get_user_by_id(999)

    assert found is None


def test_update_user():
    repo = UserRepository()

    user = repo.create_user(
        name="Original",
        email="update@finex.com",
        hashed_password="hashed",
    )

    updated = repo.update_user(
        user.id,
        {
            "name": "Updated",
            "email": "updated@finex.com",
        },
    )

    assert updated is not None
    assert updated.name == "Updated"
    assert updated.email == "updated@finex.com"


def test_update_user_not_found():
    repo = UserRepository()

    result = repo.update_user(
        999,
        {"name": "Unknown"},
    )

    assert result is None


def test_list_users():
    repo = UserRepository()

    repo.create_user(
        name="User One",
        email="one@finex.com",
        hashed_password="hash1",
    )
    repo.create_user(
        name="User Two",
        email="two@finex.com",
        hashed_password="hash2",
    )

    users = repo.list_users()

    assert len(users) == 2
    assert users[0].name == "User One"
    assert users[1].name == "User Two"


def test_duplicate_user():
    repo = UserRepository()

    repo.create_user(
        name="User1",
        email="dup@finex.com",
        hashed_password="hash1",
    )
    repo.create_user(
        name="User2",
        email="dup@finex.com",
        hashed_password="hash2",
    )

    users = repo.list_users()
    emails = [user.email for user in users]

    assert emails.count("dup@finex.com") == 2


def test_delete_user():
    repo = UserRepository()

    user = repo.create_user(
        name="Delete Me",
        email="delete@finex.com",
        hashed_password="hash",
    )

    result = repo.delete_user(user.id)

    assert result is True
    assert repo.get_user_by_id(user.id) is None


def test_delete_user_not_found():
    repo = UserRepository()

    result = repo.delete_user(999)

    assert result is False
