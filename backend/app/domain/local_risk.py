"""Immutable owned risk records, independent of HTTP and persistence vendors."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LocalRiskDraftRecord:
    user_id: str
    questionnaire_id: str
    questionnaire_version: str
    answers_json: str
    updated_at: datetime


@dataclass(frozen=True)
class LocalRiskAssessmentRecord:
    assessment_id: str
    user_id: str
    idempotency_key: str
    request_fingerprint: str
    document_json: str
    created_at: datetime
    sequence: int = 0
