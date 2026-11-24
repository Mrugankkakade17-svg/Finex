from datetime import datetime
from typing import Any, Optional

from app.models.user import UserModel


class UserRepository:
    """
    In-memory user repository.
    Exposes an interface that can later be replaced by Databricks.
    No FastAPI imports inside repository.
    """

    def __init__(self):
        self._users: dict[int, dict[str, Any]] = {}
        self._next_id: int = 1

    def _to_model(self, user: dict[str, Any]) -> UserModel:
        return UserModel(
            id=user["id"],
            name=user["name"],
            email=user["email"],
            hashed_password=user["hashed_password"],
            google_id=user.get("google_id"),
            picture=user.get("picture"),
            created_at=user["created_at"],
            updated_at=user["updated_at"],
            is_active=user["is_active"],
            role=user["role"],
            risk_profile=user["risk_profile"],
        )

    def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str,
        google_id: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> UserModel:
        now = datetime.utcnow()

        user: dict[str, Any] = {
            "id": self._next_id,
            "name": name,
            "email": email,
            "hashed_password": hashed_password,
            "google_id": google_id,
            "picture": picture,
            "created_at": now,
            "updated_at": now,
            "is_active": True,
            "role": "user",
            "risk_profile": None,
        }

        self._users[self._next_id] = user
        self._next_id += 1

        return self._to_model(user)

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        for user in self._users.values():
            if user["email"] == email:
                return self._to_model(user)

        return None

    def get_user_by_id(self, user_id: int) -> Optional[UserModel]:
        user = self._users.get(user_id)

        if user:
            return self._to_model(user)

        return None

    def get_or_create_google_user(
        self,
        google_id: str,
        email: str,
        name: str,
        picture: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> UserModel:
        """
        Find existing user by email and link google_id, or create a new OAuth user.
        Idempotent — calling twice with same google_id returns same user.
        Accepts both picture and avatar_url for flexibility.
        """
        pic = picture or avatar_url
        # Look for existing user by email
        for user in self._users.values():
            if user["email"] == email:
                # Link google_id and picture if not already set
                if not user.get("google_id"):
                    user["google_id"] = google_id
                    user["updated_at"] = datetime.utcnow()
                if pic and not user.get("picture"):
                    user["picture"] = pic
                return self._to_model(user)

        # No existing user — create a new OAuth user
        return self.create_user(
            name=name,
            email=email,
            hashed_password="",
            google_id=google_id,
            picture=pic,
        )

    def update_user(
        self,
        user_id: int,
        data: dict[str, Any],
    ) -> Optional[UserModel]:
        user = self._users.get(user_id)

        if not user:
            return None

        for key, value in data.items():
            if value is not None and key in user:
                user[key] = value

        user["updated_at"] = datetime.utcnow()

        return self._to_model(user)

    def get_profile(self, user_id: int) -> Optional[UserModel]:
        return self.get_user_by_id(user_id)

    def update_profile(
        self,
        user_id: int,
        data: dict[str, Any],
    ) -> Optional[UserModel]:
        allowed_fields = {"name", "email", "risk_profile"}

        profile_data = {
            key: value for key, value in data.items() if key in allowed_fields and value is not None
        }

        return self.update_user(user_id, profile_data)

    def delete_user(self, user_id: int) -> bool:
        if user_id in self._users:
            del self._users[user_id]
            return True

        return False

    def list_users(self) -> list[UserModel]:
        return [self._to_model(user) for user in self._users.values()]


# Singleton instance
user_repository = UserRepository()
