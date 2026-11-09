"""Native owned risk persistence; no HTTP, scoring or S1 write capability."""

import sqlite3
from dataclasses import replace
from pathlib import Path

from app.domain.local_risk import LocalRiskAssessmentRecord, LocalRiskDraftRecord
from app.ports.adapters.sqlite_local_store import (
    SQLiteAuthorizationTransaction,
    SQLiteTransactionStore,
    stored_integer,
    stored_text,
    stored_time,
    utc_text,
)
from app.ports.local_risk_store import LocalRiskTransaction

MAX_SEQUENCE = 2**63 - 1


def _assessment(row: sqlite3.Row) -> LocalRiskAssessmentRecord:
    sequence = stored_integer(row["sequence"])
    if not 1 <= sequence <= MAX_SEQUENCE:
        raise ValueError("Persisted risk sequence is invalid.")
    return LocalRiskAssessmentRecord(
        assessment_id=stored_text(row["assessment_id"]),
        user_id=stored_text(row["user_id"]),
        idempotency_key=stored_text(row["idempotency_key"]),
        request_fingerprint=stored_text(row["request_fingerprint"]),
        document_json=stored_text(row["document_json"]),
        created_at=stored_time(row["created_at"]),
        sequence=sequence,
    )


class SQLiteLocalRiskTransaction(SQLiteAuthorizationTransaction):
    def get_risk_draft(self, user_id: str) -> LocalRiskDraftRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_risk_drafts WHERE user_id=?", (user_id,)
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
            """INSERT INTO local_risk_drafts(
            user_id,questionnaire_id,questionnaire_version,answers_json,updated_at
            ) VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET
            questionnaire_id=excluded.questionnaire_id,
            questionnaire_version=excluded.questionnaire_version,
            answers_json=excluded.answers_json,updated_at=excluded.updated_at""",
            (
                record.user_id,
                record.questionnaire_id,
                record.questionnaire_version,
                record.answers_json,
                utc_text(record.updated_at),
            ),
        )

    def get_risk_assessment(
        self, user_id: str, assessment_id: str
    ) -> LocalRiskAssessmentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_risk_assessments WHERE user_id=? AND assessment_id=?",
            (user_id, assessment_id),
        ).fetchone()
        return _assessment(row) if row is not None else None

    def get_risk_assessment_by_key(
        self, user_id: str, idempotency_key: str
    ) -> LocalRiskAssessmentRecord | None:
        row = self._connection.execute(
            "SELECT * FROM local_risk_assessments WHERE user_id=? AND idempotency_key=?",
            (user_id, idempotency_key),
        ).fetchone()
        return _assessment(row) if row is not None else None

    def insert_risk_assessment(
        self, record: LocalRiskAssessmentRecord
    ) -> LocalRiskAssessmentRecord:
        if type(record.sequence) is not int or record.sequence != 0:
            raise ValueError("Only a new unsequenced risk record can be inserted.")
        inserted = self._connection.execute(
            """INSERT INTO local_risk_assessments(
            assessment_id,user_id,idempotency_key,request_fingerprint,document_json,created_at
            ) VALUES(?,?,?,?,?,?)""",
            (
                record.assessment_id,
                record.user_id,
                record.idempotency_key,
                record.request_fingerprint,
                record.document_json,
                utc_text(record.created_at),
            ),
        )
        sequence = inserted.lastrowid
        if sequence is None or not 1 <= sequence <= MAX_SEQUENCE:
            raise ValueError("The inserted risk sequence is invalid.")
        return replace(record, sequence=sequence)

    def list_risk_assessments(
        self, user_id: str, *, before: int | None, limit: int
    ) -> list[LocalRiskAssessmentRecord]:
        # The service requests at most the public 50 records plus one look-ahead.
        if (
            type(limit) is not int
            or not 1 <= limit <= 51
            or (before is not None and (type(before) is not int or not 1 <= before <= MAX_SEQUENCE))
        ):
            raise ValueError("The risk history query is not bounded.")
        if before is None:
            rows = self._connection.execute(
                "SELECT * FROM local_risk_assessments WHERE user_id=? "
                "ORDER BY sequence DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "SELECT * FROM local_risk_assessments WHERE user_id=? AND sequence<? "
                "ORDER BY sequence DESC LIMIT ?",
                (user_id, before, limit),
            ).fetchall()
        return [_assessment(row) for row in rows]


class SQLiteLocalRiskStore(SQLiteTransactionStore[LocalRiskTransaction]):
    """Owns a path lazily and constructs only the dedicated risk capability."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, SQLiteLocalRiskTransaction)
