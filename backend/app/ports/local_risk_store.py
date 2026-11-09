"""Typed risk capability: shared authorization reads and owned risk records."""

from typing import Protocol

from app.domain.local_risk import LocalRiskAssessmentRecord, LocalRiskDraftRecord
from app.ports.local_authorization import AuthorizationTransaction, TransactionStore


class LocalRiskTransaction(AuthorizationTransaction, Protocol):
    def get_risk_draft(self, user_id: str) -> LocalRiskDraftRecord | None: ...

    def save_risk_draft(self, record: LocalRiskDraftRecord) -> None: ...

    def get_risk_assessment(
        self, user_id: str, assessment_id: str
    ) -> LocalRiskAssessmentRecord | None: ...

    def get_risk_assessment_by_key(
        self, user_id: str, idempotency_key: str
    ) -> LocalRiskAssessmentRecord | None: ...

    def insert_risk_assessment(
        self, record: LocalRiskAssessmentRecord
    ) -> LocalRiskAssessmentRecord: ...

    def list_risk_assessments(
        self, user_id: str, *, before: int | None, limit: int
    ) -> list[LocalRiskAssessmentRecord]: ...


class LocalRiskStore(TransactionStore[LocalRiskTransaction], Protocol):
    """A dedicated typed store, not a runtime guess about an S1-only store."""
