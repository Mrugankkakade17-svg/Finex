"""Shared synchronous PostgreSQL transaction infrastructure for local stores."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generic, TypeVar
from urllib.parse import urlparse, urlunparse

import psycopg
from psycopg.rows import DictRow, dict_row

from app.domain.local_application import (
    ConsentRecord,
    LocalSession,
    LocalStoreUnavailable,
    LocalUser,
    OnboardingRecord,
)
from app.ports.local_authorization import AuthorizationTransaction

TransactionT = TypeVar("TransactionT", bound=AuthorizationTransaction)
PostgresConnection = psycopg.Connection[DictRow]


def postgres_dsn(database_url: str) -> str:
    parsed = urlparse(database_url.strip())
    if parsed.scheme not in {
        "postgres",
        "postgresql",
        "postgresql+psycopg",
        "postgresql+asyncpg",
    }:
        raise ValueError("APP_DATABASE_URL must be a PostgreSQL URL.")
    normalized = parsed._replace(scheme="postgresql")
    if normalized.hostname == "localhost":
        netloc = normalized.netloc.replace("localhost", "127.0.0.1")
        normalized = normalized._replace(netloc=netloc)
    if normalized.query == "ssl=require":
        normalized = normalized._replace(query="sslmode=require")
    return urlunparse(normalized)


def stored_text(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("Persisted PostgreSQL text has an invalid type.")
    return value


def stored_integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("Persisted PostgreSQL integer has an invalid type.")
    return value


def stored_time(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise ValueError("Persisted PostgreSQL time has an invalid type.")
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("Persisted PostgreSQL time must be UTC-aware.")
    return parsed


SCHEMA_STATEMENTS = (
    "CREATE SCHEMA IF NOT EXISTS finex",
    """CREATE TABLE IF NOT EXISTS finex.local_users (
        user_id TEXT PRIMARY KEY, alias TEXT NOT NULL UNIQUE, active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_sessions (
        digest TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_onboarding (
        user_id TEXT PRIMARY KEY REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        profile_schema_version TEXT NOT NULL, display_name TEXT, experience_level TEXT,
        updated_at TIMESTAMPTZ, completed_at TIMESTAMPTZ
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_consent_events (
        event_id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        version TEXT NOT NULL, accepted BOOLEAN NOT NULL, recorded_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_risk_drafts (
        user_id TEXT PRIMARY KEY REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        questionnaire_id TEXT NOT NULL, questionnaire_version TEXT NOT NULL,
        answers_json TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_risk_assessments (
        sequence BIGSERIAL PRIMARY KEY, assessment_id TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL, request_fingerprint TEXT NOT NULL,
        document_json TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL, UNIQUE(user_id,idempotency_key)
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_manual_portfolios (
        portfolio_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        name TEXT NOT NULL, description TEXT, currency TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE(user_id,portfolio_id)
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_manual_holdings (
        holding_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, portfolio_id TEXT NOT NULL,
        instrument_id TEXT NOT NULL, quantity_micro_units BIGINT NOT NULL,
        average_cost_units BIGINT NOT NULL, currency TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        FOREIGN KEY(user_id,portfolio_id)
            REFERENCES finex.local_manual_portfolios(user_id,portfolio_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_watchlists (
        watchlist_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        name TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE(watchlist_id,user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_watchlist_items (
        user_id TEXT NOT NULL, watchlist_id TEXT NOT NULL,
        instrument_id TEXT NOT NULL, added_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY(watchlist_id,instrument_id),
        FOREIGN KEY(watchlist_id,user_id)
            REFERENCES finex.local_watchlists(watchlist_id,user_id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_paper_accounts (
        account_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES finex.local_users(user_id) ON DELETE CASCADE,
        opening_ledger_id TEXT NOT NULL, currency TEXT NOT NULL,
        opening_cash_cents BIGINT NOT NULL, cash_balance_cents BIGINT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE(account_id,user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS finex.local_paper_ledger (
        ledger_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, account_id TEXT NOT NULL,
        entry_type TEXT NOT NULL, cash_delta_cents BIGINT NOT NULL,
        cash_after_cents BIGINT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL, sequence BIGSERIAL,
        FOREIGN KEY(account_id,user_id)
            REFERENCES finex.local_paper_accounts(account_id,user_id) ON DELETE CASCADE
    )""",
)


class PostgresAuthorizationTransaction:
    def __init__(self, connection: PostgresConnection) -> None:
        self._connection = connection

    def get_session(self, digest: str) -> LocalSession | None:
        row = self._connection.execute(
            """SELECT s.digest,s.user_id,s.expires_at,s.revoked_at,u.alias
               FROM finex.local_sessions s JOIN finex.local_users u ON u.user_id=s.user_id
               WHERE s.digest=%s AND u.active=TRUE""",
            (digest,),
        ).fetchone()
        if row is None:
            return None
        return LocalSession(
            stored_text(row["digest"]),
            LocalUser(stored_text(row["user_id"]), stored_text(row["alias"])),
            stored_time(row["expires_at"]),
            stored_time(row["revoked_at"]) if row["revoked_at"] is not None else None,
        )

    def get_onboarding(self, user_id: str) -> OnboardingRecord:
        row = self._connection.execute(
            "SELECT * FROM finex.local_onboarding WHERE user_id=%s", (user_id,)
        ).fetchone()
        if row is None:
            raise LocalStoreUnavailable()
        return OnboardingRecord(
            stored_text(row["user_id"]),
            stored_text(row["profile_schema_version"]),
            row["display_name"],
            row["experience_level"],
            stored_time(row["updated_at"]) if row["updated_at"] is not None else None,
            stored_time(row["completed_at"]) if row["completed_at"] is not None else None,
        )

    def latest_consent(self, user_id: str) -> ConsentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_consent_events WHERE user_id=%s "
            "ORDER BY event_id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        accepted = row["accepted"]
        if not isinstance(accepted, bool):
            raise ValueError("Persisted PostgreSQL consent is invalid.")
        return ConsentRecord(
            stored_integer(row["event_id"]),
            stored_text(row["user_id"]),
            stored_text(row["version"]),
            accepted,
            stored_time(row["recorded_at"]),
        )


class PostgresTransactionStore(Generic[TransactionT]):
    def __init__(
        self, database_url: str, factory: Callable[[PostgresConnection], TransactionT]
    ) -> None:
        self._dsn = postgres_dsn(database_url)
        self._factory = factory

    def _connect(self) -> PostgresConnection:
        connection = psycopg.connect(self._dsn, row_factory=dict_row)
        try:
            with connection.cursor() as cursor:
                for statement in SCHEMA_STATEMENTS:
                    cursor.execute(statement)
            connection.commit()
            return connection
        except BaseException:
            connection.rollback()
            connection.close()
            raise

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[TransactionT]:
        connection: PostgresConnection | None = None
        try:
            connection = self._connect()
            connection.execute("BEGIN")
            yield self._factory(connection)
            connection.commit()
        except (psycopg.Error, OSError, ValueError) as exc:
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
