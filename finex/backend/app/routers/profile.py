from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.core.responses import APIResponse
from app.schemas.profile import ProfileUpdateRequest
from app.services import profile_service

router = APIRouter(
    prefix="/api/v1/users/me",
    tags=["Profile"],
)


@router.get("/profile")
def get_profile(
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]

    result = profile_service.get_profile(user_id)

    return APIResponse.success(
        message="Profile retrieved successfully",
        data=result,
        correlation_id=request.state.correlation_id,
    )


@router.put("/profile")
def update_profile(
    request: Request,
    profile: ProfileUpdateRequest,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]

    result = profile_service.update_profile(
        user_id=user_id,
        data=profile.model_dump(exclude_none=True),
    )

    return APIResponse.success(
        message="Profile updated successfully",
        data=result,
        correlation_id=request.state.correlation_id,
    )
