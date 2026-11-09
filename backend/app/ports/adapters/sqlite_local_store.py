"""Typed native transaction factory and only the three shared authorization reads."""

import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from typing import Generic, TypeVar

from app.domain.local_application import (
    ConsentRecord,
    LocalSession,
    LocalStoreUnavailable,
    LocalUser,
    OnboardingRecord,
)
from app.ports.adapters.sqlite_local_schema import SCHEMA_VERSION, bootstrap_schema, inspect_schema
from app.ports.local_authorization import AuthorizationTransaction

TransactionT = TypeVar("TransactionT", bound=AuthorizationTransaction)


def stored_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Persisted local text has an invalid type.")
    return value


def optional_text(value: object) -> str | None:
    return stored_text(value) if value is not None else None


def stored_integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Persisted local integer has an invalid type.")
    return value


def stored_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(stored_text(value))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Persisted local time must be UTC-aware.")
    return parsed


def optional_time(value: object) -> datetime | None:
    return stored_time(value) if value is not None else None


def utc_text(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("The local record time must be UTC-aware.")
    return value.isoformat()


class SQLiteAuthorizationTransaction:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def get_session(self, digest: str) -> LocalSession | None:
        row = self._connection.execute(
            """SELECT s.digest,s.user_id,s.expires_at,s.revoked_at,u.alias
            FROM local_sessions s JOIN local_users u ON u.user_id=s.user_id
            WHERE s.digest=? AND u.active=1""",
            (digest,),
        ).fetchone()
        if row is None:
            return None
        return LocalSession(
            stored_text(row["digest"]),
            LocalUser(stored_text(row["user_id"]), stored_text(row["alias"])),
            stored_time(row["expires_at"]),
            optional_time(row["revoked_at"]),
        )

    def get_onboarding(self, user_id: str) -> OnboardingRecord:
        row = self._connection.execute(
            "SELECT * FROM local_onboarding WHERE user_id=?", (user_id,)
        ).fetchone()
        if row is None:
            raise LocalStoreUnavailable()
        return OnboardingRecord(
            stored_text(row["user_id"]),
            stored_text(row["profile_schema_version"]),
            optional_text(row["display_name"]),
            optional_text(row["experience_level"]),
            optional_time(row["updated_at"]),
            optional_time(row["completed_at"]),
        )

    def latest_consent(self, user_id: str) -> ConsentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_consent_events WHERE user_id=? ORDER BY event_id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        accepted = stored_integer(row["accepted"])
        if accepted not in (0, 1):
            raise ValueError("Persisted local consent is invalid.")
        return ConsentRecord(
            stored_integer(row["event_id"]),
            stored_text(row["user_id"]),
            stored_text(row["version"]),
            bool(accepted),
            stored_time(row["recorded_at"]),
        )


class SQLiteTransactionStore(Generic[TransactionT]):
    """Constructing a store performs no database/filesystem operation."""

    def __init__(self, path: Path, factory: Callable[[sqlite3.Connection], TransactionT]) -> None:
        self._path = path
        self._factory = factory

    @staticmethod
    def _schema_ready(connection: sqlite3.Connection) -> bool:
        return inspect_schema(connection) == SCHEMA_VERSION

    def _before_schema_commit(self, connection: sqlite3.Connection) -> None:
        """Protected migration-fault seam, separate from domain mutation commits."""

    def _enable_wal(self, connection: sqlite3.Connection) -> None:
        """Retry only recognized bootstrap journal contention within one 3s budget.

        SQLite journal conversion can return BUSY immediately when concurrent
        first users upgrade shared locks. No schema DDL or domain unit is
        replayed here; each journal attempt rechecks the strict owned schema.
        """
        deadline = monotonic() + 3
        try:
            while True:
                if not self._schema_ready(connection):
                    raise LocalStoreUnavailable()
                remaining = deadline - monotonic()
                if remaining <= 0:
                    raise LocalStoreUnavailable()
                timeout_ms = min(3000, max(1, int(remaining * 1000)))
                connection.execute(f"PRAGMA busy_timeout={timeout_ms}")
                try:
                    mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()
                    if mode is None or mode[0] != "wal":
                        raise LocalStoreUnavailable()
                    return
                except sqlite3.OperationalError as error:
                    # SQLite supplies this public error code for native failures;
                    # a non-native/uncategorized exception is never retried.
                    try:
                        code = error.sqlite_errorcode
                    except AttributeError:
                        raise error
                    if code & 0xFF not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                        raise
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        raise
                    sleep(min(0.01, remaining))
        finally:
            connection.execute("PRAGMA busy_timeout=3000")

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self._path, timeout=3, isolation_level=None)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA busy_timeout=3000")
            bootstrap_schema(connection, self._before_schema_commit)
            # Never change the journal of a foreign/future/incomplete schema or a
            # migration that failed before its metadata commit.
            self._enable_wal(connection)
            return connection
        except BaseException:
            connection.rollback()
            connection.close()
            raise

    def _before_commit(self, connection: sqlite3.Connection) -> None:
        """Preserved domain failure/race seam; normal commits have no hook."""

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[TransactionT]:
        connection: sqlite3.Connection | None = None
        try:
            connection = self._connect()
            if not write:
                connection.execute("PRAGMA query_only=ON")
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            if not self._schema_ready(connection):
                raise LocalStoreUnavailable()
            yield self._factory(connection)
            if write:
                self._before_commit(connection)
            connection.commit()
        except (sqlite3.Error, OSError, ValueError) as exc:
            if connection is not None:
                connection.rollback()
            raise LocalStoreUnavailable() from exc
        except BaseException:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            if connection is not None:
                connection.close()
