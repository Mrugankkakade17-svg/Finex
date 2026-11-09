"""FinEx AI Risk Profiling Package (v1).

Deterministic, rule-based risk profiling engine evaluating willingness and capacity.
"""

from ai.risk.explanation import (
    RiskExplanationEngine,
    evaluate_and_explain,
    explain_risk_assessment,
    get_explanation_engine,
)
from ai.risk.prompts import (
    PROMPT_VERSION_V1,
    SCHEMA_VERSION_V1,
    SYSTEM_PROMPT_V1,
    USER_PROMPT_TEMPLATE_V1,
    format_user_prompt_v1,
)
from ai.risk.schemas import (
    DimensionScore,
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
from ai.risk.scoring import RiskScoringEngine, calculate_risk_score

__all__ = [
    "RiskScoringEngine",
    "calculate_risk_score",
    "RiskExplanationEngine",
    "explain_risk_assessment",
    "evaluate_and_explain",
    "get_explanation_engine",
    "RiskAssessmentRequest",
    "RiskAssessmentResult",
    "RiskExplanationRequest",
    "RiskExplanationResponse",
    "RiskAssessmentAndExplanationResult",
    "KeyInfluencingFactor",
    "QuestionAnswer",
    "DimensionScore",
    "RiskScoreBreakdown",
    "NonLLMExplanation",
    "RiskCategory",
    "PROMPT_VERSION_V1",
    "SCHEMA_VERSION_V1",
    "SYSTEM_PROMPT_V1",
    "USER_PROMPT_TEMPLATE_V1",
    "format_user_prompt_v1",
]

