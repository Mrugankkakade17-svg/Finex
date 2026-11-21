"""PostgreSQL implementation of the local risk store."""

from dataclasses import replace

from psycopg.rows import DictRow

from app.domain.local_risk import LocalRiskAssessmentRecord, LocalRiskDraftRecord
from app.ports.adapters.postgres_local_store import (
    PostgresAuthorizationTransaction,
    PostgresTransactionStore,
    stored_integer,
    stored_text,
    stored_time,
)
from app.ports.local_risk_store import LocalRiskTransaction


def _assessment(row: DictRow) -> LocalRiskAssessmentRecord:
    return LocalRiskAssessmentRecord(
        assessment_id=stored_text(row["assessment_id"]),
        user_id=stored_text(row["user_id"]),
        idempotency_key=stored_text(row["idempotency_key"]),
        request_fingerprint=stored_text(row["request_fingerprint"]),
        document_json=stored_text(row["document_json"]),
        created_at=stored_time(row["created_at"]),
        sequence=stored_integer(row["sequence"]),
    )


class PostgresLocalRiskTransaction(PostgresAuthorizationTransaction):
    def get_risk_draft(self, user_id: str) -> LocalRiskDraftRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_risk_drafts WHERE user_id=%s", (user_id,)
        ).fetchone()
        if row is None:
            return None
        return LocalRiskDraftRecord(
            user_id=stored_text(row["user_id"]),
            questionnaire_id=stored_text(row["questionnaire_id"]),
            questionnaire_version=stored_text(row["questionnaire_version"]),
            answers_json=stored_text(row["answers_json"]),
            updated_at=stored_time(row["updated_at"]),
        )

    def save_risk_draft(self, record: LocalRiskDraftRecord) -> None:
        self._connection.execute(
            """INSERT INTO finex.local_risk_drafts
               (user_id,questionnaire_id,questionnaire_version,answers_json,updated_at)
               VALUES(%s,%s,%s,%s,%s)
               ON CONFLICT(user_id) DO UPDATE SET questionnaire_id=EXCLUDED.questionnaire_id,
               questionnaire_version=EXCLUDED.questionnaire_version,answers_json=EXCLUDED.answers_json,
               updated_at=EXCLUDED.updated_at""",
            (
                record.user_id,
                record.questionnaire_id,
                record.questionnaire_version,
                record.answers_json,
                record.updated_at,
            ),
        )

    def get_risk_assessment(
        self, user_id: str, assessment_id: str
    ) -> LocalRiskAssessmentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_risk_assessments WHERE user_id=%s AND assessment_id=%s",
            (user_id, assessment_id),
        ).fetchone()
        return _assessment(row) if row else None

    def get_risk_assessment_by_key(
        self, user_id: str, idempotency_key: str
    ) -> LocalRiskAssessmentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM finex.local_risk_assessments WHERE user_id=%s AND idempotency_key=%s",
            (user_id, idempotency_key),
        ).fetchone()
        return _assessment(row) if row else None

    def insert_risk_assessment(
        self, record: LocalRiskAssessmentRecord
    ) -> LocalRiskAssessmentRecord:
        if type(record.sequence) is not int or record.sequence != 0:
            raise ValueError("Only a new unsequenced risk record can be inserted.")
        row = self._connection.execute(
            """INSERT INTO finex.local_risk_assessments
               (assessment_id,user_id,idempotency_key,request_fingerprint,document_json,created_at)
               VALUES(%s,%s,%s,%s,%s,%s) RETURNING sequence""",
            (
                record.assessment_id,
                record.user_id,
                record.idempotency_key,
                record.request_fingerprint,
                record.document_json,
                record.created_at,
            ),
        ).fetchone()
        if row is None:
            raise ValueError("The inserted risk sequence is missing.")
        return replace(record, sequence=stored_integer(row["sequence"]))

    def list_risk_assessments(
        self, user_id: str, *, before: int | None, limit: int
    ) -> list[LocalRiskAssessmentRecord]:
        if type(limit) is not int or not 1 <= limit <= 51:
            raise ValueError("The risk history query is not bounded.")
        if before is None:
            rows = self._connection.execute(
                "SELECT * FROM finex.local_risk_assessments WHERE user_id=%s "
                "ORDER BY sequence DESC LIMIT %s",
                (user_id, limit),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM finex.local_risk_assessments WHERE user_id=%s AND sequence<%s "
                "ORDER BY sequence DESC LIMIT %s",
                (user_id, before, limit),
            ).fetchall()
        return [_assessment(row) for row in rows]


class PostgresLocalRiskStore(PostgresTransactionStore[LocalRiskTransaction]):
    def __init__(self, database_url: str) -> None:
        super().__init__(database_url, PostgresLocalRiskTransaction)
