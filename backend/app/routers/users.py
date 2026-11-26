from typing import Any, Optional, Union

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.core.exceptions import NotFoundException
from app.core.responses import APIResponse
from app.services.auth_service import get_user_repository

router = APIRouter(prefix="/api/v1/users", tags=["Users"])

# Backward-compatible attribute for tests monkeypatching app.routers.users.user_repository
user_repository: Any = None


def _get_repo() -> Any:
    if user_repository is not None:
        return user_repository
    return get_user_repository()


def _find_user(repo: Any, raw_uid: Optional[Union[str, int]]) -> Any:
    if raw_uid is None:
        return None
    user = repo.get_user_by_id(raw_uid)
    if user:
        return user
    uid_str = str(raw_uid)
    if uid_str.isdigit():
        user = repo.get_user_by_id(int(uid_str))
        if user:
            return user
    return repo.get_user_by_id(uid_str)


@router.get("/me", summary="Get my profile")
def get_me(user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's full profile."""
    repo = _get_repo()
    db_user = _find_user(repo, user.get("user_id"))
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
    repo = _get_repo()
    current = _find_user(repo, user.get("user_id"))
    users = [current] if current else []
    return APIResponse.success(
        message="Users retrieved",
        data=[{"id": u.id, "email": u.email, "name": u.name} for u in users],
    )


@router.get("/{user_id}")
def get_user(user_id: str, user: dict = Depends(get_current_user)):
    repo = _get_repo()
    req_uid = str(user_id)
    token_uid = str(user.get("user_id", ""))
    if req_uid != token_uid:
        raise NotFoundException(message="User not found", error_code="USER_NOT_FOUND")
    db_user = _find_user(repo, user_id)
    if not db_user:
        raise NotFoundException(message="User not found", error_code="USER_NOT_FOUND")
    return APIResponse.success(
        message="User retrieved",
        data={"id": db_user.id, "email": db_user.email, "name": db_user.name},
    )
