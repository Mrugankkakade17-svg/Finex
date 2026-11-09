from pydantic import BaseModel


class GoogleCallbackRequest(BaseModel):
    """Request body for POST /api/v1/auth/google/callback."""

    id_token: str


class LogoutRequest(BaseModel):
    """Request body for POST /api/v1/auth/logout.

    Requires refresh token to revoke it server-side.
    """

    refresh_token: str
