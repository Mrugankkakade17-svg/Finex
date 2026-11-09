from app.auth.password import hash_password
from app.core.exceptions import BadRequestException, NotFoundException

# In-memory mock data (replace with Databricks repository later)
fake_users: list = [
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

next_id = 3


def get_all_users() -> list:
    return [
        {
            "user_id": u["user_id"],
            "email": u["email"],
            "name": u["name"],
            "is_active": u["is_active"],
        }
        for u in fake_users
    ]


def get_user_by_id(user_id: int) -> dict:
    user = next((u for u in fake_users if u["user_id"] == user_id), None)

    if not user:
        raise NotFoundException(
            message="User not found",
            error_code="USER_NOT_FOUND",
        )

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "is_active": user["is_active"],
    }


def create_user(email: str, password: str, name: str) -> dict:
    global next_id

    if any(u["email"] == email for u in fake_users):
        raise BadRequestException(
            message="Email already exists",
            error_code="EMAIL_EXISTS",
        )

    new_user = {
        "user_id": next_id,
        "email": email,
        "name": name,
        "is_active": True,
        "password_hash": hash_password(password),
    }

    fake_users.append(new_user)
    next_id += 1

    return {
        "user_id": new_user["user_id"],
        "email": new_user["email"],
        "name": new_user["name"],
        "is_active": new_user["is_active"],
    }


def update_user(user_id: int, data: dict) -> dict:
    user = next((u for u in fake_users if u["user_id"] == user_id), None)

    if not user:
        raise NotFoundException(
            message="User not found",
            error_code="USER_NOT_FOUND",
        )

    for key, value in data.items():
        if value is not None and key in user:
            user[key] = value

    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "name": user["name"],
        "is_active": user["is_active"],
    }


def delete_user(user_id: int) -> None:
    global fake_users

    user = next((u for u in fake_users if u["user_id"] == user_id), None)

    if not user:
        raise NotFoundException(
            message="User not found",
            error_code="USER_NOT_FOUND",
        )

    fake_users = [u for u in fake_users if u["user_id"] != user_id]
