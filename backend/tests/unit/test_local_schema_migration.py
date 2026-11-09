"""Behavioral S2 schema RED/GREEN tests against real isolated native SQLite.

The legacy DDL is intentionally frozen here: importing the current schema owner
would turn a preserving version-1 migration into a test of today's new schema.
No credentials, developer database or application router is involved.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier

import pytest

from app.domain.local_application import LocalStoreUnavailable, LocalUser
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)
OWNER = "11111111-1111-4111-8111-111111111111"
DIGEST = "a" * 64
LEGACY_DDL = (
    (
        "schema_metadata",
        "CREATE TABLE schema_metadata (version INTEGER NOT NULL CHECK(version > 0))",
    ),
    (
        "local_users",
        """CREATE TABLE local_users (
        user_id TEXT PRIMARY KEY, alias TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL CHECK(active IN (0,1)), created_at TEXT NOT NULL
    )""",
    ),
    (
        "local_sessions",
        """CREATE TABLE local_sessions (
        digest TEXT PRIMARY KEY CHECK(length(digest)=64),
        user_id TEXT NOT NULL REFERENCES local_users(user_id),
        expires_at TEXT NOT NULL, revoked_at TEXT, created_at TEXT NOT NULL
    )""",
    ),
    ("local_session_owner", "CREATE INDEX local_session_owner ON local_sessions(user_id)"),
    (
        "local_onboarding",
        """CREATE TABLE local_onboarding (
        user_id TEXT PRIMARY KEY REFERENCES local_users(user_id),
        profile_schema_version TEXT NOT NULL, display_name TEXT,
        experience_level TEXT CHECK(experience_level IN ('beginner','intermediate','advanced')),
        updated_at TEXT, completed_at TEXT
    )""",
    ),
    (
        "local_consent_events",
        """CREATE TABLE local_consent_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL REFERENCES local_users(user_id), version TEXT NOT NULL,
        accepted INTEGER NOT NULL CHECK(accepted IN (0,1)), recorded_at TEXT NOT NULL
    )""",
    ),
    (
        "local_consent_owner",
        "CREATE INDEX local_consent_owner ON local_consent_events(user_id,event_id)",
    ),
    (
        "local_consent_no_update",
        """CREATE TRIGGER local_consent_no_update BEFORE UPDATE ON local_consent_events
        BEGIN SELECT RAISE(ABORT, 'Consent history is immutable'); END""",
    ),
    (
        "local_consent_no_delete",
        """CREATE TRIGGER local_consent_no_delete BEFORE DELETE ON local_consent_events
        BEGIN SELECT RAISE(ABORT, 'Consent history is immutable'); END""",
    ),
)
LEGACY_TABLES = ("local_users", "local_sessions", "local_onboarding", "local_consent_events")
# Keep the accepted schema-2 shape frozen rather than importing today's full
# declaration, which also contains the forward schema-3 portfolio objects.
LEGACY_RISK_DDL = (
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


def legacy_file(
    path: Path,
    *,
    omit: str | None = None,
    version: int = 1,
    replacement: tuple[str, str] | None = None,
) -> None:
    with closing(sqlite3.connect(path)) as connection:
        for name, statement in LEGACY_DDL:
            if name != omit:
                connection.execute(
                    replacement[1] if replacement and replacement[0] == name else statement
                )
        connection.execute("INSERT INTO schema_metadata(version) VALUES(?)", (version,))
        connection.execute(
            "INSERT INTO local_users VALUES(?,?,1,?)", (OWNER, "learner-a", NOW.isoformat())
        )
        connection.execute(
            "INSERT INTO local_sessions VALUES(?,?,?,NULL,?)",
            (DIGEST, OWNER, "2026-10-11T12:30:00+00:00", NOW.isoformat()),
        )
        if omit != "local_onboarding":
            connection.execute(
                "INSERT INTO local_onboarding VALUES(?,'profile.v1',?,?,?,?)",
                (OWNER, "Synthetic learner", "intermediate", NOW.isoformat(), NOW.isoformat()),
            )
        for accepted in (1, 0, 1):
            connection.execute(
                "INSERT INTO local_consent_events(user_id,version,accepted,recorded_at) "
                "VALUES(?,'consent.v1',?,?)",
                (OWNER, accepted, NOW.isoformat()),
            )
        connection.commit()


def version_of(path: Path) -> int:
    with closing(sqlite3.connect(path)) as connection:
        value = connection.execute("SELECT version FROM schema_metadata").fetchone()[0]
        assert isinstance(value, int)
        return value


def legacy_rows(path: Path) -> dict[str, list[tuple[object, ...]]]:
    with closing(sqlite3.connect(path)) as connection:
        return {
            table: list(connection.execute(f"SELECT * FROM {table} ORDER BY rowid"))
            for table in LEGACY_TABLES
        }


def test_fresh_s1_use_bootstraps_latest_shared_schema_and_risk_tables(tmp_path: Path) -> None:
    path = tmp_path / "fresh-owned.sqlite3"
    with SQLiteLocalApplicationStore(path).transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None
    assert version_of(path) == 4
    with closing(sqlite3.connect(path)) as connection:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"local_risk_drafts", "local_risk_assessments"}.issubset(names)


def test_first_read_migrates_real_schema_one_without_resetting_s1_records(tmp_path: Path) -> None:
    path = tmp_path / "preserving-migration.sqlite3"
    legacy_file(path)
    before = legacy_rows(path)
    with SQLiteLocalApplicationStore(path).transaction() as transaction:
        session = transaction.get_session(DIGEST)
        assert session is not None
        assert session.user.id == OWNER
        assert transaction.get_onboarding(OWNER).completed_at == NOW
        consent = transaction.latest_consent(OWNER)
        assert consent is not None and consent.event_id == 3 and consent.accepted
    assert version_of(path) == 4
    assert legacy_rows(path) == before
    with closing(sqlite3.connect(path)) as connection:
        for statement in (
            "UPDATE local_consent_events SET accepted=0",
            "DELETE FROM local_consent_events",
        ):
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(statement)


@pytest.mark.parametrize(
    "missing", ["local_onboarding", "local_session_owner", "local_consent_no_delete"]
)
def test_incomplete_owned_schema_is_rejected_before_journal_or_file_changes(
    tmp_path: Path, missing: str
) -> None:
    path = tmp_path / "incomplete-owned.sqlite3"
    legacy_file(path, omit=missing)
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("Missing required owned schema was accepted")
    unchanged = path.read_bytes() == before
    assert unchanged
    assert not path.with_name(path.name + "-wal").exists()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_bootstrap_commits_separately_before_a_domain_write_rolls_back(tmp_path: Path) -> None:
    path = tmp_path / "separate-bootstrap.sqlite3"
    with pytest.raises(RuntimeError, match="Synthetic domain rollback"):
        with SQLiteLocalApplicationStore(path).transaction(write=True) as transaction:
            transaction.create_user(LocalUser(OWNER, "learner-a"), "profile.v1", NOW)
            raise RuntimeError("Synthetic domain rollback")
    assert version_of(path) == 4
    with SQLiteLocalApplicationStore(path).transaction() as transaction:
        assert transaction.get_user_by_alias("learner-a") is None
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM local_risk_assessments").fetchone()[0] == 0


class MigrationFailureStore(SQLiteLocalApplicationStore):
    def _before_schema_commit(self, connection: sqlite3.Connection) -> None:
        raise sqlite3.OperationalError("Synthetic migration failure before metadata commit")


def test_migration_failure_rolls_back_ddl_and_preserves_version_one(tmp_path: Path) -> None:
    path = tmp_path / "migration-rollback.sqlite3"
    legacy_file(path)
    before = legacy_rows(path)
    with pytest.raises(LocalStoreUnavailable):
        with MigrationFailureStore(path).transaction():
            pytest.fail("The injected migration failure did not roll back")
    assert version_of(path) == 1
    assert legacy_rows(path) == before
    with closing(sqlite3.connect(path)) as connection:
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "local_risk_drafts" not in names
    assert "local_risk_assessments" not in names
    with SQLiteLocalApplicationStore(path).transaction() as transaction:
        assert transaction.get_onboarding(OWNER).display_name == "Synthetic learner"
    assert version_of(path) == 4


def test_concurrent_migrators_recheck_after_the_actual_native_write_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "concurrent-migration.sqlite3"
    legacy_file(path)
    before = legacy_rows(path)
    both_reached_lock = Barrier(2)
    lock_attempts: list[bool] = []
    original_connect = sqlite3.connect

    class ObservedConnection(sqlite3.Connection):
        attempted = False

        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE" and not self.attempted:
                self.attempted = True
                lock_attempts.append(True)
                both_reached_lock.wait(2)
            return super().execute(sql, parameters)

    def connect(
        database: Path, *, timeout: float = 5, isolation_level: str | None = ""
    ) -> sqlite3.Connection:
        return original_connect(
            database, timeout=timeout, isolation_level=isolation_level, factory=ObservedConnection
        )

    monkeypatch.setattr(sqlite3, "connect", connect)

    def read_owned_profile() -> str | None:
        with SQLiteLocalApplicationStore(path).transaction() as transaction:
            return transaction.get_onboarding(OWNER).display_name

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(read_owned_profile)
        second = pool.submit(read_owned_profile)
        assert first.result(timeout=5) == "Synthetic learner"
        assert second.result(timeout=5) == "Synthetic learner"
    assert len(lock_attempts) == 2
    monkeypatch.undo()
    assert version_of(path) == 4
    assert legacy_rows(path) == before


@pytest.mark.parametrize("version", [4, 5, 999])
def test_future_or_falsely_labelled_owned_schema_is_not_migrated_or_journaled(
    tmp_path: Path, version: int
) -> None:
    path = tmp_path / "future-owned.sqlite3"
    legacy_file(path, version=version)
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("A future schema was treated as an older migration")
    unchanged = path.read_bytes() == before
    assert unchanged
    assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("kind", ["table", "view"])
def test_foreign_object_with_sqlite_like_prefix_is_not_hidden_by_system_filter(
    tmp_path: Path, kind: str
) -> None:
    path = tmp_path / "foreign-prefix.sqlite3"
    legacy_file(path)
    with closing(sqlite3.connect(path)) as connection:
        if kind == "table":
            connection.execute("CREATE TABLE sqliteXforeign(value TEXT)")
        else:
            connection.execute("CREATE VIEW sqliteXforeign AS SELECT alias FROM local_users")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with SQLiteLocalApplicationStore(path).transaction():
            pytest.fail("A foreign non-system object was hidden by prefix filtering")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("store_class", [SQLiteLocalApplicationStore, SQLiteLocalRiskStore])
@pytest.mark.parametrize(
    "target,replacement",
    [
        ("schema_metadata", "CREATE TABLE schema_metadata (version INTEGER NOT NULL)"),
        ("local_users", LEGACY_DDL[1][1].replace("CHECK(active IN (0,1))", "CHECK(active >= 0)")),
        ("local_onboarding", LEGACY_DDL[4][1].replace("display_name TEXT", "renamed_display TEXT")),
        (
            "local_consent_no_delete",
            "CREATE TRIGGER local_consent_no_delete BEFORE DELETE ON local_consent_events "
            "BEGIN SELECT 1; END",
        ),
    ],
)
def test_matching_s1_object_names_with_altered_definitions_are_not_owned(
    tmp_path: Path,
    store_class: type[SQLiteLocalApplicationStore] | type[SQLiteLocalRiskStore],
    target: str,
    replacement: str,
) -> None:
    path = tmp_path / "altered-s1-schema.sqlite3"
    legacy_file(path, replacement=(target, replacement))
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with store_class(path).transaction():
            pytest.fail("An altered schema with matching object names was accepted")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


@pytest.mark.parametrize("store_class", [SQLiteLocalApplicationStore, SQLiteLocalRiskStore])
@pytest.mark.parametrize(
    "target",
    [
        "local_risk_drafts",
        "local_risk_assessment_owner",
        "local_risk_assessment_no_update",
        "weak_trigger",
    ],
)
def test_incomplete_or_weakened_version_two_is_rejected_by_both_adapters(
    tmp_path: Path,
    store_class: type[SQLiteLocalApplicationStore] | type[SQLiteLocalRiskStore],
    target: str,
) -> None:
    path = tmp_path / "altered-s2-schema.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        for statement in tuple(statement for _, statement in LEGACY_DDL) + LEGACY_RISK_DDL:
            if target != "weak_trigger" and statement.split()[2] == target:
                continue
            if target == "weak_trigger" and statement.startswith(
                "CREATE TRIGGER local_risk_assessment_no_delete "
            ):
                statement = (
                    "CREATE TRIGGER local_risk_assessment_no_delete BEFORE DELETE ON "
                    "local_risk_assessments BEGIN SELECT 1; END"
                )
            connection.execute(statement)
        connection.execute("INSERT INTO schema_metadata VALUES(2)")
        connection.commit()
    before = path.read_bytes()
    with pytest.raises(LocalStoreUnavailable):
        with store_class(path).transaction():
            pytest.fail("Incomplete or weakened shared version two was accepted")
    assert path.read_bytes() == before
    assert not path.with_name(path.name + "-wal").exists()


def test_risk_first_use_migrates_version_one_and_keeps_every_s1_row(tmp_path: Path) -> None:
    path = tmp_path / "risk-first-migration.sqlite3"
    legacy_file(path)
    before = legacy_rows(path)
    with SQLiteLocalRiskStore(path).transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) is None
        assert transaction.get_onboarding(OWNER).completed_at == NOW
    assert version_of(path) == 4
    assert legacy_rows(path) == before


def test_concurrent_s1_and_risk_first_creators_share_one_schema_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "concurrent-fresh.sqlite3"
    both_reached_lock = Barrier(2)
    original_connect = sqlite3.connect
    lock_attempts: list[bool] = []

    class ObservedConnection(sqlite3.Connection):
        attempted = False

        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> sqlite3.Cursor:
            if sql == "BEGIN IMMEDIATE" and not self.attempted:
                self.attempted = True
                lock_attempts.append(True)
                both_reached_lock.wait(2)
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
            return transaction.get_user_by_alias("learner-a") is None

    def risk_read() -> bool:
        with SQLiteLocalRiskStore(path).transaction() as transaction:
            return transaction.get_risk_draft(OWNER) is None

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(s1_read)
        second = pool.submit(risk_read)
        assert first.result(timeout=5)
        assert second.result(timeout=5)
    assert len(lock_attempts) == 2
    monkeypatch.undo()
    assert version_of(path) == 4


def test_fresh_schema_failure_rolls_back_all_ddl_before_safe_retry(tmp_path: Path) -> None:
    path = tmp_path / "fresh-bootstrap-rollback.sqlite3"
    with pytest.raises(LocalStoreUnavailable):
        with MigrationFailureStore(path).transaction():
            pytest.fail("The injected fresh schema failure was accepted")
    with closing(sqlite3.connect(path)) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name NOT GLOB 'sqlite_*'"
            ).fetchone()[0]
            == 0
        )
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    with SQLiteLocalRiskStore(path).transaction() as transaction:
        assert transaction.get_risk_draft(OWNER) is None
    assert version_of(path) == 4
