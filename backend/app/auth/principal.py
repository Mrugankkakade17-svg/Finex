"""Current principal dependency for local bearer and real JWT sessions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, status

from app.auth.jwt_handler import decode_token
from app.auth.token_store import token_revocation_store
from app.services.local_authorization import digest_token


@dataclass(frozen=True)
class Principal:
    """Authenticated user principal."""

    user_id: str
    is_synthetic: bool = False
    roles: list[str] = field(default_factory=lambda: ["user"])

    def __getitem__(self, item: str) -> Any:
        if hasattr(self, item):
            return getattr(self, item)
        raise KeyError(item)

    def get(self, item: str, default: Any = None) -> Any:
        return getattr(self, item, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "is_synthetic": self.is_synthetic,
            "roles": list(self.roles),
        }


def _extract_token(request: Request, explicit_token: Optional[str] = None) -> str:
    """Extract bearer token from argument or Authorization header.

    Raises HTTP 401 if missing, invalid format, or empty.
    """
    if explicit_token is not None:
        token = explicit_token.strip()
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or empty token",
            )
        return token

    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing",
        )

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format; expected Bearer token",
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is empty",
        )
    return token


def _resolve_jwt(token: str) -> Principal:
    """Resolve a real JWT access token into a Principal."""
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type; expected access token",
        )

    jti = payload.get("jti")
    if jti and token_revocation_store.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
        )

    user_id = str(payload.get("user_id") or payload.get("sub") or "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identifier",
        )

    raw_roles = payload.get("roles")
    if isinstance(raw_roles, list):
        roles = [str(r) for r in raw_roles]
    elif isinstance(raw_roles, str):
        roles = [raw_roles]
    elif "role" in payload:
        roles = [str(payload["role"])]
    else:
        roles = ["user"]

    return Principal(
        user_id=user_id,
        is_synthetic=False,
        roles=roles,
    )


def _resolve_local_session(request: Request, token: str) -> Principal:
    """Resolve a local educational bearer session into a Principal."""
    # Validate local token format (43-char urlsafe base64)
    if len(token) != 43 or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid local session token format",
        )

    app_state = getattr(request, "app", None)
    state = getattr(app_state, "state", None) if app_state else None

    # 1. Check if local_application_service is already initialized
    service = getattr(state, "local_application_service", None) if state else None
    if service is not None:
        try:
            with service.authorized_transaction(token) as (session, _):
                return Principal(
                    user_id=session.user.id,
                    is_synthetic=True,
                    roles=["user", "learner"],
                )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired local session",
            ) from exc

    # 2. Check if local_application_store exists in state or fallback to SQLite store
    store = getattr(state, "local_application_store", None) if state else None
    clock = getattr(state, "local_clock", None) if state else None

    if store is None:
        from app.adapters.sqlite_local_application_store import SQLiteLocalApplicationStore
        from app.config.settings import get_settings

        settings = getattr(state, "settings", None) if state else None
        if settings is None:
            settings = get_settings()
        store = SQLiteLocalApplicationStore(settings.local_db_path)

    # Query session from store transaction
    try:
        with store.transaction(write=False) as transaction:
            session = transaction.get_session(digest_token(token))
            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found or invalid",
                )

            if session.revoked_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked",
                )

            now = clock() if clock is not None else datetime.now(timezone.utc)
            if session.expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has expired",
                )

            return Principal(
                user_id=session.user.id,
                is_synthetic=True,
                roles=["user", "learner"],
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired local session",
        ) from exc


async def get_principal(
    request: Request,
    token: Optional[str] = None,
) -> Principal:
    """Resolve the authenticated Principal from local bearer or real JWT sessions."""
    raw_token = _extract_token(request, token)

    # Route based on token format:
    # JWT tokens have 3 parts separated by dots ('header.payload.signature')
    if raw_token.count(".") == 2:
        return _resolve_jwt(raw_token)

    # Otherwise, treat as local educational session token
    return _resolve_local_session(request, raw_token)


async def get_current_principal(
    request: Request,
) -> Principal:
    """FastAPI dependency to retrieve the current authenticated principal."""
    return await get_principal(request)


CurrentPrincipal = Depends(get_current_principal)


async def require_admin_role(
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    """Validate that the authenticated principal possesses the admin role.

    Raises HTTP 403 Forbidden if the principal lacks the admin role.
    """
    if "admin" not in principal.roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin role required",
        )
    return principal


RequireAdmin = Depends(require_admin_role)
