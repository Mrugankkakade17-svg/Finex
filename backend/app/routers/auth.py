from typing import Optional

from fastapi import APIRouter, Body, Depends, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.core.responses import APIResponse
from app.schemas.auth import GoogleAuthRequest, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    summary="Register a new user",
    description=("Creates a new user account with name, email, and password. Returns JWT tokens."),
    status_code=200,
    responses={
        200: {
            "description": "Registration successful",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "access_token": "eyJ...",
                            "refresh_token": "eyJ...",
                            "token_type": "bearer",
                        },
                        "meta": {
                            "correlationId": "550e8400-e29b-41d4-a716-446655440005",
                            "apiVersion": "v1",
                            "dataAsOf": None,
                            "dataStatus": "LIVE",
                        },
                    },
                }
            },
        },
        400: {"description": "Email already registered"},
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Request validation failed.",
                            "fieldErrors": [
                                {
                                    "field": "email",
                                    "code": "INVALID_FORMAT",
                                }
                            ],
                            "correlationId": "550e8400-e29b-41d4-a716-446655440010",
                        }
                    }
                }
            },
        },
    },
)
def register(request: RegisterRequest, http_request: Request):
    """Register a new user and return access + refresh tokens."""
    result = auth_service.register(
        name=request.name,
        email=request.email,
        password=request.password,
    )
    return APIResponse.success(
        message="Registration successful",
        data=result,
        correlation_id=http_request.state.correlation_id,
    )


@router.post(
    "/login",
    summary="Login user",
    description=("Authenticates user with email and password. Returns JWT tokens."),
    status_code=200,
    responses={
        200: {
            "description": "Login successful",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "access_token": "eyJ...",
                            "refresh_token": "eyJ...",
                            "token_type": "bearer",
                        },
                        "meta": {
                            "correlationId": "550e8400-e29b-41d4-a716-446655440006",
                            "apiVersion": "v1",
                            "dataAsOf": None,
                            "dataStatus": "LIVE",
                        },
                    },
                }
            },
        },
        401: {"description": "Invalid credentials"},
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "message": "Request validation failed.",
                            "fieldErrors": [
                                {
                                    "field": "email",
                                    "code": "INVALID_FORMAT",
                                }
                            ],
                            "correlationId": "550e8400-e29b-41d4-a716-446655440011",
                        }
                    }
                }
            },
        },
    },
)
def login(request: LoginRequest, http_request: Request):
    """Authenticate user and return access + refresh tokens."""
    result = auth_service.login(
        email=request.email,
        password=request.password,
    )
    return APIResponse.success(
        message="Login successful",
        data=result,
        correlation_id=http_request.state.correlation_id,
    )


@router.get(
    "/me",
    summary="Get current user",
    description=("Returns the authenticated user's information from the JWT token."),
    status_code=200,
    responses={
        200: {
            "description": "User retrieved",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "sub": "user@email.com",
                            "user_id": 1,
                            "type": "access",
                        },
                        "meta": {
                            "correlationId": "550e8400-e29b-41d4-a716-446655440007",
                            "apiVersion": "v1",
                            "dataAsOf": None,
                            "dataStatus": "LIVE",
                        },
                    },
                }
            },
        },
        401: {"description": "Invalid or expired token"},
        403: {"description": "Authorization header missing"},
    },
)
def me(http_request: Request, user: dict = Depends(get_current_user)):
    """Get current authenticated user details."""
    return APIResponse.success(
        message="User retrieved",
        data=user,
        correlation_id=http_request.state.correlation_id,
    )


@router.post(
    "/refresh",
    summary="Refresh access token",
    description="Exchanges a valid refresh token for a new access token.",
    status_code=200,
    responses={
        200: {
            "description": "Token refreshed",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "access_token": "eyJ...",
                            "token_type": "bearer",
                        },
                        "meta": {
                            "correlationId": "550e8400-e29b-41d4-a716-446655440008",
                            "apiVersion": "v1",
                            "dataAsOf": None,
                            "dataStatus": "LIVE",
                        },
                    },
                }
            },
        },
        401: {"description": "Invalid refresh token"},
    },
)
def refresh(token: str, http_request: Request):
    """Exchange refresh token for a new access token."""
    result = auth_service.refresh(token=token)
    return APIResponse.success(
        message="Token refreshed",
        data=result,
        correlation_id=http_request.state.correlation_id,
    )


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post(
    "/logout",
    summary="Logout user",
    description="Revokes the refresh token and logs out the current user.",
    status_code=200,
    responses={
        200: {
            "description": "Logout successful",
            "content": {
                "application/json": {
                    "example": {
                        "data": None,
                        "meta": {
                            "correlationId": "550e8400-e29b-41d4-a716-446655440009",
                            "apiVersion": "v1",
                            "dataAsOf": None,
                            "dataStatus": "LIVE",
                        },
                    },
                }
            },
        },
        401: {"description": "Invalid or expired token"},
        403: {"description": "Authorization header missing"},
    },
)
def logout(
    http_request: Request,
    user: dict = Depends(get_current_user),
    body: Optional[LogoutRequest] = Body(default=None),
):
    """Logout user — revokes the provided refresh token."""
    auth_service.logout(refresh_token=body.refresh_token if body else None)
    return APIResponse.success(
        message="Logout successful",
        correlation_id=http_request.state.correlation_id,
    )


@router.post(
    "/google/callback",
    summary="Google OAuth callback",
    description=(
        "Verifies a Google identity token (or mock payload) and creates or loads "
        "the matching user. Returns JWT access + refresh tokens."
    ),
    status_code=200,
    responses={
        200: {
            "description": "Google login successful",
            "content": {
                "application/json": {
                    "example": {
                        "data": {
                            "access_token": "eyJ...",
                            "refresh_token": "eyJ...",
                            "token_type": "bearer",
                        },
                        "meta": {
                            "correlationId": "550e8400-e29b-41d4-a716-446655440012",
                            "apiVersion": "v1",
                            "dataAsOf": None,
                            "dataStatus": "LIVE",
                        },
                    }
                }
            },
        },
        400: {"description": "Missing or invalid Google identity payload"},
        401: {"description": "Google token verification failed"},
    },
)
def google_callback(request: GoogleAuthRequest, http_request: Request):
    """Verify Google identity and return JWT tokens (create user if first login)."""
    # Use id_token or credential field (MockGoogleVerifier understands mock: format)
    id_token = request.id_token or request.credential
    if id_token:
        result = auth_service.google_callback(id_token=id_token)
    else:
        # Fallback: direct mock fields via legacy google_auth_service path
        from app.services.google_auth_service import google_auth_service

        identity = google_auth_service.verify_google_identity(request)
        result = auth_service.login_or_create_google_user(
            google_id=identity["google_id"],
            email=identity["email"],
            name=identity["name"],
            avatar_url=identity.get("avatar_url"),
        )
    return APIResponse.success(
        message="Google login successful",
        data=result,
        correlation_id=http_request.state.correlation_id,
    )
