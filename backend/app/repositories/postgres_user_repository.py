"""PostgreSQL User Repository for operational user data in finex.users (S1-LI02)."""

import os
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Optional, Union

import psycopg
from psycopg.errors import UniqueViolation
from psycopg.rows import DictRow, dict_row
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.logging import logger
from app.config.settings import get_settings
from app.core.exceptions import BadRequestException, DatabaseUnavailableException
from app.models.user import UserModel
from app.ports.adapters.lakebase import AsyncSessionLocal
from app.ports.adapters.postgres_local_store import postgres_dsn

PostgresConnection = psycopg.Connection[DictRow]


class PostgresUserRepository:
    """Repository for operational user accounts stored in PostgreSQL (finex.users).

    Supports both synchronous and asynchronous operations using parameterized queries,
    normalized email lookups, secure password hash persistence, and graceful fallback.
    """

    def __init__(
        self,
        session: Optional[AsyncSession] = None,
        database_url: Optional[str] = None,
        require_db: Optional[bool] = None,
    ) -> None:
        self.session = session
        if database_url is not None:
            self._database_url = database_url
        else:
            try:
                settings_url = get_settings().app_database_url
            except Exception:
                settings_url = ""
            self._database_url = (
                settings_url or os.getenv("DATABASE_URL") or os.getenv("APP_DATABASE_URL") or ""
            )
        self._require_db = require_db
        self._memory_users: dict[str, dict[str, Any]] = {}
        self._user_metadata: dict[str, dict[str, Any]] = {}
        self._db_available: Optional[bool] = None
        self._next_id: int = 1

    def is_postgres_mode(self) -> bool:
        """Determine if the repository is configured to operate in PostgreSQL mode."""
        if self._require_db is not None:
            return self._require_db
        persistence = os.getenv("APP_PERSISTENCE", "").strip().lower()
        if persistence == "postgresql":
            return True
        try:
            if get_settings().app_persistence == "postgresql":
                return True
        except Exception:
            pass
        return bool(self._database_url)

    def _get_sync_conn(self, autocommit: bool = False) -> PostgresConnection:
        dsn = postgres_dsn(self._database_url)
        return psycopg.connect(dsn, connect_timeout=5, row_factory=dict_row, autocommit=autocommit)

    def is_db_available(self, force_refresh: bool = False) -> bool:
        """Check whether the configured PostgreSQL database is reachable."""
        if not self._database_url:
            self._db_available = False
            return False
        if not force_refresh and self._db_available is True:
            return True
        try:
            with self._get_sync_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    self._db_available = True
                    return True
        except Exception:
            self._db_available = False
            return False

    def _to_model(self, row: Union[DictRow, Mapping[str, Any], dict[str, Any]]) -> UserModel:
        raw_id = row["user_id"]
        parsed_id: Union[int, str]
        try:
            parsed_id = int(raw_id)
        except (ValueError, TypeError):
            parsed_id = str(raw_id)

        meta = self._user_metadata.get(str(parsed_id), {})
        google_id = row.get("google_id") or meta.get("google_id")
        picture = row.get("picture") or meta.get("picture")

        return UserModel(
            id=parsed_id,
            name=str(row["name"]),
            email=str(row["email"]),
            hashed_password=str(row["password_hash"]),
            google_id=google_id,
            picture=picture,
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            is_active=bool(row.get("is_active", True)),
            role=str(row.get("role", "user")),
            risk_profile=row.get("risk_profile"),
        )

    # ------------------------------------------------------------------
    # Synchronous Operations (Direct psycopg / fallback)
    # ------------------------------------------------------------------

    def get_user_by_email(self, email: str) -> Optional[UserModel]:
        """Fetch a single user by normalized email."""
        norm_email = email.strip().lower()
        if self.is_postgres_mode():
            if not self.is_db_available():
                raise DatabaseUnavailableException(
                    message="PostgreSQL database is unavailable",
                    error_code="DATABASE_UNAVAILABLE",
                )
            try:
                with self._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT user_id, email, password_hash, name, role,
                                   risk_profile, is_active, google_id, picture,
                                   created_at, updated_at
                            FROM finex.users
                            WHERE LOWER(email) = LOWER(%(email)s)
                            """,
                            {"email": norm_email},
                        )
                        row = cur.fetchone()
                        if row:
                            return self._to_model(row)
                        return None
            except (psycopg.OperationalError, psycopg.DatabaseError) as exc:
                self._db_available = False
                raise DatabaseUnavailableException(
                    message=f"PostgreSQL database error: {exc}",
                    error_code="DATABASE_UNAVAILABLE",
                ) from exc
        else:
            mem_row = self._memory_users.get(norm_email)
            return self._to_model(mem_row) if mem_row else None

    def get_user_by_id(self, user_id: Union[str, int, None]) -> Optional[UserModel]:
        """Fetch a single user by their primary key user_id."""
        if user_id is None:
            return None
        uid = str(user_id)
        if self.is_postgres_mode():
            if not self.is_db_available():
                raise DatabaseUnavailableException(
                    message="PostgreSQL database is unavailable",
                    error_code="DATABASE_UNAVAILABLE",
                )
            try:
                with self._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT user_id, email, password_hash, name, role,
                                   risk_profile, is_active, google_id, picture,
                                   created_at, updated_at
                            FROM finex.users
                            WHERE user_id = %(uid)s
                            """,
                            {"uid": uid},
                        )
                        row = cur.fetchone()
                        if row:
                            return self._to_model(row)
                        return None
            except (psycopg.OperationalError, psycopg.DatabaseError) as exc:
                self._db_available = False
                raise DatabaseUnavailableException(
                    message=f"PostgreSQL database error: {exc}",
                    error_code="DATABASE_UNAVAILABLE",
                ) from exc
        else:
            for m_row in self._memory_users.values():
                if str(m_row.get("user_id")) == uid:
                    return self._to_model(m_row)
            return None

    def get_user_by_google_id(self, google_id: str) -> Optional[UserModel]:
        """Fetch a single user by their unique google_id."""
        if not google_id:
            return None
        gid = str(google_id).strip()
        if self.is_postgres_mode():
            if not self.is_db_available():
                raise DatabaseUnavailableException(
                    message="PostgreSQL database is unavailable",
                    error_code="DATABASE_UNAVAILABLE",
                )
            try:
                with self._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT user_id, email, password_hash, name, role,
                                   risk_profile, is_active, google_id, picture,
                                   created_at, updated_at
                            FROM finex.users
                            WHERE google_id = %(gid)s
                            """,
                            {"gid": gid},
                        )
                        row = cur.fetchone()
                        if row:
                            return self._to_model(row)
                        return None
            except (psycopg.OperationalError, psycopg.DatabaseError) as exc:
                self._db_available = False
                raise DatabaseUnavailableException(
                    message=f"PostgreSQL database error: {exc}",
                    error_code="DATABASE_UNAVAILABLE",
                ) from exc
        else:
            for m_row in self._memory_users.values():
                if m_row.get("google_id") == gid:
                    return self._to_model(m_row)
            return None

    def create_user(
        self,
        name: str,
        email: str,
        hashed_password: str,
        role: str = "user",
        risk_profile: Optional[str] = None,
        user_id: Optional[str] = None,
        google_id: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> UserModel:
        """Insert a new user record into finex.users. Raises BadRequestException if email exists."""
        norm_email = email.strip().lower()
        uid = str(user_id) if user_id is not None else str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if google_id or picture:
            self._user_metadata[uid] = {
                "google_id": google_id,
                "picture": picture,
            }

        if self.is_postgres_mode():
            if not self.is_db_available():
                raise DatabaseUnavailableException(
                    message="PostgreSQL database is unavailable for user registration",
                    error_code="DATABASE_UNAVAILABLE",
                )
            try:
                with self._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        # Check existing user
                        cur.execute(
                            "SELECT user_id FROM finex.users WHERE LOWER(email) = LOWER(%(email)s)",
                            {"email": norm_email},
                        )
                        if cur.fetchone():
                            raise BadRequestException(
                                message="Email already registered",
                                error_code="EMAIL_EXISTS",
                            )

                        try:
                            cur.execute(
                                """
                                INSERT INTO finex.users (
                                    user_id, email, password_hash, name, role,
                                    risk_profile, is_active, google_id, picture,
                                    created_at, updated_at
                                )
                                VALUES (
                                    %(uid)s, %(email)s, %(pw)s, %(name)s, %(role)s,
                                    %(risk)s, TRUE, %(google_id)s, %(picture)s, NOW(), NOW()
                                )
                                RETURNING user_id, email, password_hash, name, role,
                                          risk_profile, is_active, google_id, picture,
                                          created_at, updated_at
                                """,
                                {
                                    "uid": uid,
                                    "email": norm_email,
                                    "pw": hashed_password,
                                    "name": name,
                                    "role": role,
                                    "risk": risk_profile,
                                    "google_id": google_id,
                                    "picture": picture,
                                },
                            )
                        except (
                            psycopg.errors.UndefinedColumn,
                            psycopg.errors.InvalidColumnReference,
                        ):
                            # Fallback if migration fx_006 not yet applied
                            cur.execute(
                                """
                                INSERT INTO finex.users (
                                    user_id, email, password_hash, name, role,
                                    risk_profile, is_active, created_at, updated_at
                                )
                                VALUES (
                                    %(uid)s, %(email)s, %(pw)s, %(name)s, %(role)s,
                                    %(risk)s, TRUE, NOW(), NOW()
                                )
                                RETURNING user_id, email, password_hash, name, role,
                                          risk_profile, is_active, created_at, updated_at
                                """,
                                {
                                    "uid": uid,
                                    "email": norm_email,
                                    "pw": hashed_password,
                                    "name": name,
                                    "role": role,
                                    "risk": risk_profile,
                                },
                            )
                        row = cur.fetchone()
                        conn.commit()
                        if row:
                            self._memory_users[norm_email] = dict(row)
                            return self._to_model(row)
                        raise BadRequestException(
                            message="Failed to insert user record",
                            error_code="USER_CREATION_FAILED",
                        )
            except UniqueViolation:
                raise BadRequestException(
                    message="Email already registered",
                    error_code="EMAIL_EXISTS",
                )
            except (psycopg.OperationalError, psycopg.DatabaseError) as exc:
                self._db_available = False
                raise DatabaseUnavailableException(
                    message=f"PostgreSQL database error during user creation: {exc}",
                    error_code="DATABASE_UNAVAILABLE",
                ) from exc
        else:
            if norm_email in self._memory_users:
                raise BadRequestException(
                    message="Email already registered",
                    error_code="EMAIL_EXISTS",
                )
            mem_row = {
                "user_id": uid,
                "email": norm_email,
                "password_hash": hashed_password,
                "name": name,
                "role": role,
                "risk_profile": risk_profile,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "google_id": google_id,
                "picture": picture,
            }
            self._memory_users[norm_email] = mem_row
            return self._to_model(mem_row)

    def get_or_create_google_user(
        self,
        google_id: str,
        email: str,
        name: str,
        picture: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> UserModel:
        """Find existing user by google_id or email, link metadata, or create new OAuth user."""
        pic = picture or avatar_url
        norm_email = email.strip().lower()

        # 1. First check if user already exists with this exact google_id
        if google_id:
            user_by_google = self.get_user_by_google_id(google_id)
            if user_by_google:
                if user_by_google.email.strip().lower() != norm_email:
                    raise BadRequestException(
                        message="Google ID is already linked to another email address",
                        error_code="GOOGLE_ACCOUNT_CONFLICT",
                    )
                if pic and not user_by_google.picture:
                    if self.is_postgres_mode() and self.is_db_available():
                        try:
                            with self._get_sync_conn() as conn:
                                with conn.cursor() as cur:
                                    cur.execute(
                                        """
                                        UPDATE finex.users
                                        SET picture = %(pic)s, updated_at = NOW()
                                        WHERE user_id = %(uid)s
                                        RETURNING user_id, email, password_hash, name, role,
                                                  risk_profile, is_active, google_id, picture,
                                                  created_at, updated_at
                                        """,
                                        {"pic": pic, "uid": str(user_by_google.id)},
                                    )
                                    row = cur.fetchone()
                                    conn.commit()
                                    if row:
                                        return self._to_model(row)
                        except Exception as e:
                            logger.warning("Failed to update picture in PostgreSQL: %s", e)
                    else:
                        uid_str = str(user_by_google.id)
                        self._user_metadata.setdefault(uid_str, {})["picture"] = pic
                        for m_row in self._memory_users.values():
                            if str(m_row.get("user_id")) == uid_str:
                                m_row["picture"] = pic
                                break
                return user_by_google

        # 2. Check if user already exists with this email
        user = self.get_user_by_email(norm_email)
        if user:
            uid = str(user.id)
            meta = self._user_metadata.setdefault(uid, {})
            needs_update = False
            new_google_id = user.google_id
            new_picture = user.picture

            if google_id and not user.google_id:
                meta["google_id"] = google_id
                new_google_id = google_id
                needs_update = True
            elif google_id and user.google_id and user.google_id != google_id:
                raise BadRequestException(
                    message="Email is already linked to another Google account",
                    error_code="GOOGLE_ACCOUNT_CONFLICT",
                )

            if pic and not user.picture:
                meta["picture"] = pic
                new_picture = pic
                needs_update = True

            if needs_update and self.is_postgres_mode() and self.is_db_available():
                try:
                    with self._get_sync_conn() as conn:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE finex.users
                                SET google_id = COALESCE(google_id, %(gid)s),
                                    picture = COALESCE(picture, %(pic)s),
                                    updated_at = NOW()
                                WHERE user_id = %(uid)s
                                RETURNING user_id, email, password_hash, name, role,
                                          risk_profile, is_active, google_id, picture,
                                          created_at, updated_at
                                """,
                                {"gid": new_google_id, "pic": new_picture, "uid": uid},
                            )
                            row = cur.fetchone()
                            conn.commit()
                            if row:
                                return self._to_model(row)
                except Exception as exc:
                    logger.warning("Failed to update Google metadata in PostgreSQL: %s", exc)
            elif needs_update and not self.is_postgres_mode():
                if norm_email in self._memory_users:
                    if new_google_id:
                        self._memory_users[norm_email]["google_id"] = new_google_id
                    if new_picture:
                        self._memory_users[norm_email]["picture"] = new_picture

            return self.get_user_by_id(user.id) or user

        # 3. Create new OAuth user
        return self.create_user(
            name=name,
            email=norm_email,
            hashed_password="",
            google_id=google_id,
            picture=pic,
        )

    def update_user_login(self, user_id: Union[str, int]) -> None:
        """Update updated_at timestamp upon successful authentication."""
        uid = str(user_id)
        if self.is_postgres_mode():
            if not self.is_db_available():
                return
            try:
                with self._get_sync_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "UPDATE finex.users SET updated_at = NOW() WHERE user_id = %(uid)s",
                            {"uid": uid},
                        )
                        conn.commit()
            except (psycopg.OperationalError, psycopg.DatabaseError):
                self._db_available = False
        else:
            for row in self._memory_users.values():
                if str(row.get("user_id")) == uid:
                    row["updated_at"] = datetime.now(timezone.utc)
                    break

    # ------------------------------------------------------------------
    # Asynchronous Operations (SQLAlchemy AsyncSession)
    # ------------------------------------------------------------------

    async def get_user_by_email_async(self, email: str) -> Optional[UserModel]:
        """Async fetch user by normalized email."""
        norm_email = email.strip().lower()
        query = text(
            """
            SELECT user_id, email, password_hash, name, role,
                   risk_profile, is_active, google_id, picture, created_at, updated_at
            FROM finex.users
            WHERE LOWER(email) = LOWER(:email)
            """
        )
        if self.session:
            result = await self.session.execute(query, {"email": norm_email})
            row = result.fetchone()
            return self._to_model(dict(row._mapping)) if row else None

        async with AsyncSessionLocal() as session:
            result = await session.execute(query, {"email": norm_email})
            row = result.fetchone()
            return self._to_model(dict(row._mapping)) if row else None

    async def get_user_by_id_async(self, user_id: Union[str, int, None]) -> Optional[UserModel]:
        """Async fetch user by UUID."""
        if user_id is None:
            return None
        uid = str(user_id)
        query = text(
            """
            SELECT user_id, email, password_hash, name, role,
                   risk_profile, is_active, google_id, picture, created_at, updated_at
            FROM finex.users
            WHERE user_id = :uid
            """
        )
        if self.session:
            result = await self.session.execute(query, {"uid": uid})
            row = result.fetchone()
            return self._to_model(dict(row._mapping)) if row else None

        async with AsyncSessionLocal() as session:
            result = await session.execute(query, {"uid": uid})
            row = result.fetchone()
            return self._to_model(dict(row._mapping)) if row else None

    async def create_user_async(
        self,
        name: str,
        email: str,
        hashed_password: str,
        role: str = "user",
        risk_profile: Optional[str] = None,
        user_id: Optional[str] = None,
        google_id: Optional[str] = None,
        picture: Optional[str] = None,
    ) -> UserModel:
        """Async insert user record with duplicate check."""
        norm_email = email.strip().lower()
        uid = str(user_id) if user_id is not None else str(uuid.uuid4())

        if google_id or picture:
            self._user_metadata[uid] = {
                "google_id": google_id,
                "picture": picture,
            }

        existing = await self.get_user_by_email_async(norm_email)
        if existing:
            raise BadRequestException(
                message="Email already registered",
                error_code="EMAIL_EXISTS",
            )

        query = text(
            """
            INSERT INTO finex.users (
                user_id, email, password_hash, name, role,
                risk_profile, is_active, google_id, picture, created_at, updated_at
            )
            VALUES (
                :uid, :email, :pw, :name, :role,
                :risk, TRUE, :google_id, :picture, NOW(), NOW()
            )
            RETURNING user_id, email, password_hash, name, role,
                      risk_profile, is_active, google_id, picture, created_at, updated_at
            """
        )
        params = {
            "uid": uid,
            "email": norm_email,
            "pw": hashed_password,
            "name": name,
            "role": role,
            "risk": risk_profile,
            "google_id": google_id,
            "picture": picture,
        }

        try:
            if self.session:
                result = await self.session.execute(query, params)
                await self.session.flush()
                row = result.fetchone()
                if row:
                    return self._to_model(dict(row._mapping))
            else:
                async with AsyncSessionLocal() as session:
                    result = await session.execute(query, params)
                    await session.commit()
                    row = result.fetchone()
                    if row:
                        return self._to_model(dict(row._mapping))
        except IntegrityError:
            raise BadRequestException(
                message="Email already registered",
                error_code="EMAIL_EXISTS",
            )

        raise BadRequestException(
            message="Failed to insert user record",
            error_code="USER_CREATION_FAILED",
        )


postgres_user_repository = PostgresUserRepository()
