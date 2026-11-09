"""One native schema owner: exact inspection and preserving forward migrations."""

import re
import sqlite3
from collections.abc import Callable

from app.domain.local_application import LocalStoreUnavailable

SCHEMA_VERSION = 4
S1_SCHEMA_STATEMENTS = (
    "CREATE TABLE schema_metadata (version INTEGER NOT NULL CHECK(version > 0))",
    """CREATE TABLE local_users (
        user_id TEXT PRIMARY KEY, alias TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL CHECK(active IN (0,1)), created_at TEXT NOT NULL
    )""",
    """CREATE TABLE local_sessions (
        digest TEXT PRIMARY KEY CHECK(length(digest)=64),
        user_id TEXT NOT NULL REFERENCES local_users(user_id),
        expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL
    )""",
    "CREATE INDEX local_session_owner ON local_sessions(user_id)",
    """CREATE TABLE local_onboarding (
        user_id TEXT PRIMARY KEY REFERENCES local_users(user_id),
        profile_schema_version TEXT NOT NULL, display_name TEXT,
        experience_level TEXT CHECK(experience_level IN ('beginner','intermediate','advanced')),
        updated_at TEXT, completed_at TEXT
    )""",
    """CREATE TABLE local_consent_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL REFERENCES local_users(user_id), version TEXT NOT NULL,
        accepted INTEGER NOT NULL CHECK(accepted IN (0,1)), recorded_at TEXT NOT NULL
    )""",
    "CREATE INDEX local_consent_owner ON local_consent_events(user_id,event_id)",
    """CREATE TRIGGER local_consent_no_update BEFORE UPDATE ON local_consent_events
        BEGIN SELECT RAISE(ABORT, 'Consent history is immutable'); END""",
    """CREATE TRIGGER local_consent_no_delete BEFORE DELETE ON local_consent_events
        BEGIN SELECT RAISE(ABORT, 'Consent history is immutable'); END""",
)
RISK_SCHEMA_STATEMENTS = (
    """CREATE TABLE local_risk_drafts (
        user_id TEXT PRIMARY KEY NOT NULL REFERENCES local_users(user_id),
        questionnaire_id TEXT NOT NULL, questionnaire_version TEXT NOT NULL,
        answers_json TEXT NOT NULL, updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE local_risk_assessments (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT,
        assessment_id TEXT NOT NULL UNIQUE,
        user_id TEXT NOT NULL REFERENCES local_users(user_id),
        idempotency_key TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL CHECK(length(request_fingerprint)=64
            AND request_fingerprint NOT GLOB '*[^0-9a-f]*'),
        document_json TEXT NOT NULL, created_at TEXT NOT NULL,
        UNIQUE(user_id,idempotency_key)
    )""",
    "CREATE INDEX local_risk_assessment_owner ON local_risk_assessments(user_id,sequence)",
    """CREATE TRIGGER local_risk_assessment_no_update BEFORE UPDATE ON local_risk_assessments
        BEGIN SELECT RAISE(ABORT, 'Risk history is immutable'); END""",
    """CREATE TRIGGER local_risk_assessment_no_delete BEFORE DELETE ON local_risk_assessments
        BEGIN SELECT RAISE(ABORT, 'Risk history is immutable'); END""",
)
PORTFOLIO_SCHEMA_STATEMENTS = (
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
FOUNDATION_SCHEMA_STATEMENTS = (
    """CREATE TABLE local_watchlists (
        watchlist_id TEXT PRIMARY KEY NOT NULL,
        user_id TEXT NOT NULL REFERENCES local_users(user_id),
        name TEXT NOT NULL CHECK(typeof(name)='text' AND length(name) BETWEEN 1 AND 100),
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        UNIQUE(user_id,watchlist_id)
    )""",
    "CREATE INDEX local_watchlist_owner ON local_watchlists(user_id,created_at,watchlist_id)",
    """CREATE TABLE local_watchlist_items (
        user_id TEXT NOT NULL, watchlist_id TEXT NOT NULL, instrument_id TEXT NOT NULL,
        added_at TEXT NOT NULL,
        PRIMARY KEY(user_id,watchlist_id,instrument_id),
        FOREIGN KEY(user_id,watchlist_id) REFERENCES local_watchlists(user_id,watchlist_id)
            ON DELETE CASCADE
    )""",
    "CREATE INDEX local_watchlist_item_owner ON "
    "local_watchlist_items(user_id,watchlist_id,added_at,instrument_id)",
    """CREATE TABLE local_paper_accounts (
        account_id TEXT PRIMARY KEY NOT NULL,
        user_id TEXT NOT NULL UNIQUE REFERENCES local_users(user_id),
        opening_ledger_id TEXT NOT NULL UNIQUE,
        currency TEXT NOT NULL CHECK(currency='USD'),
        opening_cash_cents INTEGER NOT NULL CHECK(typeof(opening_cash_cents)='integer'
            AND opening_cash_cents=1000000),
        cash_balance_cents INTEGER NOT NULL CHECK(typeof(cash_balance_cents)='integer'
            AND cash_balance_cents BETWEEN 0 AND 10000000000000000),
        created_at TEXT NOT NULL,
        UNIQUE(user_id,account_id), UNIQUE(user_id,account_id,opening_ledger_id),
        FOREIGN KEY(user_id,account_id,opening_ledger_id)
            REFERENCES local_paper_ledger(user_id,account_id,ledger_id)
            DEFERRABLE INITIALLY DEFERRED
    )""",
    """CREATE TABLE local_paper_ledger (
        sequence INTEGER PRIMARY KEY AUTOINCREMENT
            CHECK(sequence BETWEEN 1 AND 9007199254740991),
        ledger_id TEXT NOT NULL UNIQUE, user_id TEXT NOT NULL, account_id TEXT NOT NULL,
        entry_type TEXT NOT NULL CHECK(entry_type='OPENING'),
        cash_delta_cents INTEGER NOT NULL CHECK(typeof(cash_delta_cents)='integer'
            AND cash_delta_cents=1000000),
        cash_after_cents INTEGER NOT NULL CHECK(typeof(cash_after_cents)='integer'
            AND cash_after_cents=1000000),
        instrument_id TEXT CHECK(instrument_id IS NULL),
        quantity_delta_micro_units INTEGER CHECK(quantity_delta_micro_units IS NULL),
        position_after_micro_units INTEGER CHECK(position_after_micro_units IS NULL),
        order_id TEXT CHECK(order_id IS NULL), trade_id TEXT CHECK(trade_id IS NULL),
        corrects_ledger_id TEXT CHECK(corrects_ledger_id IS NULL), created_at TEXT NOT NULL,
        UNIQUE(user_id,account_id), UNIQUE(user_id,account_id,ledger_id),
        FOREIGN KEY(user_id,account_id) REFERENCES local_paper_accounts(user_id,account_id),
        FOREIGN KEY(user_id,account_id,ledger_id)
            REFERENCES local_paper_accounts(user_id,account_id,opening_ledger_id)
    )""",
    "CREATE INDEX local_paper_ledger_owner ON local_paper_ledger(user_id,account_id,sequence)",
    """CREATE TRIGGER local_paper_ledger_no_update BEFORE UPDATE ON local_paper_ledger
        BEGIN SELECT RAISE(ABORT, 'Simulated ledger is immutable'); END""",
    """CREATE TRIGGER local_paper_ledger_no_delete BEFORE DELETE ON local_paper_ledger
        BEGIN SELECT RAISE(ABORT, 'Simulated ledger is immutable'); END""",
)
SCHEMA_STATEMENTS = (
    S1_SCHEMA_STATEMENTS
    + RISK_SCHEMA_STATEMENTS
    + PORTFOLIO_SCHEMA_STATEMENTS
    + FOUNDATION_SCHEMA_STATEMENTS
)
SQL_TOKENS = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|\w+|[^\s]")
SQL_OBJECT = re.compile(r"CREATE\s+(TABLE|INDEX|TRIGGER)\s+([a-z_]+)\b", re.IGNORECASE)


def _tokens(statement: str) -> tuple[str, ...]:
    # Ignore formatting/keyword case, but retain string literals exactly: CHECK
    # constraints and immutable-history trigger bodies cannot be weakened.
    return tuple(
        token if token.startswith("'") else token.casefold()
        for token in SQL_TOKENS.findall(statement)
    )


def _expected_objects(statements: tuple[str, ...]) -> dict[str, tuple[str, tuple[str, ...]]]:
    expected: dict[str, tuple[str, tuple[str, ...]]] = {}
    for statement in statements:
        match = SQL_OBJECT.match(statement)
        if match is None:
            raise RuntimeError("The owned schema declaration is invalid.")
        expected[match[2]] = (match[1].lower(), _tokens(statement))
    return expected


EXPECTED_S1_OBJECTS = _expected_objects(S1_SCHEMA_STATEMENTS)
EXPECTED_S2_OBJECTS = _expected_objects(S1_SCHEMA_STATEMENTS + RISK_SCHEMA_STATEMENTS)
EXPECTED_S3_OBJECTS = _expected_objects(
    S1_SCHEMA_STATEMENTS + RISK_SCHEMA_STATEMENTS + PORTFOLIO_SCHEMA_STATEMENTS
)
EXPECTED_S4_OBJECTS = _expected_objects(SCHEMA_STATEMENTS)


def inspect_schema(connection: sqlite3.Connection) -> int:
    """Read only; reject foreign, future and incomplete files before any writes."""
    # Every accepted generation uses only schema_metadata as its version owner.
    # Explicit foreign PRAGMA markers remain foreign even when table names and
    # definitions happen to match; do not migrate or change their journal.
    if (
        connection.execute("PRAGMA user_version").fetchone()[0] != 0
        or connection.execute("PRAGMA application_id").fetchone()[0] != 0
    ):
        raise LocalStoreUnavailable()
    objects: dict[str, tuple[str, tuple[str, ...]]] = {}
    for row in connection.execute(
        "SELECT name,type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'"
    ):
        name, kind, statement = row
        if not isinstance(name, str) or not isinstance(kind, str) or not isinstance(statement, str):
            raise LocalStoreUnavailable()
        objects[name] = (kind, _tokens(statement))
    if not objects:
        return 0
    if objects.get("schema_metadata") != EXPECTED_S1_OBJECTS["schema_metadata"]:
        raise LocalStoreUnavailable()
    versions = connection.execute("SELECT version FROM schema_metadata").fetchall()
    if len(versions) != 1:
        raise LocalStoreUnavailable()
    version: object = versions[0][0]
    if not isinstance(version, int) or version not in (1, 2, 3, SCHEMA_VERSION):
        raise LocalStoreUnavailable()
    expected = {
        1: EXPECTED_S1_OBJECTS,
        2: EXPECTED_S2_OBJECTS,
        3: EXPECTED_S3_OBJECTS,
        4: EXPECTED_S4_OBJECTS,
    }[version]
    if objects != expected:
        raise LocalStoreUnavailable()
    return version


def bootstrap_schema(
    connection: sqlite3.Connection, before_commit: Callable[[sqlite3.Connection], None]
) -> None:
    """Creation/migration commits before the separate domain unit of work."""
    version = inspect_schema(connection)
    if version == SCHEMA_VERSION:
        return
    connection.execute("BEGIN IMMEDIATE")
    try:
        # A competing creator/migrator may have committed while this lock waited.
        version = inspect_schema(connection)
        if version == 0:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            before_commit(connection)
            connection.execute("INSERT INTO schema_metadata(version) VALUES(?)", (SCHEMA_VERSION,))
        elif version in (1, 2, 3):
            additional = {
                1: RISK_SCHEMA_STATEMENTS
                + PORTFOLIO_SCHEMA_STATEMENTS
                + FOUNDATION_SCHEMA_STATEMENTS,
                2: PORTFOLIO_SCHEMA_STATEMENTS + FOUNDATION_SCHEMA_STATEMENTS,
                3: FOUNDATION_SCHEMA_STATEMENTS,
            }[version]
            for statement in additional:
                connection.execute(statement)
            before_commit(connection)
            changed = connection.execute(
                "UPDATE schema_metadata SET version=? WHERE version=?", (SCHEMA_VERSION, version)
            )
            if changed.rowcount != 1:
                raise LocalStoreUnavailable()
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
    if inspect_schema(connection) != SCHEMA_VERSION:
        raise LocalStoreUnavailable()
