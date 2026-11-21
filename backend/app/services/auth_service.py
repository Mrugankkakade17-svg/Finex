"""Authentication service supporting PostgreSQL persistence, bcrypt, and rate limiting (S1-LI02)."""

import threading
import time
from typing import Any

from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.auth.token_store import token_revocation_store
from app.config.logging import logger
from app.core.exceptions import (
    BadRequestException,
    LoginRateLimitExceededException,
    UnauthorizedException,
)
from app.ports.adapters.mock_google_verifier import mock_google_verifier
from app.repositories.postgres_user_repository import (
    postgres_user_repository,
)


class LoginAttemptTracker:
    """Thread-safe in-memory tracker for consecutive failed login attempts."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def is_throttled(self, key: str) -> bool:
        """Check if the key has reached or exceeded max allowed failed attempts in the window."""
        now = time.time()
        with self._lock:
            attempts = self._attempts.get(key, [])
            attempts = [t for t in attempts if now - t < self.window_seconds]
            self._attempts[key] = attempts
            return len(attempts) >= self.max_attempts

    def record_failed_attempt(self, key: str) -> int:
        """Record a failed login timestamp and return current attempt count in window."""
        now = time.time()
        with self._lock:
            attempts = self._attempts.get(key, [])
            attempts = [t for t in attempts if now - t < self.window_seconds]
            attempts.append(now)
            self._attempts[key] = attempts
            return len(attempts)

    def reset(self, key: str) -> None:
        """Clear failed attempt records for a key upon successful login."""
        with self._lock:
            self._attempts.pop(key, None)

    def clear(self) -> None:
        """Reset all tracked state (for test isolation)."""
        with self._lock:
            self._attempts.clear()


login_tracker = LoginAttemptTracker(max_attempts=10, window_seconds=900)
user_repository: Any = postgres_user_repository


def register(name: str, email: str, password: str) -> dict:
    """Validate duplicate email, hash password with bcrypt, and persist user.

    Never logs plaintext passwords or password hashes.
    """
    normalized_email = email.strip().lower()

    existing = user_repository.get_user_by_email(normalized_email)
    if existing:
        logger.warning("Registration rejected: email already registered")
        raise BadRequestException(
            message="Email already registered",
            error_code="EMAIL_EXISTS",
        )

    hashed = hash_password(password)
    user = user_repository.create_user(name=name, email=normalized_email, hashed_password=hashed)

    user_id_str = str(getattr(user, "id", None) or getattr(user, "user_id", ""))
    access_token = create_access_token(data={"sub": user.email, "user_id": user_id_str})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user_id_str})

    logger.info("User registered successfully user_id=%s", user_id_str)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


def login(email: str, password: str) -> dict:
    """Authenticate user with email and password, enforcing failed login throttling.

    Throttles on the 11th failed attempt within the active window.
    Resets failed attempt count on successful authentication.
    Never logs plaintext passwords, hashes, or tokens.
    """
    normalized_email = email.strip().lower()

    if login_tracker.is_throttled(normalized_email):
        logger.warning("Login throttled: rate limit exceeded")
        raise LoginRateLimitExceededException(
            message="Too many failed login attempts. Please try again later.",
            retry_after_seconds=login_tracker.window_seconds,
        )

    user = user_repository.get_user_by_email(normalized_email)
    stored_hash = getattr(user, "hashed_password", None) or getattr(user, "password_hash", None)

    if not user or not stored_hash or not verify_password(password, stored_hash):
        count = login_tracker.record_failed_attempt(normalized_email)
        logger.warning("Invalid credentials attempt=%d", count)
        raise UnauthorizedException(
            message="Invalid email or password",
            error_code="INVALID_CREDENTIALS",
        )

    # Successful login: reset failed attempt tracker
    login_tracker.reset(normalized_email)

    if hasattr(user_repository, "update_user_login"):
        user_repository.update_user_login(user.id)

    user_id_str = str(getattr(user, "id", None) or getattr(user, "user_id", ""))
    access_token = create_access_token(data={"sub": user.email, "user_id": user_id_str})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user_id_str})

    logger.info("User login successful user_id=%s", user_id_str)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


def get_current_user(token: str) -> dict:
    """Decode access token and return payload."""
    payload = decode_token(token)

    if payload is None:
        raise UnauthorizedException(
            message="Invalid or expired token",
            error_code="INVALID_TOKEN",
        )

    if payload.get("type") != "access":
        raise UnauthorizedException(
            message="Invalid token type",
            error_code="INVALID_TOKEN_TYPE",
        )

    return payload


def refresh(token: str) -> dict:
    """Validate refresh token and issue new access token."""
    payload = decode_token(token)

    if payload is None or payload.get("type") != "refresh":
        raise UnauthorizedException(
            message="Invalid refresh token",
            error_code="INVALID_REFRESH_TOKEN",
        )

    jti = payload.get("jti")
    if jti and token_revocation_store.is_revoked(jti):
        raise UnauthorizedException(
            message="Token has been revoked",
            error_code="TOKEN_REVOKED",
        )

    new_access_token = create_access_token(
        data={"sub": payload["sub"], "user_id": payload.get("user_id")}
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
    }


def logout(refresh_token: str | None = None) -> dict:
    """Revoke refresh token by JTI on logout."""
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload is None:
            return {}
        if payload.get("type") != "refresh":
            raise UnauthorizedException(
                message="Expected a refresh token, not an access token",
                error_code="INVALID_TOKEN_TYPE",
            )
        jti = payload.get("jti")
        if jti:
            token_revocation_store.revoke(jti)
    return {}


def login_or_create_google_user(
    google_id: str, email: str, name: str, avatar_url: str | None = None
) -> dict:
    """Find existing user by email or create new OAuth user."""
    normalized_email = email.strip().lower()
    user = user_repository.get_user_by_email(normalized_email)

    if not user:
        user = user_repository.create_user(
            name=name,
            email=normalized_email,
            hashed_password="",
        )

    user_id_str = str(getattr(user, "id", None) or getattr(user, "user_id", ""))
    access_token = create_access_token(data={"sub": user.email, "user_id": user_id_str})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": user_id_str})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }


def google_callback(id_token: str, google_verifier=None) -> dict:
    """Verify Google token and return session."""
    verifier = google_verifier or mock_google_verifier
    identity = verifier.verify_google_token(id_token)
    return login_or_create_google_user(
        google_id=identity.google_id,
        email=str(identity.email),
        name=identity.name,
        avatar_url=identity.picture,
    )
