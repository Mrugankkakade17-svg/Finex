from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.core.responses import APIResponse
from app.repositories.user_repository import user_repository

router = APIRouter(prefix="/api/v1/users", tags=["Users"])


@router.get("/me", summary="Get my profile")
def get_me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's full profile."""
    db_user = user_repository.get_user_by_id(user["user_id"])
    if not db_user:
        raise NotFoundException(message="User not found", error_code="USER_NOT_FOUND")
    return APIResponse.success(
        message="Profile retrieved",
        data={
            "id": db_user.id,
            "email": db_user.email,
            "name": db_user.name,
            "is_active": db_user.is_active,
            "role": db_user.role,
        },
    )


@router.get("")
def get_users(user: dict = Depends(get_current_user)):
    users = user_repository.list_users()
    return APIResponse.success(
        message="Users retrieved",
        data=[{"id": u.id, "email": u.email, "name": u.name} for u in users],
    )


@router.get("/{user_id}")
def get_user(user_id: int, user: dict = Depends(get_current_user)):
    db_user = user_repository.get_user_by_id(user_id)
    if not db_user:
        raise NotFoundException(message="User not found", error_code="USER_NOT_FOUND")
    return APIResponse.success(
        message="User retrieved",
        data={"id": db_user.id, "email": db_user.email, "name": db_user.name},
    )
