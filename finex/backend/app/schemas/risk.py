"""Backend API schemas for FinEx risk APIs."""

from typing import List

from ai.risk.schemas import (
    KeyInfluencingFactor,
    NonLLMExplanation,
    QuestionAnswer,
    RiskAssessmentAndExplanationResult,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskCategory,
    RiskExplanationRequest,
    RiskExplanationResponse,
    RiskScoreBreakdown,
)
from pydantic import BaseModel, Field

QUESTIONNAIRE_VERSION = "v1"


class LegacyRiskAnswer(BaseModel):
    question_id: str = Field(..., min_length=1)
    answer_id: str = Field(..., min_length=1)


class LegacyRiskQuestion(BaseModel):
    question_id: str
    question: str
    answers: List[dict]


class LegacyRiskQuestionsResponse(BaseModel):
    questionnaire_version: str
    questions: List[LegacyRiskQuestion]


class LegacyRiskAssessmentRequest(BaseModel):
    questionnaire_version: str
    answers: List[LegacyRiskAnswer]


class LegacyRiskAssessmentResponse(BaseModel):
    assessment_id: int
    user_id: int
    questionnaire_version: str
    score: float
    risk_profile: str


__all__ = [
    "KeyInfluencingFactor",
    "NonLLMExplanation",
    "QuestionAnswer",
    "RiskAssessmentAndExplanationResult",
    "RiskAssessmentRequest",
    "RiskAssessmentResult",
    "RiskCategory",
    "RiskExplanationRequest",
    "RiskExplanationResponse",
    "RiskScoreBreakdown",
    "QUESTIONNAIRE_VERSION",
    "LegacyRiskAnswer",
    "LegacyRiskQuestion",
    "LegacyRiskQuestionsResponse",
    "LegacyRiskAssessmentRequest",
    "LegacyRiskAssessmentResponse",
]
