"""PostgreSQL Integration tests for PostgresUserRepository against real finex.users table."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.password import hash_password, verify_password
from app.core.exceptions import BadRequestException
from app.repositories.postgres_user_repository import PostgresUserRepository

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_postgres_user_repository_crud_against_real_db(postgres_db):
    """Verify PostgresUserRepository CRUD operations on real PostgreSQL finex.users."""
    async with AsyncSession(postgres_db) as session:
        repo = PostgresUserRepository(session=session)

        test_uid = str(uuid.uuid4())
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        raw_pw = "SecurePostgresPass@2026"
        hashed = hash_password(raw_pw)

        try:
            # 1. Create user
            created_user = await repo.create_user_async(
                name="Postgres Test User",
                email=email,
                hashed_password=hashed,
                role="trader",
                risk_profile="aggressive",
                user_id=test_uid,
            )
            assert created_user.id == test_uid
            assert created_user.email == email.lower()
            assert created_user.role == "trader"
            assert verify_password(raw_pw, created_user.hashed_password)

            # 2. Retrieve by normalized email
            found_by_email = await repo.get_user_by_email_async(email.upper())
            assert found_by_email is not None
            assert found_by_email.id == test_uid
            assert found_by_email.name == "Postgres Test User"

            # 3. Retrieve by ID
            found_by_id = await repo.get_user_by_id_async(test_uid)
            assert found_by_id is not None
            assert found_by_id.email == email.lower()

            # 4. Enforce duplicate email rejection
            with pytest.raises(BadRequestException) as exc_info:
                await repo.create_user_async(
                    name="Duplicate User",
                    email=email.upper(),
                    hashed_password=hashed,
                )
            assert exc_info.value.error_code == "EMAIL_EXISTS"

            # 5. Verify direct SQL selection on finex.users table
            result = await session.execute(
                text("SELECT user_id, email, role FROM finex.users WHERE user_id = :uid"),
                {"uid": test_uid},
            )
            db_row = result.fetchone()
            assert db_row is not None
            assert db_row.user_id == test_uid
            assert db_row.email == email.lower()
            assert db_row.role == "trader"
        finally:
            await session.execute(
                text("DELETE FROM finex.users WHERE user_id = :uid"),
                {"uid": test_uid},
            )
            await session.commit()


@pytest.mark.asyncio
async def test_auth_service_real_postgres_integration(postgres_db, monkeypatch):
    """Verify synchronous auth_service.register and auth_service.login against real PostgreSQL."""
    url = str(postgres_db.url).replace("+asyncpg", "").replace("localhost", "127.0.0.1")
    repo = PostgresUserRepository(database_url=url, require_db=True)

    from app.core.exceptions import UnauthorizedException
    from app.services import auth_service

    monkeypatch.setattr(auth_service, "user_repository", repo)
    monkeypatch.setenv("APP_PERSISTENCE", "postgresql")
    monkeypatch.setenv("APP_DATABASE_URL", url)

    test_uid = None
    email = f"auth_svc_{uuid.uuid4().hex[:8]}@example.com"
    raw_pw = "RealPostgresPass@2026"

    try:
        # 1. Register through auth_service
        reg_result = auth_service.register(name="Auth Real User", email=email, password=raw_pw)
        assert "access_token" in reg_result
        assert "refresh_token" in reg_result
        assert reg_result["user"]["email"] == email.lower()
        test_uid = reg_result["user"]["id"]
        assert test_uid is not None

        # 2. Verify persisted directly in finex.users via SQL
        async with AsyncSession(postgres_db) as session:
            result = await session.execute(
                text(
                    "SELECT user_id, email, password_hash, name "
                    "FROM finex.users WHERE user_id = :uid"
                ),
                {"uid": str(test_uid)},
            )
            row = result.fetchone()
            assert row is not None
            assert row.email == email.lower()
            assert row.name == "Auth Real User"
            assert verify_password(raw_pw, row.password_hash)

        # 3. Successful login through auth_service
        login_result = auth_service.login(email=email, password=raw_pw)
        assert "access_token" in login_result
        assert login_result["user"]["email"] == email.lower()
        assert str(login_result["user"]["id"]) == str(test_uid)

        # 4. Failed login raises UnauthorizedException
        with pytest.raises(UnauthorizedException) as exc_info:
            auth_service.login(email=email, password="WrongPassword@123")
        assert exc_info.value.status_code == 401
        assert exc_info.value.error_code == "INVALID_CREDENTIALS"

        # 5. Duplicate registration raises EMAIL_EXISTS
        with pytest.raises(BadRequestException) as exc_info:
            auth_service.register(name="Duplicate User", email=email.upper(), password=raw_pw)
        assert exc_info.value.error_code == "EMAIL_EXISTS"

    finally:
        if test_uid:
            async with AsyncSession(postgres_db) as session:
                await session.execute(
                    text("DELETE FROM finex.users WHERE user_id = :uid"),
                    {"uid": str(test_uid)},
                )
                await session.commit()
