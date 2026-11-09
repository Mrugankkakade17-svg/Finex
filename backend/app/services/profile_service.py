from app.core.exceptions import NotFoundException
from app.repositories.user_repository import user_repository


def get_profile(user_id: int) -> dict:
    user = user_repository.get_profile(user_id)

    if user is None:
        raise NotFoundException(
            message="User profile not found",
            error_code="PROFILE_NOT_FOUND",
        )

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "risk_profile": user.risk_profile,
    }


def update_profile(user_id: int, data: dict) -> dict:
    user = user_repository.update_profile(user_id, data)

    if user is None:
        raise NotFoundException(
            message="User profile not found",
            error_code="PROFILE_NOT_FOUND",
        )

    return {
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "risk_profile": user.risk_profile,
    }
