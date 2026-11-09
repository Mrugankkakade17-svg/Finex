from typing import Any, Dict, Optional

from pydantic import BaseModel, EmailStr, Field

# Request Models


class RegisterRequest(BaseModel):
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Full Name",
    )
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=64,
        description="Password",
    )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleAuthRequest(BaseModel):
    """Request body for POST /api/v1/auth/google/callback.
    Supports mock identity, mock_payload dict, or JWT credential/id_token.
    """

    # Option 1: Direct mock identity fields
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    google_id: Optional[str] = None
    picture: Optional[str] = None

    # Option 2: Nested mock payload dict
    mock_payload: Optional[Dict[str, Any]] = None

    # Option 3: JWT token string
    credential: Optional[str] = None
    id_token: Optional[str] = None


# Response Models


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
