from datetime import datetime
from typing import Any, Dict, Optional, Set


class TokenRepository:
    """
    Repository for managing refresh tokens and token revocation.
    In-memory storage designed with an interface that can be backed by Redis or Lakebase.
    """

    def __init__(self):
        # Map: token_jti -> {"user_id": int, "expires_at": datetime, "revoked": bool}
        self._refresh_tokens: Dict[str, Dict[str, Any]] = {}
        # Set of explicitly revoked token identifiers (access token or refresh token JTIs)
        self._revoked_jtis: Set[str] = set()

    def store_refresh_token(
        self,
        user_id: int,
        token_jti: str,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """Store an active refresh token with its JTI."""
        self._refresh_tokens[token_jti] = {
            "user_id": user_id,
            "expires_at": expires_at,
            "revoked": False,
            "created_at": datetime.utcnow(),
        }

    def revoke_token(self, token_jti: str) -> bool:
        """Mark a token (by JTI) as revoked."""
        if not token_jti:
            return False

        self._revoked_jtis.add(token_jti)
        if token_jti in self._refresh_tokens:
            self._refresh_tokens[token_jti]["revoked"] = True
            return True
        return True

    def revoke_user_tokens(self, user_id: int) -> int:
        """Revoke all active refresh tokens for a given user."""
        count = 0
        for jti, info in self._refresh_tokens.items():
            if info["user_id"] == user_id and not info["revoked"]:
                info["revoked"] = True
                self._revoked_jtis.add(jti)
                count += 1
        return count

    def is_token_revoked(self, token_jti: str) -> bool:
        """Check if a token JTI is in the revocation list."""
        if not token_jti:
            return False
        if token_jti in self._revoked_jtis:
            return True
        token_info = self._refresh_tokens.get(token_jti)
        if token_info and token_info.get("revoked", False):
            return True
        return False

    def is_refresh_token_valid(self, token_jti: str) -> bool:
        """Check if a refresh token JTI exists, is not revoked, and is not expired."""
        if not token_jti or self.is_token_revoked(token_jti):
            return False

        token_info = self._refresh_tokens.get(token_jti)
        if not token_info:
            # If the token was not tracked, but also not revoked, we check if revoked
            return False

        if token_info.get("revoked", False):
            return False

        expires_at = token_info.get("expires_at")
        if expires_at and expires_at < datetime.utcnow():
            return False

        return True

    def clear(self) -> None:
        """Reset state (useful for tests)."""
        self._refresh_tokens.clear()
        self._revoked_jtis.clear()


# Singleton instance
token_repository = TokenRepository()
