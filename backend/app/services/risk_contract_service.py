"""Local deterministic adapter; it neither stores answers nor uses cloud services."""

from typing import Any

from ai.risk.contract import evaluate_risk_contract

from app.ports.assessment_scorer import AssessmentScorer


class LocalAssessmentScorer:
    def score(self, payload: object) -> dict[str, Any]:
        return evaluate_risk_contract(payload)


def get_assessment_scorer() -> AssessmentScorer:
    """FastAPI dependency can be substituted in tests without a hosted provider."""
    return LocalAssessmentScorer()
