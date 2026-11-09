from fastapi import APIRouter, Request

from app.config.settings import get_settings
from app.core.responses import APIResponse

router = APIRouter(prefix="/api/v1", tags=["Health"])

settings = get_settings()


@router.get("/health")
def health_check(request: Request):

    data = {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }

    return APIResponse.success(
        message="Backend is healthy",
        data=data,
        correlation_id=request.state.correlation_id,
    )


@router.get("/health/live")
def liveness_check(request: Request):
    return APIResponse.success(
        message="Service is alive",
        data={"status": "healthy"},
        correlation_id=request.state.correlation_id,
    )


@router.get("/health/ready")
def readiness_check(request: Request):
    return APIResponse.success(
        message="Service is ready",
        data={"status": "healthy"},
        correlation_id=request.state.correlation_id,
    )
