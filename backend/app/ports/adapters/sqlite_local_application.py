"""Native, transactional synthetic-local adapter; never resets existing data."""

from datetime import datetime
from pathlib import Path

from app.domain.local_application import (
    LocalSession,
    LocalUser,
    OnboardingRecord,
)
from app.ports.adapters.sqlite_local_schema import SCHEMA_STATEMENTS as SCHEMA_STATEMENTS
from app.ports.adapters.sqlite_local_schema import SCHEMA_VERSION as SCHEMA_VERSION
from app.ports.adapters.sqlite_local_store import (
    SQLiteAuthorizationTransaction,
    SQLiteTransactionStore,
    stored_text,
    utc_text,
)
from app.ports.local_application_store import LocalApplicationTransaction


class SQLiteLocalTransaction(SQLiteAuthorizationTransaction):
    def get_user_by_alias(self, alias: str) -> LocalUser | None:
        row = self._connection.execute(
            "SELECT user_id, alias FROM local_users WHERE alias=? AND active=1", (alias,)
        ).fetchone()
        return LocalUser(stored_text(row["user_id"]), stored_text(row["alias"])) if row else None

    def create_user(self, user: LocalUser, profile_version: str, now: datetime) -> None:
        self._connection.execute(
            "INSERT INTO local_users(user_id,alias,active,created_at) VALUES(?,?,1,?)",
            (user.id, user.alias, utc_text(now)),
        )
        self._connection.execute(
            "INSERT INTO local_onboarding(user_id,profile_schema_version) VALUES(?,?)",
            (user.id, profile_version),
        )

    def insert_session(self, session: LocalSession, now: datetime) -> None:
        self._connection.execute(
            "INSERT INTO local_sessions(digest,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (session.digest, session.user.id, utc_text(session.expires_at), utc_text(now)),
        )

    def revoke_session(self, digest: str, user_id: str, now: datetime) -> None:
        self._connection.execute(
            "UPDATE local_sessions SET revoked_at=? WHERE digest=? AND user_id=?",
            (utc_text(now), digest, user_id),
        )

    def save_onboarding(self, record: OnboardingRecord) -> None:
        self._connection.execute(
            """UPDATE local_onboarding SET profile_schema_version=?,display_name=?,
            experience_level=?,updated_at=?,completed_at=? WHERE user_id=?""",
            (
                record.profile_schema_version,
                record.display_name,
                record.experience_level,
                utc_text(record.updated_at) if record.updated_at else None,
                utc_text(record.completed_at) if record.completed_at else None,
                record.user_id,
            ),
        )

    def append_consent(self, user_id: str, version: str, accepted: bool, now: datetime) -> None:
        self._connection.execute(
            "INSERT INTO local_consent_events(user_id,version,accepted,recorded_at) "
            "VALUES(?,?,?,?)",
            (user_id, version, int(accepted), utc_text(now)),
        )


class SQLiteLocalApplicationStore(SQLiteTransactionStore[LocalApplicationTransaction]):
    """Constructing this adapter performs no filesystem/database operation."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, SQLiteLocalTransaction)
