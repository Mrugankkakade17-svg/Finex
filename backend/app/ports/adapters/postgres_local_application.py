"""PostgreSQL implementation of the local application store."""

from datetime import datetime

from app.domain.local_application import LocalSession, LocalUser, OnboardingRecord
from app.ports.adapters.postgres_local_store import (
    PostgresAuthorizationTransaction,
    PostgresTransactionStore,
)
from app.ports.local_application_store import LocalApplicationTransaction


class PostgresLocalApplicationTransaction(PostgresAuthorizationTransaction):
    def get_user_by_alias(self, alias: str) -> LocalUser | None:
        row = self._connection.execute(
            "SELECT user_id,alias FROM finex.local_users WHERE alias=%s AND active=TRUE",
            (alias,),
        ).fetchone()
        return LocalUser(row["user_id"], row["alias"]) if row else None

    def create_user(self, user: LocalUser, profile_version: str, now: datetime) -> None:
        self._connection.execute(
            "INSERT INTO finex.local_users(user_id,alias,active,created_at) VALUES(%s,%s,TRUE,%s)",
            (user.id, user.alias, now),
        )
        self._connection.execute(
            "INSERT INTO finex.local_onboarding(user_id,profile_schema_version) VALUES(%s,%s)",
            (user.id, profile_version),
        )

    def insert_session(self, session: LocalSession, now: datetime) -> None:
        self._connection.execute(
            "INSERT INTO finex.local_sessions(digest,user_id,expires_at,created_at) "
            "VALUES(%s,%s,%s,%s)",
            (session.digest, session.user.id, session.expires_at, now),
        )

    def revoke_session(self, digest: str, user_id: str, now: datetime) -> None:
        self._connection.execute(
            "UPDATE finex.local_sessions SET revoked_at=%s WHERE digest=%s AND user_id=%s",
            (now, digest, user_id),
        )

    def save_onboarding(self, record: OnboardingRecord) -> None:
        self._connection.execute(
            "UPDATE finex.local_onboarding SET profile_schema_version=%s,display_name=%s,"
            "experience_level=%s,updated_at=%s,completed_at=%s WHERE user_id=%s",
            (
                record.profile_schema_version,
                record.display_name,
                record.experience_level,
                record.updated_at,
                record.completed_at,
                record.user_id,
            ),
        )

    def append_consent(self, user_id: str, version: str, accepted: bool, now: datetime) -> None:
        self._connection.execute(
            "INSERT INTO finex.local_consent_events(user_id,version,accepted,recorded_at) "
            "VALUES(%s,%s,%s,%s)",
            (user_id, version, accepted, now),
        )


class PostgresLocalApplicationStore(PostgresTransactionStore[LocalApplicationTransaction]):
    def __init__(self, database_url: str) -> None:
        super().__init__(database_url, PostgresLocalApplicationTransaction)
