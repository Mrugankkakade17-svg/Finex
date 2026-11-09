from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationException


class BearerTokenScheme(HTTPBearer):
    """
    Custom bearer token scheme.

    Missing Authorization header -> 403
    Invalid authentication scheme -> 401
    Invalid authorization format -> 401
    Empty token -> 401
    """

    async def __call__(
        self,
        request: Request,
    ) -> HTTPAuthorizationCredentials | None:
        authorization = request.headers.get("Authorization")

        # Missing Authorization header
        if not authorization:
            raise HTTPException(
                status_code=403,
                detail="Authorization header missing",
            )

        # Split Authorization header
        parts = authorization.split()

        # Invalid format, for example:
        # "Bearer"
        # "Bearer token extra"
        if len(parts) != 2:
            raise HTTPException(
                status_code=401,
                detail="Invalid authorization format",
            )

        scheme, token = parts

        # Authorization scheme must be Bearer
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication scheme",
            )

        # Token cannot be empty
        if not token:
            raise HTTPException(
                status_code=401,
                detail="Token is empty",
            )

        return HTTPAuthorizationCredentials(
            scheme=scheme,
            credentials=token,
        )


# Reusable security scheme instance
security_scheme = BearerTokenScheme()


def extract_token(authorization: str) -> str:
    """Extract token from Authorization header string."""
    if not authorization:
        raise AuthenticationException(
            message="Authorization header missing",
        )

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationException(
            message="Invalid authorization format",
        )

    return parts[1]
