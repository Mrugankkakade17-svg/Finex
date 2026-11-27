"""Genuine PostgreSQL integration tests for production watchlists and items."""

from __future__ import annotations

import os
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv

import app.repositories.watchlist_repository as watchlist_repo_module
from app.config.settings import Settings
from app.ports.adapters.postgres_local_store import postgres_dsn
from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.watchlist import WatchlistCreate, WatchlistItemCreate
from app.services.watchlist_service import WatchlistService


@pytest.mark.postgres
def test_watchlists_postgres_persistence_and_cross_user_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_dotenv()
    database_url = os.getenv("APP_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("APP_DATABASE_URL or DATABASE_URL is required for PostgreSQL coverage")

    monkeypatch.setenv("APP_PERSISTENCE", "postgresql")
    settings = Settings(app_persistence="postgresql", app_database_url=database_url)
    monkeypatch.setattr(watchlist_repo_module, "get_settings", lambda: settings)

    dsn = postgres_dsn(database_url)

    # 1. Ensure required finex schema and tables exist
    with psycopg.connect(dsn) as conn:
        conn.execute(
            """
            CREATE SCHEMA IF NOT EXISTS finex;
            CREATE TABLE IF NOT EXISTS finex.users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS finex.watchlists (
                user_id TEXT NOT NULL REFERENCES finex.users(user_id) ON DELETE CASCADE,
                watchlist_id TEXT NOT NULL,
                name VARCHAR(100) NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (user_id, watchlist_id)
            );
            CREATE TABLE IF NOT EXISTS finex.watchlist_items (
                user_id TEXT NOT NULL REFERENCES finex.users(user_id) ON DELETE CASCADE,
                watchlist_id TEXT NOT NULL,
                instrument_id VARCHAR(32) NOT NULL,
                added_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (watchlist_id, instrument_id),
                FOREIGN KEY (user_id, watchlist_id)
                    REFERENCES finex.watchlists(user_id, watchlist_id) ON DELETE CASCADE
            );
            """
        )

        user_alice = str(uuid4())
        user_bob = str(uuid4())

        conn.execute(
            """
            INSERT INTO finex.users (user_id, email, password_hash, name)
            VALUES
                (%s, %s, 'hash-alice', 'Alice Tester'),
                (%s, %s, 'hash-bob', 'Bob Tester')
            ON CONFLICT (user_id) DO NOTHING;
            """,
            (
                user_alice,
                f"alice-{user_alice[:8]}@test.finex",
                user_bob,
                f"bob-{user_bob[:8]}@test.finex",
            ),
        )

    try:
        repo = WatchlistRepository()
        assert repo.is_postgres is True
        service = WatchlistService(repo)

        # Alice creates a watchlist
        created = service.create_watchlist(user_alice, WatchlistCreate(name="Alice PG Growth"))
        watchlist_id = created.watchlist_id
        assert created.name == "Alice PG Growth"
        assert created.item_count == 0

        # Alice adds items
        service.add_item(user_alice, watchlist_id, WatchlistItemCreate(instrument_id="RELIANCE"))
        service.add_item(user_alice, watchlist_id, WatchlistItemCreate(instrument_id="TCS"))

        # Verify items can be retrieved via service
        w_retrieved = service.get_watchlist(user_alice, watchlist_id)
        assert w_retrieved.item_count == 2
        symbols = [item.instrument_id for item in w_retrieved.items]
        assert "RELIANCE" in symbols and "TCS" in symbols

        # Direct SQL query against PostgreSQL: verify rows genuinely exist in the database
        with psycopg.connect(dsn) as conn:
            w_row = conn.execute(
                "SELECT name, user_id FROM finex.watchlists WHERE watchlist_id = %s",
                (watchlist_id,),
            ).fetchone()
            assert w_row is not None
            assert w_row[0] == "Alice PG Growth"
            assert w_row[1] == user_alice

            i_count = conn.execute(
                "SELECT COUNT(*) FROM finex.watchlist_items WHERE watchlist_id = %s",
                (watchlist_id,),
            ).fetchone()[0]
            assert i_count == 2

        # Cross-User Isolation: Bob attempts to access Alice's watchlist
        # 1. Bob's list should be empty
        assert service.list_watchlists(user_bob) == []

        # 2. Bob cannot get Alice's watchlist (raises 404)
        with pytest.raises(Exception) as exc_info:
            service.get_watchlist(user_bob, watchlist_id)
        assert "404" in str(exc_info.value) or exc_info.value.status_code == 404

        # 3. Bob cannot add items to Alice's watchlist (raises 404)
        with pytest.raises(Exception):
            service.add_item(user_bob, watchlist_id, WatchlistItemCreate(instrument_id="AAPL"))

        # 4. Bob cannot list items from Alice's watchlist (raises 404)
        with pytest.raises(Exception):
            service.list_items(user_bob, watchlist_id)

        # 5. Bob cannot delete Alice's watchlist (raises 404)
        with pytest.raises(Exception):
            service.delete_watchlist(user_bob, watchlist_id)

        # Re-check direct SQL: Alice's items were NOT affected by Bob's attempts
        with psycopg.connect(dsn) as conn:
            i_count = conn.execute(
                "SELECT COUNT(*) FROM finex.watchlist_items WHERE watchlist_id = %s",
                (watchlist_id,),
            ).fetchone()[0]
            assert i_count == 2

        # Alice deletes her watchlist
        service.delete_watchlist(user_alice, watchlist_id)

        # Direct SQL: Verify cascading delete removed watchlist and its items from PostgreSQL
        with psycopg.connect(dsn) as conn:
            w_exists = conn.execute(
                "SELECT COUNT(*) FROM finex.watchlists WHERE watchlist_id = %s",
                (watchlist_id,),
            ).fetchone()[0]
            assert w_exists == 0

            i_exists = conn.execute(
                "SELECT COUNT(*) FROM finex.watchlist_items WHERE watchlist_id = %s",
                (watchlist_id,),
            ).fetchone()[0]
            assert i_exists == 0

    finally:
        # Cleanup test users
        with psycopg.connect(dsn) as conn:
            conn.execute(
                "DELETE FROM finex.users WHERE user_id IN (%s, %s)",
                (user_alice, user_bob),
            )
