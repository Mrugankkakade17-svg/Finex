"""
User schemas for authentication and JWT payloads.
"""

from typing import Optional

from pydantic import BaseModel


class CurrentUser(BaseModel):
    """Schema for the authenticated user returned by get_current_user dependency.

    This represents the JWT payload structure and is used for type hinting
    in FastAPI route handlers.
    """

    sub: str  # Subject (user email or identifier)
    user_id: int  # User database ID
    type: str  # Token type: 'access' or 'refresh'
    jti: Optional[str] = None  # JWT ID for revocation tracking
    iat: Optional[int] = None  # Issued at
    exp: Optional[int] = None  # Expiration

    class Config:
        # Allow dict-to-model conversion from JWT payload
        extra = "allow"
