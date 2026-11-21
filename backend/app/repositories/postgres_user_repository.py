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

from app.core.exceptions import BadRequestException
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
    ) -> None:
        self.session = session
        self._database_url = (
            database_url
            or os.getenv("DATABASE_URL")
            or os.getenv("APP_DATABASE_URL")
            or "postgresql://postgres:postgres@localhost:5432/finex_test"
        )
        self._memory_users: dict[str, dict[str, Any]] = {}
        self._db_available: Optional[bool] = None
        self._next_id: int = 1

    def _get_sync_conn(self) -> PostgresConnection:
        dsn = postgres_dsn(self._database_url)
        return psycopg.connect(dsn, connect_timeout=1, row_factory=dict_row)

    def is_db_available(self) -> bool:
        """Check whether the configured PostgreSQL database is reachable."""
        if self._db_available is not None:
            return self._db_available
        try:
            with self._get_sync_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    self._db_available = True
                    return True
        except Exception:
            self._db_available = False
            return False

    @staticmethod
    def _to_model(row: Union[DictRow, Mapping[str, Any], dict[str, Any]]) -> UserModel:
        raw_id = row["user_id"]
        parsed_id: Union[int, str]
        try:
            parsed_id = int(raw_id)
        except (ValueError, TypeError):
            parsed_id = str(raw_id)

        return UserModel(
            id=parsed_id,
            name=str(row["name"]),
            email=str(row["email"]),
            hashed_password=str(row["password_hash"]),
            google_id=row.get("google_id"),
            picture=row.get("picture"),
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
        if not self.is_db_available():
            mem_row = self._memory_users.get(norm_email)
            return self._to_model(mem_row) if mem_row else None

        try:
            with self._get_sync_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT user_id, email, password_hash, name, role,
                               risk_profile, is_active, created_at, updated_at
                        FROM finex.users
                        WHERE LOWER(email) = LOWER(%(email)s)
                        """,
                        {"email": norm_email},
                    )
                    row = cur.fetchone()
                    if row:
                        return self._to_model(row)
                    return None
        except (psycopg.OperationalError, psycopg.DatabaseError):
            self._db_available = False
            mem_row = self._memory_users.get(norm_email)
            return self._to_model(mem_row) if mem_row else None

    def get_user_by_id(self, user_id: Union[str, int]) -> Optional[UserModel]:
        """Fetch a single user by their primary key user_id."""
        uid = str(user_id)
        if not self.is_db_available():
            for m_row in self._memory_users.values():
                if str(m_row.get("user_id")) == uid:
                    return self._to_model(m_row)
            return None

        try:
            with self._get_sync_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT user_id, email, password_hash, name, role,
                               risk_profile, is_active, created_at, updated_at
                        FROM finex.users
                        WHERE user_id = %(uid)s
                        """,
                        {"uid": uid},
                    )
                    row = cur.fetchone()
                    if row:
                        return self._to_model(row)
                    return None
        except (psycopg.OperationalError, psycopg.DatabaseError):
            self._db_available = False
            for m_row in self._memory_users.values():
                if str(m_row.get("user_id")) == uid:
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
    ) -> UserModel:
        """Insert a new user record into finex.users. Raises BadRequestException if email exists."""
        norm_email = email.strip().lower()
        uid = str(user_id) if user_id is not None else str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        if not self.is_db_available():
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
            }
            self._memory_users[norm_email] = mem_row
            return self._to_model(mem_row)

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
        except (psycopg.OperationalError, psycopg.DatabaseError):
            self._db_available = False
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
            }
            self._memory_users[norm_email] = mem_row
            return self._to_model(mem_row)

    def update_user_login(self, user_id: Union[str, int]) -> None:
        """Update updated_at timestamp upon successful authentication."""
        uid = str(user_id)
        if not self.is_db_available():
            for row in self._memory_users.values():
                if str(row.get("user_id")) == uid:
                    row["updated_at"] = datetime.now(timezone.utc)
                    break
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
                   risk_profile, is_active, created_at, updated_at
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

    async def get_user_by_id_async(self, user_id: Union[str, int]) -> Optional[UserModel]:
        """Async fetch user by UUID."""
        uid = str(user_id)
        query = text(
            """
            SELECT user_id, email, password_hash, name, role,
                   risk_profile, is_active, created_at, updated_at
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
    ) -> UserModel:
        """Async insert user record with duplicate check."""
        norm_email = email.strip().lower()
        uid = str(user_id) if user_id is not None else str(uuid.uuid4())

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
                risk_profile, is_active, created_at, updated_at
            )
            VALUES (
                :uid, :email, :pw, :name, :role,
                :risk, TRUE, NOW(), NOW()
            )
            RETURNING user_id, email, password_hash, name, role,
                      risk_profile, is_active, created_at, updated_at
            """
        )
        params = {
            "uid": uid,
            "email": norm_email,
            "pw": hashed_password,
            "name": name,
            "role": role,
            "risk": risk_profile,
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
