"""Current shared migration behavior against frozen real version-1/2 SQLite files.

These declarations intentionally do not import the current schema statements.
The fixtures contain synthetic owned records, never a developer database/token.
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
from app.ports.adapters.sqlite_local_schema import PORTFOLIO_SCHEMA_STATEMENTS, SCHEMA_STATEMENTS

V1_DDL = (
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
V2_ADDED_DDL = (
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
S1_TABLES = ("local_users", "local_sessions", "local_onboarding", "local_consent_events")
S2_TABLES = S1_TABLES + ("local_risk_drafts", "local_risk_assessments")
OWNER = "synthetic-owner-a"
DIGEST = "a" * 64
STAMP = "2026-10-11T12:00:00+00:00"


def frozen_owned_file(path: Path, version: int) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for statement in V1_DDL + (V2_ADDED_DDL if version == 2 else ()):
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES(?)", (version,))
        connection.execute("INSERT INTO local_users VALUES(?,?,1,?)", (OWNER, "learner-a", STAMP))
        connection.execute(
            "INSERT INTO local_sessions VALUES(?,?,?,NULL,?)",
            (DIGEST, OWNER, "2026-10-11T12:30:00+00:00", STAMP),
        )
        connection.execute(
            "INSERT INTO local_onboarding VALUES(?,'profile.v1',?,'beginner',?,?)",
            (OWNER, "Synthetic learner", STAMP, STAMP),
        )
        for decision in (1, 0, 1):
            connection.execute(
                "INSERT INTO local_consent_events(user_id,version,accepted,recorded_at) "
                "VALUES(?,'consent.v1',?,?)",
                (OWNER, decision, STAMP),
            )
        if version == 2:
            connection.execute(
                "INSERT INTO local_risk_drafts VALUES(?,'risk_questionnaire_v1','v1',?,?)",
                (OWNER, '[{"question_id":"W1","answer_code":"W1_B"}]', STAMP),
            )
            for number in (1, 2):
                connection.execute(
                    "INSERT INTO local_risk_assessments(assessment_id,user_id,idempotency_key,"
                    "request_fingerprint,document_json,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        f"00000000-0000-4000-8000-{number:012d}",
                        OWNER,
                        f"10000000-0000-4000-8000-{number:012d}",
                        str(number) * 64,
                        '{"synthetic_sql_fixture":"immutable opaque document"}',
                        STAMP,
                    ),
                )
        connection.commit()


def stored_rows(path: Path, version: int) -> dict[str, list[tuple[object, ...]]]:
    with closing(sqlite3.connect(path)) as connection:
        return {
            name: list(connection.execute(f"SELECT * FROM {name} ORDER BY rowid"))
            for name in (S2_TABLES if version == 2 else S1_TABLES) + ("sqlite_sequence",)
        }


def stored_schema(path: Path) -> list[tuple[object, ...]]:
    with closing(sqlite3.connect(path)) as connection:
        return list(
            connection.execute(
                "SELECT name,type,sql FROM sqlite_master WHERE name NOT GLOB 'sqlite_*' "
                "ORDER BY name"
            )
        )


def stored_version(path: Path) -> int:
    with closing(sqlite3.connect(path)) as connection:
        value = connection.execute("SELECT version FROM schema_metadata").fetchone()[0]
        assert type(value) is int
        return value


def test_fresh_s1_use_creates_schema_four_and_manual_tables(tmp_path: Path) -> None:
    path = tmp_path / "fresh-v3.sqlite3"
    with SQLiteLocalApplicationStore(path).transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None
    assert stored_version(path) == 4
    names = {row[0] for row in stored_schema(path)}
    assert {"local_manual_portfolios", "local_manual_holdings"}.issubset(names)


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize(
    "store_class", [SQLiteLocalApplicationStore, SQLiteLocalRiskStore, SQLiteLocalPortfolioStore]
)
def test_atomic_forward_migration_preserves_frozen_prior_rows_objects_and_sequences(
    tmp_path: Path,
    version: int,
    store_class: (
        type[SQLiteLocalApplicationStore]
        | type[SQLiteLocalRiskStore]
        | type[SQLiteLocalPortfolioStore]
    ),
) -> None:
    path = tmp_path / "forward-v3.sqlite3"
    frozen_owned_file(path, version)
    rows_before = stored_rows(path, version)
    objects_before = stored_schema(path)
    with store_class(path).transaction() as transaction:
        saved = transaction.get_session(DIGEST)
        assert saved is not None and saved.user.id == OWNER
        assert transaction.get_onboarding(OWNER).display_name == "Synthetic learner"
    assert stored_version(path) == 4
    rows_after = stored_rows(path, version)
    # Version1 gains an empty risk AUTOINCREMENT entry only after its first insert.
    assert rows_after == rows_before
    assert set(objects_before).issubset(stored_schema(path))
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_manual_portfolios").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM local_manual_holdings").fetchone()[0] == 0
        statements = (
            "UPDATE local_consent_events SET accepted=0",
            "DELETE FROM local_consent_events",
        )
        if version == 2:
            statements += (
                "UPDATE local_risk_assessments SET document_json='{}'",
                "DELETE FROM local_risk_assessments",
            )
        for statement in statements:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)


class FailedSchemaCommitStore(SQLiteLocalApplicationStore):
    def _before_schema_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic preserving bootstrap rollback")


@pytest.mark.parametrize("version", [0, 1, 2])
def test_bootstrap_failure_preserves_exact_previous_schema_rows_and_journal(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "migration-rollback-v3.sqlite3"
    if version:
        frozen_owned_file(path, version)
    objects_before = stored_schema(path)
    rows_before = stored_rows(path, version) if version else None
    with pytest.raises(LocalStoreUnavailable):
        with FailedSchemaCommitStore(path).transaction():
            pytest.fail("A failed bootstrap was accepted")
    assert stored_schema(path) == objects_before
    if version:
        assert stored_version(path) == version
        assert stored_rows(path, version) == rows_before
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert not path.with_name(path.name + "-wal").exists()
    with SQLiteLocalRiskStore(path).transaction() as transaction:
        assert (transaction.get_risk_draft(OWNER) is not None) == (version == 2)
    assert stored_version(path) == 4


@pytest.mark.parametrize("version", [0, 1, 2])
@pytest.mark.parametrize("second_store_class", [SQLiteLocalRiskStore, SQLiteLocalPortfolioStore])
def test_competing_capability_migrators_reinspect_after_real_native_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: int,
    second_store_class: type[SQLiteLocalRiskStore] | type[SQLiteLocalPortfolioStore],
) -> None:
    path = tmp_path / "concurrent-migration-v3.sqlite3"
    if version:
        frozen_owned_file(path, version)
    before = stored_rows(path, version) if version else None
    reached = Barrier(2)
    attempts: list[bool] = []
    original_connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        attempted = False

        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE" and not self.attempted:
                self.attempted = True
                attempts.append(True)
                reached.wait(2)
            return super().execute(sql, parameters)

    def connect(
        database: Path, *, timeout: float = 5, isolation_level: str | None = ""
    ) -> sqlite3.Connection:
        return original_connect(
            database, timeout=timeout, isolation_level=isolation_level, factory=ObservedConnection
        )

    monkeypatch.setattr(sqlite3, "connect", connect)

    def s1_read() -> bool:
        with SQLiteLocalApplicationStore(path).transaction() as transaction:
            return (transaction.get_user_by_alias("learner-a") is not None) == bool(version)

    def domain_read() -> bool:
        with second_store_class(path).transaction() as transaction:
            return (transaction.get_session(DIGEST) is not None) == bool(version)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(s1_read)
        second = pool.submit(domain_read)
        assert first.result(timeout=5)
        assert second.result(timeout=5)
    assert len(attempts) == 2
    monkeypatch.undo()
    assert stored_version(path) == 4
    if version:
        assert stored_rows(path, version) == before


@pytest.mark.parametrize(
    "store_class", [SQLiteLocalApplicationStore, SQLiteLocalRiskStore, SQLiteLocalPortfolioStore]
)
def test_known_current_schema_four_is_accepted_by_all_capabilities(
    tmp_path: Path,
    store_class: (
        type[SQLiteLocalApplicationStore]
        | type[SQLiteLocalRiskStore]
        | type[SQLiteLocalPortfolioStore]
    ),
) -> None:
    path = tmp_path / "valid-v3.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES(4)")
        connection.commit()
    before = stored_schema(path)
    with store_class(path).transaction() as transaction:
        assert transaction.get_session(DIGEST) is None
    assert stored_schema(path) == before
    assert stored_version(path) == 4


@pytest.mark.parametrize(
    "target,old,new",
    [
        ("local_manual_portfolio_owner", None, None),
        ("local_manual_holding_owner", None, None),
        ("local_manual_portfolios", "UNIQUE(user_id,portfolio_id)", "UNIQUE(portfolio_id)"),
        ("local_manual_portfolios", "length(name) BETWEEN 1 AND 100", "length(name)<=101"),
        ("local_manual_portfolios", "length(description)<=500", "length(description)<=501"),
        ("local_manual_holdings", "ON DELETE CASCADE", "ON DELETE NO ACTION"),
        (
            "local_manual_holdings",
            "REFERENCES local_manual_portfolios(user_id,portfolio_id)",
            "REFERENCES local_manual_portfolios(portfolio_id,user_id)",
        ),
        (
            "local_manual_holdings",
            "UNIQUE(user_id,portfolio_id,instrument_id)",
            "UNIQUE(holding_id,instrument_id)",
        ),
        (
            "local_manual_holdings",
            "typeof(quantity_micro_units)='integer'",
            "typeof(quantity_micro_units) IN ('integer','real')",
        ),
        ("local_manual_holdings", "BETWEEN 1 AND 1000000000000", "BETWEEN 0 AND 1000000000001"),
        ("local_manual_holdings", "BETWEEN 0 AND 10000000000", "BETWEEN -1 AND 10000000001"),
    ],
)
def test_missing_or_weakened_current_objects_fail_before_any_journal_change(
    tmp_path: Path, target: str, old: str | None, new: str | None
) -> None:
    path = tmp_path / "malformed-v3.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        for statement in SCHEMA_STATEMENTS:
            if statement.split()[2] == target:
                if old is None or new is None:
                    continue
                assert old in statement
                statement = statement.replace(old, new)
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES(4)")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalPortfolioStore(path).transaction():
            pytest.fail("A malformed owned manual schema was accepted")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


@pytest.mark.parametrize("version", [2, 3, 5, 999])
def test_complete_current_objects_with_wrong_metadata_are_not_relabelled(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "wrong-metadata-v3.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES(?)", (version,))
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalPortfolioStore(path).transaction():
            pytest.fail("An incompatible schema was relabelled as current")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


def test_metadata_three_with_only_frozen_schema_two_is_rejected_before_journal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "false-current-v3.sqlite3"
    frozen_owned_file(path, 2)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("UPDATE schema_metadata SET version=3")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalPortfolioStore(path).transaction():
            pytest.fail("Metadata alone was treated as a complete current schema")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("kind", ["table", "view"])
def test_portfolio_adapter_rejects_foreign_sqlite_like_prefix_before_migration(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "foreign-manual.sqlite3"
    frozen_owned_file(path, 2)
    with closing(sqlite3.connect(path)) as connection:
        statement = (
            "CREATE TABLE sqliteXforeign(value TEXT)"
            if kind == "table"
            else "CREATE VIEW sqliteXforeign AS SELECT alias FROM local_users"
        )
        connection.execute(statement)
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalPortfolioStore(path).transaction():
            pytest.fail("A foreign non-system object was hidden")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("version", [1, 2, 3, 4])
@pytest.mark.parametrize("marker", ["user_version", "application_id"])
def test_exact_known_schema_with_foreign_owner_marker_is_preserved_and_rejected(
    tmp_path: Path, version: int, marker: str
) -> None:
    path = tmp_path / "foreign-owner-marker.sqlite3"
    if version in (1, 2):
        frozen_owned_file(path, version)
    else:
        with closing(sqlite3.connect(path)) as connection:
            statements = (
                V1_DDL + V2_ADDED_DDL + PORTFOLIO_SCHEMA_STATEMENTS
                if version == 3
                else SCHEMA_STATEMENTS
            )
            for statement in statements:
                connection.execute(statement)
            connection.execute("INSERT INTO schema_metadata VALUES(?)", (version,))
            connection.commit()
    with closing(sqlite3.connect(path)) as connection:
        # marker is selected solely from this fixed test-owned parametrization.
        connection.execute(f"PRAGMA {marker}=79")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalPortfolioStore(path).transaction():
            pytest.fail("A foreign owner marker was ignored on a recognized schema")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute(f"PRAGMA {marker}").fetchone()[0] == 79
        assert stored_version(path) == version


@pytest.mark.parametrize("foreign_marker", [False, True])
def test_schema_ownership_is_rechecked_after_native_lock_before_added_ddl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign_marker: bool
) -> None:
    path = tmp_path / "competing-schema-drift.sqlite3"
    frozen_owned_file(path, 2)
    before = stored_schema(path)
    rows_before = stored_rows(path, 2)
    native_connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        attempted = False

        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE" and not self.attempted:
                self.attempted = True
                # A separate native connection changes only a synthetic fixture
                # after initial inspection, before the application's lock.
                with closing(native_connect(path)) as competing:
                    competing.execute(
                        "PRAGMA application_id=79"
                        if foreign_marker
                        else "UPDATE schema_metadata SET version=999"
                    )
                    competing.commit()
            return super().execute(sql, parameters)

    def connect(
        database: Path, *, timeout: float = 5, isolation_level: str | None = ""
    ) -> sqlite3.Connection:
        return native_connect(
            database, timeout=timeout, isolation_level=isolation_level, factory=ObservedConnection
        )

    monkeypatch.setattr(sqlite3, "connect", connect)
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalPortfolioStore(path).transaction():
            pytest.fail("Competing schema ownership drift was ignored")
    monkeypatch.undo()
    assert stored_schema(path) == before
    assert stored_rows(path, 2) == rows_before
    assert stored_version(path) == (2 if foreign_marker else 999)
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("PRAGMA application_id").fetchone()[0] == (
            79 if foreign_marker else 0
        )
    assert not path.with_name(path.name + "-wal").exists()
