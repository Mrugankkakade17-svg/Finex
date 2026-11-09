"""Native adapter metadata, rollback, immutable history and safe failure tests."""

import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.domain.local_application import LocalStoreUnavailable, LocalUser
from app.main import create_app
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.services.local_application_service import LocalApplicationService

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)


def test_store_construction_has_no_filesystem_side_effect(tmp_path: Path) -> None:
    path = tmp_path / "not-yet-created" / "local.sqlite3"
    SQLiteLocalApplicationStore(path)
    assert not path.parent.exists()


def test_future_schema_does_not_change_file_or_journal_mode(tmp_path: Path) -> None:
    path = tmp_path / "future.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE schema_metadata(version INTEGER)")
        connection.execute("INSERT INTO schema_metadata VALUES(999)")
        connection.execute("CREATE TABLE precious_history(value TEXT)")
        connection.execute("INSERT INTO precious_history VALUES('keep synthetic history')")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("Future schema was accepted")
    assert path.read_bytes() == before
    assert not Path(str(path) + "-wal").exists()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("SELECT value FROM precious_history").fetchone()[0]


def test_unrecognized_database_is_not_reset(tmp_path: Path) -> None:
    path = tmp_path / "foreign.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE unrelated(value TEXT)")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("Unrecognized database was accepted")
    assert path.read_bytes() == before


def test_consent_history_cannot_be_modified_or_deleted(tmp_path: Path) -> None:
    path = tmp_path / "immutable.sqlite3"
    store = SQLiteLocalApplicationStore(path)
    with store.transaction(write=True) as transaction:
        transaction.create_user(LocalUser("synthetic-id", "learner-a"), "profile.v1", NOW)
        transaction.append_consent("synthetic-id", "consent.v1", True, NOW)
    with closing(sqlite3.connect(path)) as connection:
        for statement in (
            "UPDATE local_consent_events SET accepted=0",
            "DELETE FROM local_consent_events",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)
        assert connection.execute("SELECT accepted FROM local_consent_events").fetchone()[0] == 1


def test_rollback_and_foreign_keys_are_real(tmp_path: Path) -> None:
    store = SQLiteLocalApplicationStore(tmp_path / "atomic.sqlite3")
    with pytest.raises(RuntimeError):
        with store.transaction(write=True) as transaction:
            transaction.create_user(LocalUser("never-committed", "learner-a"), "profile.v1", NOW)
            raise RuntimeError("A synthetic test failure")
    with store.transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction(write=True) as transaction:
            transaction.append_consent("unknown-owner", "consent.v1", True, NOW)


def test_read_transaction_cannot_accidentally_write(tmp_path: Path) -> None:
    store = SQLiteLocalApplicationStore(tmp_path / "read-only.sqlite3")
    with pytest.raises(LocalStoreUnavailable):
        with store.transaction() as transaction:
            transaction.create_user(
                LocalUser("not-authorized-to-write", "learner-a"), "profile.v1", NOW
            )
    with store.transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None


def test_database_failure_is_a_safe_503(tmp_path: Path) -> None:
    path = tmp_path / "not-a-database.sqlite3"
    path.mkdir()
    client = TestClient(create_app(Settings(local_app_enabled=True, local_db_path=path)))
    response = client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
    assert response.status_code == 503
    assert response.json()["error_code"] == "LOCAL_STORE_UNAVAILABLE"
    assert str(path) not in response.text
    assert "sqlite" not in response.text.lower()


def test_naive_clock_rejected_without_database_creation(tmp_path: Path) -> None:
    path = tmp_path / "naive.sqlite3"
    service = LocalApplicationService(
        SQLiteLocalApplicationStore(path), clock=lambda: datetime(2026, 10, 11, 12)
    )
    with pytest.raises(ValueError, match="UTC-aware"):
        service.login("learner-a")
    assert not path.exists()
