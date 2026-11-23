"""Authentication service supporting PostgreSQL persistence, bcrypt, and rate limiting (S1-LI02)."""

import os
import threading
import time
from typing import Any, Optional

from app.auth.jwt_handler import create_access_token, create_refresh_token, decode_token
from app.auth.password import hash_password, verify_password
from app.auth.token_store import token_revocation_store
from app.config.logging import logger
from app.config.settings import get_settings
from app.core.exceptions import (
    BadRequestException,
    LoginRateLimitExceededException,
    UnauthorizedException,
)
from app.ports.adapters.mock_google_verifier import mock_google_verifier
from app.repositories.postgres_user_repository import (
    postgres_user_repository,
)
from app.repositories.user_repository import user_repository as default_user_repo


def _resolve_initial_user_repository() -> Any:
    persistence = os.getenv("APP_PERSISTENCE", "").strip().lower()
    if persistence == "postgresql":
        return postgres_user_repository
    try:
        if get_settings().app_persistence == "postgresql":
            return postgres_user_repository
    except Exception:
        pass
    return default_user_repo


# Default user repository follows APP_PERSISTENCE (sqlite by default);
# tests may monkeypatch user_repository
user_repository: Any = _resolve_initial_user_repository()


def get_user_repository() -> Any:
    """Resolve the active user repository based on configuration and overrides."""
    if user_repository is not default_user_repo:
        return user_repository
    persistence = os.getenv("APP_PERSISTENCE", "").strip().lower()
    if persistence == "postgresql":
        return postgres_user_repository
    try:
        if get_settings().app_persistence == "postgresql":
            return postgres_user_repository
    except Exception:
        pass
    return user_repository


class PostgresKeyLock:
    """Context manager acquiring both a local threading lock and a PostgreSQL advisory lock.

    Provides multi-worker safety across independent process instances.
    """

    def __init__(self, key: str, repo: Any, local_lock: threading.Lock) -> None:
        self.key = key
        self.repo = repo
        self.local_lock = local_lock
        self._conn: Optional[Any] = None

    def __enter__(self) -> "PostgresKeyLock":
        self.local_lock.acquire()
        if (
            hasattr(self.repo, "is_postgres_mode")
            and self.repo.is_postgres_mode()
            and self.repo.is_db_available()
        ):
            try:
                self._conn = self.repo._get_sync_conn(autocommit=True)
                with self._conn.cursor() as cur:
                    cur.execute("SET lock_timeout = '10s'")
                    cur.execute(
                        "SELECT pg_advisory_lock(hashtext(%(key)s))",
                        {"key": self.key},
                    )
            except Exception as e:
                logger.warning("Failed to acquire PostgreSQL advisory lock: %s", e)
                if self._conn:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
                    self._conn = None
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if self._conn:
                try:
                    with self._conn.cursor() as cur:
                        cur.execute(
                            "SELECT pg_advisory_unlock(hashtext(%(key)s))",
                            {"key": self.key},
                        )
                except Exception:
                    pass
                finally:
                    try:
                        self._conn.close()
                    except Exception:
                        pass
        finally:
            self.local_lock.release()


class LoginAttemptTracker:
    """Thread-safe and multi-worker PostgreSQL tracker for consecutive failed login attempts."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._key_locks: dict[str, threading.Lock] = {}

    def get_lock(self, key: str) -> Any:
        """Return a lock context manager (thread lock + PostgreSQL advisory lock)."""
        norm_key = key.strip().lower()
        repo = get_user_repository()
        with self._lock:
            if norm_key not in self._key_locks:
                self._key_locks[norm_key] = threading.Lock()
            thread_lock = self._key_locks[norm_key]
        return PostgresKeyLock(norm_key, repo, thread_lock)

    def is_throttled(self, key: str) -> bool:
        """Check if the key has reached or exceeded max allowed failed attempts in the window."""
        norm_key = key.strip().lower()
        repo = get_user_repository()
        if hasattr(repo, "is_postgres_mode") and repo.is_postgres_mode() and repo.is_db_available():
            try:
                with repo._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT failed_count,
                                   EXTRACT(EPOCH FROM (NOW() - first_attempt_at)) AS elapsed
                            FROM finex.failed_logins
                            WHERE email = %(email)s
                            """,
                            {"email": norm_key},
                        )
                        row = cur.fetchone()
                        if not row:
                            return False
                        elapsed = float(row["elapsed"] or 0)
                        if elapsed >= self.window_seconds:
                            cur.execute(
                                "DELETE FROM finex.failed_logins WHERE email = %(email)s",
                                {"email": norm_key},
                            )
                            conn.commit()
                            return False
                        return int(row["failed_count"]) >= self.max_attempts
            except Exception as e:
                logger.warning("Postgres failed-login check failed, using memory fallback: %s", e)

        # In-memory check (for SQLite or non-Postgres mode)
        now = time.time()
        with self._lock:
            attempts = self._attempts.get(norm_key, [])
            attempts = [t for t in attempts if now - t < self.window_seconds]
            self._attempts[norm_key] = attempts
            return len(attempts) >= self.max_attempts

    def record_failed_attempt(self, key: str) -> int:
        """Record a failed login timestamp and return current attempt count in window."""
        norm_key = key.strip().lower()
        repo = get_user_repository()
        if hasattr(repo, "is_postgres_mode") and repo.is_postgres_mode() and repo.is_db_available():
            try:
                with repo._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO finex.failed_logins (
                                email, failed_count, first_attempt_at, last_attempt_at
                            )
                            VALUES (%(email)s, 1, NOW(), NOW())
                            ON CONFLICT (email) DO UPDATE
                            SET failed_count = CASE
                                    WHEN EXTRACT(
                                        EPOCH FROM (NOW() - finex.failed_logins.first_attempt_at)
                                    ) >= %(window)s THEN 1
                                    ELSE finex.failed_logins.failed_count + 1
                                END,
                                first_attempt_at = CASE
                                    WHEN EXTRACT(
                                        EPOCH FROM (NOW() - finex.failed_logins.first_attempt_at)
                                    ) >= %(window)s THEN NOW()
                                    ELSE finex.failed_logins.first_attempt_at
                                END,
                                last_attempt_at = NOW()
                            RETURNING failed_count
                            """,
                            {"email": norm_key, "window": self.window_seconds},
                        )
                        row = cur.fetchone()
                        conn.commit()
                        if row:
                            count = int(row["failed_count"])
                            with self._lock:
                                self._attempts.setdefault(norm_key, []).append(time.time())
                            return count
            except Exception as e:
                logger.warning(
                    "Postgres record failed attempt failed, using memory fallback: %s", e
                )

        # In-memory fallback
        now = time.time()
        with self._lock:
            attempts = self._attempts.get(norm_key, [])
            attempts = [t for t in attempts if now - t < self.window_seconds]
            attempts.append(now)
            self._attempts[norm_key] = attempts
            return len(attempts)

    def reset(self, key: str) -> None:
        """Clear failed attempt records for a key upon successful login."""
        norm_key = key.strip().lower()
        repo = get_user_repository()
        if hasattr(repo, "is_postgres_mode") and repo.is_postgres_mode() and repo.is_db_available():
            try:
                with repo._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "DELETE FROM finex.failed_logins WHERE email = %(email)s",
                            {"email": norm_key},
                        )
                        conn.commit()
            except Exception as e:
                logger.warning("Postgres failed-login reset failed: %s", e)
        with self._lock:
            self._attempts.pop(norm_key, None)

    def clear(self) -> None:
        """Reset all tracked state (for test isolation)."""
        repo = get_user_repository()
        if hasattr(repo, "is_postgres_mode") and repo.is_postgres_mode() and repo.is_db_available():
            try:
                with repo._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("DELETE FROM finex.failed_logins")
                        conn.commit()
            except Exception:
                pass
        with self._lock:
            self._attempts.clear()
            self._key_locks.clear()


login_tracker = LoginAttemptTracker(max_attempts=10, window_seconds=900)


def register(name: str, email: str, password: str) -> dict:
    """Validate duplicate email, hash password with bcrypt, and persist user.

    Never logs plaintext passwords or password hashes.
    """
    normalized_email = email.strip().lower()
    repo = get_user_repository()

    existing = repo.get_user_by_email(normalized_email)
    if existing:
        logger.warning("Registration rejected: email already registered")
        raise BadRequestException(
            message="Email already registered",
            error_code="EMAIL_EXISTS",
        )

    hashed = hash_password(password)

    user = repo.create_user(name=name, email=normalized_email, hashed_password=hashed)

    if repo is not default_user_repo and hasattr(default_user_repo, "_users"):
        try:
            rec = {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "hashed_password": hashed,
                "google_id": user.google_id,
                "picture": user.picture,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "is_active": user.is_active,
                "role": user.role,
                "risk_profile": user.risk_profile,
            }
            if hasattr(user, "id") and user.id is not None and str(user.id).isdigit():
                default_user_repo._users[int(str(user.id))] = rec
        except Exception:
            pass

    uid: Any
    if isinstance(user.id, int):
        uid = user.id
    elif user.id is not None and str(user.id).isdigit():
        uid = int(str(user.id))
    else:
        uid = user.id or ""

    access_token = create_access_token(data={"sub": user.email, "user_id": uid})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": uid})

    logger.info("User registered successfully user_id=%s", uid)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {"id": uid, "email": user.email, "name": user.name},
    }


def login(email: str, password: str) -> dict:
    """Authenticate user with email and password, enforcing failed login throttling.

    Throttles on the 11th failed attempt within the active window.
    Resets failed attempt count on successful authentication.
    Never logs plaintext passwords, hashes, or tokens.
    """
    normalized_email = email.strip().lower()

    with login_tracker.get_lock(normalized_email):
        if login_tracker.is_throttled(normalized_email):
            logger.warning("Login throttled: rate limit exceeded")
            raise LoginRateLimitExceededException(
                message="Too many failed login attempts. Please try again later.",
                retry_after_seconds=login_tracker.window_seconds,
            )

        repo = get_user_repository()
        user = repo.get_user_by_email(normalized_email)
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

        if hasattr(repo, "update_user_login") and user.id is not None:
            repo.update_user_login(user.id)

        uid: Any
        if isinstance(user.id, int):
            uid = user.id
        elif user.id is not None and str(user.id).isdigit():
            uid = int(str(user.id))
        else:
            uid = user.id or ""

        # Ensure in-memory repo has the record if uid is int
        if (
            repo is not default_user_repo
            and hasattr(default_user_repo, "_users")
            and not default_user_repo.get_user_by_id(uid)
        ):
            try:
                default_user_repo._users[uid] = {
                    "id": uid,
                    "name": user.name,
                    "email": user.email,
                    "hashed_password": stored_hash,
                    "google_id": user.google_id,
                    "picture": user.picture,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "is_active": user.is_active,
                    "role": user.role,
                    "risk_profile": user.risk_profile,
                }
            except Exception:
                pass

        access_token = create_access_token(data={"sub": user.email, "user_id": uid})
        refresh_token = create_refresh_token(data={"sub": user.email, "user_id": uid})

        logger.info("User login successful user_id=%s", uid)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": {"id": uid, "email": user.email, "name": user.name},
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
    """Find existing user by google_id or email, link metadata, or create new OAuth user."""
    normalized_email = email.strip().lower()
    repo = get_user_repository()

    if hasattr(repo, "get_or_create_google_user"):
        user = repo.get_or_create_google_user(
            google_id=google_id,
            email=normalized_email,
            name=name,
            picture=avatar_url,
            avatar_url=avatar_url,
        )
    else:
        user = repo.get_user_by_email(normalized_email)
        if not user:
            try:
                user = repo.create_user(
                    name=name,
                    email=normalized_email,
                    hashed_password="",
                    google_id=google_id,
                    picture=avatar_url,
                )
            except TypeError:
                user = repo.create_user(
                    name=name,
                    email=normalized_email,
                    hashed_password="",
                )
        else:
            if hasattr(repo, "_user_metadata") and user.id is not None:
                user_uid_str = str(user.id)
                meta = repo._user_metadata.setdefault(user_uid_str, {})
                if google_id and not user.google_id:
                    meta["google_id"] = google_id
                if avatar_url and not user.picture:
                    meta["picture"] = avatar_url
                user = repo.get_user_by_id(user.id) or user

    if repo is not default_user_repo and hasattr(default_user_repo, "_users") and user:
        try:
            default_user_repo._users[user.id] = {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "hashed_password": "",
                "google_id": google_id,
                "picture": avatar_url,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "is_active": user.is_active,
                "role": user.role,
                "risk_profile": user.risk_profile,
            }
        except Exception:
            pass

    uid: Any
    if isinstance(user.id, int):
        uid = user.id
    elif user.id is not None and str(user.id).isdigit():
        uid = int(str(user.id))
    else:
        uid = user.id or ""

    access_token = create_access_token(data={"sub": user.email, "user_id": uid})
    refresh_token = create_refresh_token(data={"sub": user.email, "user_id": uid})

    picture = getattr(user, "picture", None) or avatar_url

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": uid,
            "email": user.email,
            "name": user.name,
            "picture": picture,
            "risk_profile": user.risk_profile,
        },
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
