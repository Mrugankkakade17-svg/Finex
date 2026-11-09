"""Preserving native schema-4 assertions against independent frozen generations.

Only fresh pytest-owned synthetic SQLite files are touched. This does not run
cloud Alembic DDL, reset a user's database or prove native TCP acceptance.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from threading import Barrier

import pytest

from app.domain.local_application import LocalStoreUnavailable
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_portfolio_store import SQLiteLocalPortfolioStore
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore
from tests.unit.test_local_portfolio_schema import (
    DIGEST,
    OWNER,
    STAMP,
    frozen_owned_file,
    stored_schema,
    stored_version,
)

V3_ADDED = (
    """CREATE TABLE local_manual_portfolios (
        portfolio_id TEXT PRIMARY KEY NOT NULL,
        user_id TEXT NOT NULL REFERENCES local_users(user_id),
        name TEXT NOT NULL CHECK(typeof(name)='text' AND length(name) BETWEEN 1 AND 100),
        description TEXT CHECK(description IS NULL OR
            (typeof(description)='text' AND length(description)<=500)),
        currency TEXT NOT NULL CHECK(currency='USD'),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(user_id,portfolio_id)
    )""",
    "CREATE INDEX local_manual_portfolio_owner ON "
    "local_manual_portfolios(user_id,created_at,portfolio_id)",
    """CREATE TABLE local_manual_holdings (
        holding_id TEXT PRIMARY KEY NOT NULL,
        user_id TEXT NOT NULL, portfolio_id TEXT NOT NULL,
        instrument_id TEXT NOT NULL,
        quantity_micro_units INTEGER NOT NULL CHECK(typeof(quantity_micro_units)='integer'
            AND quantity_micro_units BETWEEN 1 AND 1000000000000),
        average_cost_units INTEGER NOT NULL CHECK(typeof(average_cost_units)='integer'
            AND average_cost_units BETWEEN 0 AND 10000000000),
        currency TEXT NOT NULL CHECK(currency='USD'),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id,portfolio_id) REFERENCES local_manual_portfolios(user_id,portfolio_id)
            ON DELETE CASCADE,
        UNIQUE(user_id,portfolio_id,instrument_id)
    )""",
    "CREATE INDEX local_manual_holding_owner ON "
    "local_manual_holdings(user_id,portfolio_id,created_at,holding_id)",
)
NEW_TABLES = {
    "local_watchlists",
    "local_watchlist_items",
    "local_paper_accounts",
    "local_paper_ledger",
}
PORTFOLIO_ID = "00000000-0000-4000-8000-000000000195"
HOLDING_ID = "00000000-0000-4000-8000-000000000196"
V1_TABLES = (
    "local_users",
    "local_sessions",
    "local_onboarding",
    "local_consent_events",
    "sqlite_sequence",
)
RISK_TABLES = ("local_risk_drafts", "local_risk_assessments")
MANUAL_TABLES = ("local_manual_portfolios", "local_manual_holdings")
SOURCE_TABLES = {
    1: V1_TABLES,
    2: V1_TABLES + RISK_TABLES,
    3: V1_TABLES + RISK_TABLES + MANUAL_TABLES,
}


def frozen_file(path: Path, version: int) -> None:
    frozen_owned_file(path, min(version, 2))
    if version == 3:
        with closing(sqlite3.connect(path)) as connection:
            for statement in V3_ADDED:
                connection.execute(statement)
            connection.execute("UPDATE schema_metadata SET version=3")
            connection.execute(
                "INSERT INTO local_manual_portfolios VALUES(?,?,?,?,?,?,?)",
                (PORTFOLIO_ID, OWNER, "Synthetic preserved portfolio", None, "USD", STAMP, STAMP),
            )
            connection.execute(
                "INSERT INTO local_manual_holdings VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    HOLDING_ID,
                    OWNER,
                    PORTFOLIO_ID,
                    "SYN:AAPL",
                    1000000,
                    1500000,
                    "USD",
                    STAMP,
                    STAMP,
                ),
            )
            connection.commit()


def preserved_rows(path: Path, source_version: int) -> dict[str, list[tuple[object, ...]]]:
    with closing(sqlite3.connect(path)) as connection:
        tables = tuple(
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND (name NOT GLOB 'sqlite_*' OR name='sqlite_sequence') ORDER BY name"
            )
        )
        originals = SOURCE_TABLES[source_version]
        assert set(originals) <= set(tables)
        current = connection.execute("SELECT version FROM schema_metadata").fetchone()[0]
        if current == 4:
            expected = {*V1_TABLES, *RISK_TABLES, *MANUAL_TABLES, *NEW_TABLES, "schema_metadata"}
            assert set(tables) == expected
            for name in expected - set(originals) - {"schema_metadata"}:
                assert connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] == 0
        else:
            assert current == source_version
            assert set(tables) == {*originals, "schema_metadata"}
        return {
            name: list(connection.execute(f"SELECT * FROM {name} ORDER BY rowid"))
            for name in originals
        }


def test_first_accepted_s1_use_creates_shared_schema_four_lazily(tmp_path: Path) -> None:
    path = tmp_path / "fresh-v4.sqlite3"
    store = SQLiteLocalApplicationStore(path)
    assert not path.exists()
    with store.transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None
    assert stored_version(path) == 4
    assert NEW_TABLES <= {row[0] for row in stored_schema(path)}


@pytest.mark.parametrize("version", [1, 2, 3])
@pytest.mark.parametrize(
    "store_type", [SQLiteLocalApplicationStore, SQLiteLocalRiskStore, SQLiteLocalPortfolioStore]
)
def test_prior_generations_and_all_capabilities_preserve_rows_objects_sequences_to_four(
    tmp_path: Path,
    version: int,
    store_type: type[SQLiteLocalApplicationStore]
    | type[SQLiteLocalRiskStore]
    | type[SQLiteLocalPortfolioStore],
) -> None:
    path = tmp_path / "preserving-v4.sqlite3"
    frozen_file(path, version)
    before_rows, before_schema = preserved_rows(path, version), stored_schema(path)
    with store_type(path).transaction() as transaction:
        session = transaction.get_session(DIGEST)
        owner_matches = session is not None and session.user.id == OWNER
        assert owner_matches
    assert stored_version(path) == 4
    assert preserved_rows(path, version) == before_rows
    assert set(before_schema) <= set(stored_schema(path))
    assert NEW_TABLES <= {row[0] for row in stored_schema(path)}
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("PRAGMA application_id").fetchone()[0] == 0
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        for table in ("local_consent_events",) + (
            ("local_risk_assessments",) if version >= 2 else ()
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(f"UPDATE {table} SET user_id=user_id")
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(f"DELETE FROM {table}")


class FailedBootstrapStore(SQLiteLocalApplicationStore):
    def _before_schema_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic schema-four commit failure")


@pytest.mark.parametrize("version", [1, 2, 3])
def test_upgrade_failure_preserves_prior_file_rows_schema_version_and_journal(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "rollback-v4.sqlite3"
    frozen_file(path, version)
    before_rows, before_schema, before_bytes = (
        preserved_rows(path, version),
        stored_schema(path),
        path.read_bytes(),
    )
    with pytest.raises(LocalStoreUnavailable):
        with FailedBootstrapStore(path).transaction():
            pytest.fail("The failed preserving bootstrap was accepted")
    assert stored_version(path) == version
    assert preserved_rows(path, version) == before_rows and stored_schema(path) == before_schema
    assert path.read_bytes() == before_bytes
    assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("version", [1, 2, 3])
def test_concurrent_prior_generation_users_upgrade_once_without_replaying_rows(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "competing-v4.sqlite3"
    frozen_file(path, version)
    before = preserved_rows(path, version)
    ready = Barrier(2)

    def use_risk() -> bool:
        ready.wait(3)
        with SQLiteLocalRiskStore(path).transaction() as transaction:
            return transaction.get_session(DIGEST) is not None

    def use_portfolio() -> bool:
        ready.wait(3)
        with SQLiteLocalPortfolioStore(path).transaction() as transaction:
            return transaction.get_session(DIGEST) is not None

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(use_risk), pool.submit(use_portfolio)
        assert first.result(timeout=6) and second.result(timeout=6)
    assert stored_version(path) == 4
    assert preserved_rows(path, version) == before
    assert NEW_TABLES <= {row[0] for row in stored_schema(path)}


@pytest.mark.parametrize("change", ["future", "foreign-marker", "foreign-table", "missing-trigger"])
def test_future_foreign_and_partial_schema_remain_byte_identical_before_wal(
    tmp_path: Path, change: str
) -> None:
    path = tmp_path / "not-owned.sqlite3"
    frozen_file(path, 3)
    with closing(sqlite3.connect(path)) as connection:
        if change == "future":
            connection.execute("UPDATE schema_metadata SET version=5")
        elif change == "foreign-marker":
            connection.execute("PRAGMA application_id=195")
        elif change == "foreign-table":
            connection.execute("CREATE TABLE sqliteXforeign(value TEXT)")
        else:
            connection.execute("DROP TRIGGER local_consent_no_delete")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("A future, foreign or incomplete schema was accepted")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()
