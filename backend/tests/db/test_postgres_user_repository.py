"""PostgreSQL Integration tests for PostgresUserRepository against real finex.users table."""

import os
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
    raw_url = os.getenv("DATABASE_URL") or postgres_db.url.render_as_string(hide_password=False)
    url = raw_url.replace("+asyncpg", "").replace("localhost", "127.0.0.1")
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


@pytest.mark.asyncio
async def test_google_sign_in_persists_to_real_postgres(postgres_db):
    """Verify Google OAuth metadata survives repository reinitialization in PostgreSQL."""
    raw_url = os.getenv("DATABASE_URL") or postgres_db.url.render_as_string(hide_password=False)
    url = raw_url.replace("+asyncpg", "").replace("localhost", "127.0.0.1")

    # Instance 1: Initial creation
    repo1 = PostgresUserRepository(database_url=url, require_db=True)
    google_id = f"g_{uuid.uuid4().hex[:12]}"
    email = f"google_persist_{uuid.uuid4().hex[:8]}@example.com"
    picture = "https://lh3.googleusercontent.com/a/real_avatar.png"
    name = "Persistent Google User"

    test_uid = None
    link_uid = None
    try:
        user1 = repo1.get_or_create_google_user(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
        )
        assert user1 is not None
        assert user1.google_id == google_id
        assert user1.picture == picture
        test_uid = str(user1.id)

        # 1. Directly query finex.users SQL table to verify database row has columns populated
        async with AsyncSession(postgres_db) as session:
            result = await session.execute(
                text(
                    "SELECT user_id, email, google_id, picture "
                    "FROM finex.users WHERE user_id = :uid"
                ),
                {"uid": test_uid},
            )
            row = result.fetchone()
            assert row is not None
            assert row.email == email.lower()
            assert row.google_id == google_id
            assert row.picture == picture

        # 2. Instantiate a fresh repository instance (simulating app restart / new worker)
        repo2 = PostgresUserRepository(database_url=url, require_db=True)
        assert len(repo2._user_metadata) == 0  # Verify empty in-memory cache

        # 3. Reload by email from PostgreSQL
        user2_by_email = repo2.get_user_by_email(email)
        assert user2_by_email is not None
        assert str(user2_by_email.id) == test_uid
        assert user2_by_email.google_id == google_id
        assert user2_by_email.picture == picture

        # 4. Reload by ID from PostgreSQL
        user2_by_id = repo2.get_user_by_id(test_uid)
        assert user2_by_id is not None
        assert user2_by_id.google_id == google_id
        assert user2_by_id.picture == picture

        # 5. Reload by google_id from PostgreSQL
        user2_by_google = repo2.get_user_by_google_id(google_id)
        assert user2_by_google is not None
        assert str(user2_by_google.id) == test_uid
        assert user2_by_google.email == email.lower()

        # 6. Idempotent call with existing user on repo2 returns same persisted data
        user2_relogin = repo2.get_or_create_google_user(
            google_id=google_id,
            email=email,
            name=name,
            picture=picture,
        )
        assert str(user2_relogin.id) == test_uid
        assert user2_relogin.google_id == google_id
        assert user2_relogin.picture == picture

        # 7. Attempting to use same google_id with a different email raises GOOGLE_ACCOUNT_CONFLICT
        other_email = f"conflict_{uuid.uuid4().hex[:8]}@example.com"
        with pytest.raises(BadRequestException) as exc_info:
            repo2.get_or_create_google_user(
                google_id=google_id,
                email=other_email,
                name="Conflict User",
            )
        assert exc_info.value.error_code == "GOOGLE_ACCOUNT_CONFLICT"

        # 8. User registered with email/password links google_id in PostgreSQL
        link_email = f"link_pg_{uuid.uuid4().hex[:8]}@example.com"
        link_pw_user = repo2.create_user(
            name="Link User",
            email=link_email,
            hashed_password=hash_password("Pass@123"),
        )
        link_uid = str(link_pw_user.id)
        new_gid = f"g_link_{uuid.uuid4().hex[:12]}"
        new_pic = "https://lh3.googleusercontent.com/link_avatar.png"

        linked_user = repo2.get_or_create_google_user(
            google_id=new_gid,
            email=link_email,
            name="Link User",
            picture=new_pic,
        )
        assert str(linked_user.id) == link_uid
        assert linked_user.google_id == new_gid
        assert linked_user.picture == new_pic

        # Verify on a fresh repo3 instance (simulating restart)
        repo3 = PostgresUserRepository(database_url=url, require_db=True)
        reloaded = repo3.get_user_by_google_id(new_gid)
        assert reloaded is not None
        assert str(reloaded.id) == link_uid
        assert reloaded.google_id == new_gid
        assert reloaded.picture == new_pic

    finally:
        async with AsyncSession(postgres_db) as session:
            if test_uid:
                await session.execute(
                    text("DELETE FROM finex.users WHERE user_id = :uid"),
                    {"uid": test_uid},
                )
            if link_uid:
                await session.execute(
                    text("DELETE FROM finex.users WHERE user_id = :uid"),
                    {"uid": link_uid},
                )
            await session.commit()


@pytest.mark.asyncio
async def test_multi_worker_failed_login_throttling_postgres(postgres_db, monkeypatch):
    """Verify failed login rate limit is shared across worker instances via PostgreSQL."""
    raw_url = os.getenv("DATABASE_URL") or postgres_db.url.render_as_string(hide_password=False)
    url = raw_url.replace("+asyncpg", "").replace("localhost", "127.0.0.1")

    from app.core.exceptions import LoginRateLimitExceededException, UnauthorizedException
    from app.services import auth_service
    from app.services.auth_service import LoginAttemptTracker

    monkeypatch.setenv("APP_PERSISTENCE", "postgresql")
    monkeypatch.setenv("APP_DATABASE_URL", url)

    # Worker A and Worker B simulated as two independent repository & tracker instances
    repo_worker_a = PostgresUserRepository(database_url=url, require_db=True)
    repo_worker_b = PostgresUserRepository(database_url=url, require_db=True)

    tracker_worker_a = LoginAttemptTracker(max_attempts=10, window_seconds=900)
    tracker_worker_b = LoginAttemptTracker(max_attempts=10, window_seconds=900)

    email = f"multiworker_{uuid.uuid4().hex[:8]}@example.com"
    raw_pw = "WorkerPass@2026"
    test_uid = None

    try:
        # Create user via Worker A
        created = repo_worker_a.create_user(
            name="Worker User", email=email, hashed_password=hash_password(raw_pw)
        )
        test_uid = str(created.id)

        # Clear any prior state for this email
        tracker_worker_a.reset(email)

        # Send 5 failed attempts through Worker A
        monkeypatch.setattr(auth_service, "user_repository", repo_worker_a)
        monkeypatch.setattr(auth_service, "login_tracker", tracker_worker_a)
        for i in range(1, 6):
            with pytest.raises(UnauthorizedException):
                auth_service.login(email=email, password="BadPassword")

        # Send 5 failed attempts through Worker B (attempts 6-10)
        monkeypatch.setattr(auth_service, "user_repository", repo_worker_b)
        monkeypatch.setattr(auth_service, "login_tracker", tracker_worker_b)
        for i in range(6, 11):
            with pytest.raises(UnauthorizedException):
                auth_service.login(email=email, password="BadPassword")

        # Attempt 11 on Worker A -> Must be throttled with HTTP 429
        monkeypatch.setattr(auth_service, "user_repository", repo_worker_a)
        monkeypatch.setattr(auth_service, "login_tracker", tracker_worker_a)
        with pytest.raises(LoginRateLimitExceededException) as exc_a:
            auth_service.login(email=email, password="BadPassword")
        assert exc_a.value.status_code == 429

        # Attempt 12 on Worker B -> Must also be throttled with HTTP 429 across process boundary
        monkeypatch.setattr(auth_service, "user_repository", repo_worker_b)
        monkeypatch.setattr(auth_service, "login_tracker", tracker_worker_b)
        with pytest.raises(LoginRateLimitExceededException) as exc_b:
            auth_service.login(email=email, password="BadPassword")
        assert exc_b.value.status_code == 429

        # Direct database query: verify failed_count in finex.failed_logins is >= 10
        async with AsyncSession(postgres_db) as session:
            result = await session.execute(
                text("SELECT email, failed_count FROM finex.failed_logins WHERE email = :email"),
                {"email": email.lower()},
            )
            row = result.fetchone()
            assert row is not None
            assert row.failed_count >= 10

        # Successful login resets the counter in PostgreSQL
        tracker_worker_a.reset(email)
        login_res = auth_service.login(email=email, password=raw_pw)
        assert "access_token" in login_res

        # After reset, Worker B can attempt again without 429
        monkeypatch.setattr(auth_service, "user_repository", repo_worker_b)
        monkeypatch.setattr(auth_service, "login_tracker", tracker_worker_b)
        with pytest.raises(UnauthorizedException):
            auth_service.login(email=email, password="WrongPasswordAfterReset")

    finally:
        tracker_worker_a.reset(email)
        if test_uid:
            async with AsyncSession(postgres_db) as session:
                await session.execute(
                    text("DELETE FROM finex.users WHERE user_id = :uid"),
                    {"uid": test_uid},
                )
                await session.execute(
                    text("DELETE FROM finex.failed_logins WHERE email = :email"),
                    {"email": email.lower()},
                )
                await session.commit()


@pytest.mark.asyncio
async def test_postgres_key_lock_mutual_exclusion_and_cleanup_real_postgres(postgres_db):
    """Verify PostgresKeyLock mutual exclusion across separate physical DB sessions."""
    raw_url = os.getenv("DATABASE_URL") or postgres_db.url.render_as_string(hide_password=False)
    url = raw_url.replace("+asyncpg", "").replace("localhost", "127.0.0.1")

    import threading

    from app.services.auth_service import PostgresKeyLock

    repo = PostgresUserRepository(database_url=url, require_db=True)
    test_key = f"lock_test_{uuid.uuid4().hex[:8]}@example.com"
    local_lock = threading.Lock()

    # 1. Normal execution: lock is held inside context, verified from separate connection conn2
    with PostgresKeyLock(test_key, repo, local_lock):
        # Open a completely distinct second physical connection
        with repo._get_sync_conn(autocommit=True) as conn2:
            with conn2.cursor() as cur2:
                # pg_try_advisory_lock returns false because connection 1 holds it
                cur2.execute(
                    "SELECT pg_try_advisory_lock(hashtext(%(k)s)) AS acquired",
                    {"k": test_key},
                )
                row = cur2.fetchone()
                assert row is not None
                assert row["acquired"] is False

    # 2. Outside context: lock has been released, conn2 can now acquire it
    with repo._get_sync_conn(autocommit=True) as conn2:
        with conn2.cursor() as cur2:
            cur2.execute(
                "SELECT pg_try_advisory_lock(hashtext(%(k)s)) AS acquired",
                {"k": test_key},
            )
            row = cur2.fetchone()
            assert row is not None
            assert row["acquired"] is True
            # Release it on conn2
            cur2.execute("SELECT pg_advisory_unlock(hashtext(%(k)s))", {"k": test_key})

    # 3. Exception path: ensure lock is released even if an exception occurs inside context
    try:
        with PostgresKeyLock(test_key, repo, local_lock):
            raise RuntimeError("Simulated crash inside lock context")
    except RuntimeError:
        pass

    # Verify conn2 can immediately acquire lock following the exception
    with repo._get_sync_conn(autocommit=True) as conn2:
        with conn2.cursor() as cur2:
            cur2.execute(
                "SELECT pg_try_advisory_lock(hashtext(%(k)s)) AS acquired",
                {"k": test_key},
            )
            row = cur2.fetchone()
            assert row is not None
            assert row["acquired"] is True
            cur2.execute("SELECT pg_advisory_unlock(hashtext(%(k)s))", {"k": test_key})
