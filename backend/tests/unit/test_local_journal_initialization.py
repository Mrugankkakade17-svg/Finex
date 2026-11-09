"""Narrow safe initialization retries; never retry DDL or domain writes.

The real concurrent creator regression is separate. These fault/clock controls
deterministically exercise retry classification, exhaustion and schema drift.
They never contact an API or read a developer database.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.domain.local_application import LocalStoreUnavailable
from app.ports.adapters import sqlite_local_store
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore


def journal_error(code: int) -> sqlite3.OperationalError:
    error = sqlite3.OperationalError("Synthetic journal initialization failure")
    error.sqlite_errorcode = code
    return error


def observed_connect(
    monkeypatch: pytest.MonkeyPatch, connection_class: type[sqlite3.Connection]
) -> None:
    native_connect = sqlite3.connect

    def connect(
        database: Path, *, timeout: float = 5, isolation_level: str | None = ""
    ) -> sqlite3.Connection:
        return native_connect(
            database, timeout=timeout, isolation_level=isolation_level, factory=connection_class
        )

    monkeypatch.setattr(sqlite3, "connect", connect)


@pytest.mark.parametrize("code", [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED])
def test_recoverable_journal_lock_retries_only_journal_after_committed_bootstrap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    path = tmp_path / "recoverable-journal.sqlite3"
    events: list[str] = []

    class ObservedConnection(sqlite3.Connection):
        attempts = 0

        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE":
                events.append("begin")
            if sql == "PRAGMA journal_mode=WAL":
                events.append("journal")
                self.attempts += 1
                if self.attempts == 1:
                    raise journal_error(code)
            return super().execute(sql, parameters)

    observed_connect(monkeypatch, ObservedConnection)
    with SQLiteLocalApplicationStore(path).transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None
    assert events == ["begin", "journal", "journal"]
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT version FROM schema_metadata").fetchone()[0] == 4
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


@pytest.mark.parametrize("code", [sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED])
def test_journal_busy_exhaustion_stays_within_three_second_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    path = tmp_path / "exhausted-journal.sqlite3"
    budgets: list[int] = []
    events: list[str] = []
    clock = [0.0]

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE":
                events.append("begin")
            if sql.startswith("PRAGMA busy_timeout="):
                budgets.append(int(sql.split("=")[1]))
            if sql == "PRAGMA journal_mode=WAL":
                events.append("journal")
                clock[0] += 1.0  # Simulated one-second native lock wait, not a real sleep.
                raise journal_error(code)
            return super().execute(sql, parameters)

    monkeypatch.setattr(sqlite_local_store, "monotonic", lambda: clock[0], raising=False)
    monkeypatch.setattr(sqlite_local_store, "sleep", lambda seconds: None, raising=False)
    observed_connect(monkeypatch, ObservedConnection)
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("Exhausted journal lock was accepted")
    assert events == ["begin", "journal", "journal", "journal"]
    assert clock[0] == 3.0
    assert budgets == [3000, 3000, 2000, 1000, 3000]
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT version FROM schema_metadata").fetchone()[0] == 4
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


@pytest.mark.parametrize("code", [sqlite3.SQLITE_IOERR, sqlite3.SQLITE_CORRUPT])
def test_nonbusy_journal_failure_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    events: list[str] = []

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "PRAGMA journal_mode=WAL":
                events.append("journal")
                raise journal_error(code)
            return super().execute(sql, parameters)

    observed_connect(monkeypatch, ObservedConnection)
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(tmp_path / "nonbusy-journal.sqlite3").transaction():
            pytest.fail("A nonrecoverable journal error was accepted")
    assert events == ["journal"]


def test_uncategorized_journal_failure_is_not_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "PRAGMA journal_mode=WAL":
                events.append("journal")
                raise sqlite3.OperationalError("Synthetic uncategorized journal failure")
            return super().execute(sql, parameters)

    observed_connect(monkeypatch, ObservedConnection)
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(tmp_path / "uncategorized-journal.sqlite3").transaction():
            pytest.fail("An uncategorized journal error was accepted")
    assert events == ["journal"]


def test_future_schema_drift_is_rechecked_before_a_journal_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "journal-schema-drift.sqlite3"
    events: list[str] = []

    class ObservedConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "PRAGMA journal_mode=WAL":
                events.append("journal")
                if len(events) == 1:
                    # A test-only competing schema change after the safe bootstrap.
                    super().execute("UPDATE schema_metadata SET version=999")
                    raise journal_error(sqlite3.SQLITE_BUSY)
            return super().execute(sql, parameters)

    observed_connect(monkeypatch, ObservedConnection)
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("Future schema drift was accepted")
    assert events == ["journal"]
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT version FROM schema_metadata").fetchone()[0] == 999
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
