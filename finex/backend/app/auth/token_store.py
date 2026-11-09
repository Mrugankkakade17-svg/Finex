"""
In-memory refresh token revocation store.

Stores revoked JTI (JWT ID) values. A token whose JTI is in this store
is treated as invalid regardless of its expiry time.

This is consistent with the rest of S1's in-memory data layer and is
designed to be swapped for a Redis/database store in production.
"""

import threading
from typing import Set


class TokenRevocationStore:
    """
    Thread-safe in-memory store for revoked JWT IDs (jti claims).

    On logout the refresh token's jti is added here.
    On every refresh or protected-route access the jti is checked here.
    """

    def __init__(self) -> None:
        self._revoked: Set[str] = set()
        self._lock = threading.Lock()

    def revoke(self, jti: str) -> None:
        """Mark a token as revoked by its JTI."""
        with self._lock:
            self._revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        """Return True if the token JTI has been revoked."""
        with self._lock:
            return jti in self._revoked

    def clear(self) -> None:
        """Clear all revoked tokens — for testing only."""
        with self._lock:
            self._revoked.clear()


# Singleton instance used across the application
token_revocation_store = TokenRevocationStore()
