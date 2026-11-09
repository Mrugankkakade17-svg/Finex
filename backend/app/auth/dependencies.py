from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.jwt_handler import decode_token
from app.auth.security import security_scheme
from app.auth.token_store import token_revocation_store
from app.core.exceptions import AuthenticationException


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> dict:
    """
    Read Authorization Header.
    Verify JWT.
    Check revocation store (token invalidated by logout).
    Return authenticated user.
    Raise AuthenticationException if invalid.
    """
    if credentials is None:
        raise AuthenticationException(
            message="Authorization header missing",
            error_code="AUTH_HEADER_MISSING",
        )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise AuthenticationException(
            message="Invalid or expired token",
            error_code="INVALID_TOKEN",
        )

    if payload.get("type") != "access":
        raise AuthenticationException(
            message="Invalid token type",
            error_code="INVALID_TOKEN_TYPE",
        )

    jti = payload.get("jti")
    if jti and token_revocation_store.is_revoked(jti):
        raise AuthenticationException(
            message="Token has been revoked",
            error_code="TOKEN_REVOKED",
        )

    return payload
