"""Pydantic schemas for FinEx AI Risk Profiling v1.

Validated data models for request inputs, dimensions, composite scores,
deterministic categorization, and rule-based explanations.
"""

import re
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RiskCategory(str, Enum):
    """Canonical risk categories."""
    CONSERVATIVE = "Conservative"
    MODERATE = "Moderate"
    AGGRESSIVE = "Aggressive"


class QuestionAnswer(BaseModel):
    """Represents a user's answer to a single questionnaire question."""
    question_id: str = Field(..., description="ID of the question (e.g., 'W1', 'C1')")
    answer_code: str = Field(..., description="Code of selected answer (e.g., 'W1_C', 'C2_A')")

    @field_validator("question_id")
    @classmethod
    def validate_question_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("question_id cannot be empty")
        if not re.match(r"^[A-Z0-9_]+$", v):
            raise ValueError(f"Invalid question_id format: '{v}'")
        return v

    @field_validator("answer_code")
    @classmethod
    def validate_answer_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("answer_code cannot be empty")
        if not re.match(r"^[A-Z0-9_]+$", v):
            raise ValueError(f"Invalid answer_code format: '{v}'")
        return v


class RiskAssessmentRequest(BaseModel):
    """Incoming request to score a risk questionnaire."""
    questionnaire_id: str = Field(
        default="risk_questionnaire_v1",
        description="ID of the questionnaire being submitted",
    )
    version: str = Field(
        default="v1",
        description="Version tag of the questionnaire",
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user UUID or identifier",
    )
    calculated_at: Optional[str] = Field(
        default=None,
        description="Optional ISO 8601 UTC timestamp override for deterministic audits and replay",
    )
    answers: List[QuestionAnswer] = Field(
        ...,
        description="List of selected answers for the questionnaire",
    )

    @field_validator("answers")
    @classmethod
    def validate_answers_not_empty(cls, v: List[QuestionAnswer]) -> List[QuestionAnswer]:
        if not v:
            raise ValueError("answers list cannot be empty")
        return v


class DimensionScore(BaseModel):
    """Computed score for a single risk dimension (Willingness or Capacity)."""
    dimension: str = Field(..., description="'willingness' or 'capacity'")
    raw_score: int = Field(..., ge=5, le=25, description="Sum of answer weights (5-25)")
    min_raw: int = Field(default=5, description="Minimum possible raw score")
    max_raw: int = Field(default=25, description="Maximum possible raw score")
    normalized_score: float = Field(..., ge=0.0, le=100.0, description="Normalized score (0-100)")
    weight: float = Field(default=0.5, description="Weight used in composite scoring")


class RiskScoreBreakdown(BaseModel):
    """Detailed breakdown across both dimensions."""
    willingness: DimensionScore
    capacity: DimensionScore


class NonLLMExplanation(BaseModel):
    """Safe, deterministic non-LLM explanation and rationale."""
    summary: str = Field(..., description="High-level risk profile classification summary")
    willingness_rationale: str = Field(..., description="Explanation of behavioral risk willingness")
    capacity_rationale: str = Field(..., description="Explanation of financial capacity and horizon")
    alignment_note: str = Field(..., description="Analysis of alignment or tension between willingness and capacity")
    is_fallback: bool = Field(default=True, description="Flag indicating deterministic non-LLM rationale")


class RiskAssessmentResult(BaseModel):
    """Final deterministic risk assessment output."""
    questionnaire_id: str = Field(..., description="Questionnaire ID used for evaluation")
    version: str = Field(..., description="Questionnaire version")
    willingness_score: float = Field(..., ge=0.0, le=100.0, description="Normalized willingness score (0-100)")
    capacity_score: float = Field(..., ge=0.0, le=100.0, description="Normalized capacity score (0-100)")
    composite_score: float = Field(..., ge=0.0, le=100.0, description="Weighted composite risk score (0-100)")
    risk_category: RiskCategory = Field(..., description="Canonical risk profile category")
    risk_category_code: str = Field(..., description="Upper-snake code: CONSERVATIVE, MODERATE, AGGRESSIVE")
    breakdown: RiskScoreBreakdown = Field(..., description="Detailed dimension breakdowns")
    explanation: NonLLMExplanation = Field(..., description="Deterministic explanation")
    model_version: str = Field(default="deterministic_v1.0.0", description="Scoring engine version")
    schema_version: str = Field(default="v1.0.0", description="Output JSON schema version")
    calculated_at: str = Field(..., description="ISO 8601 UTC calculation timestamp")


class KeyInfluencingFactor(BaseModel):
    """A specific questionnaire question and answer that significantly influenced the risk result."""
    dimension: str = Field(..., description="'willingness' or 'capacity'")
    question_id: str = Field(..., description="Question ID (e.g., 'W1', 'C3')")
    question_text: str = Field(..., description="Full text of the question")
    answer_code: str = Field(..., description="Selected answer code (e.g., 'W1_A', 'C3_E')")
    answer_label: str = Field(..., description="Text of the selected answer")
    score: int = Field(..., ge=1, le=5, description="Answer weight (1-5)")
    impact: str = Field(..., description="Impact description, e.g., 'Conservative Anchor', 'Growth Driver'")
    explanation: str = Field(..., description="Beginner-friendly explanation of why this answer impacted the score")


class RiskExplanationResponse(BaseModel):
    """Structured, beginner-friendly explanation of deterministic risk assessment (S2-AI-02)."""
    summary: str = Field(
        ...,
        description="Clear, beginner-friendly summary explaining the investor category and score without altering values",
    )
    willingness_explanation: str = Field(
        ...,
        description="Plain-language explanation of psychological risk tolerance and emotional comfort with market swings",
    )
    capacity_explanation: str = Field(
        ...,
        description="Plain-language explanation of financial capacity, emergency cushion, and time horizon",
    )
    alignment_analysis: str = Field(
        ...,
        description="Explanation of whether willingness and capacity align or if one acts as a constraint",
    )
    key_influencing_factors: List[KeyInfluencingFactor] = Field(
        default_factory=list,
        description="List of top questionnaire answers that most strongly influenced the final profile",
    )
    limitations_and_disclaimers: List[str] = Field(
        default_factory=list,
        description="Mandatory regulatory and methodology disclaimers (no return promises, point-in-time assessment)",
    )
    is_fallback: bool = Field(
        default=False,
        description="True if generated by deterministic non-LLM safety fallback, False if generated by LLM",
    )
    model_version: str = Field(default="deterministic_rule_v1.0.0", description="LLM or rule engine identifier")
    prompt_version: str = Field(default="v1.0.0", description="Prompt template version used")
    schema_version: str = Field(default="v1.0.0", description="JSON schema version")
    generated_at: str = Field(..., description="ISO 8601 UTC timestamp of explanation generation")


class RiskAssessmentAndExplanationResult(BaseModel):
    """Combined output containing both deterministic calculation and beginner-friendly explanation."""
    assessment: RiskAssessmentResult = Field(..., description="Deterministic scoring engine result")
    explanation: RiskExplanationResponse = Field(..., description="Structured explanation output")


class RiskExplanationRequest(BaseModel):
    """Request payload to generate a risk explanation."""
    assessment: Optional[RiskAssessmentResult] = Field(
        default=None,
        description="Pre-calculated deterministic assessment result (if already computed)",
    )
    answers: Optional[List[QuestionAnswer]] = Field(
        default=None,
        description="List of questionnaire answers (if calculation should be performed in-flight)",
    )
    questionnaire_id: str = Field(default="risk_questionnaire_v1", description="Questionnaire ID")
    version: str = Field(default="v1", description="Questionnaire version")
    user_id: Optional[str] = Field(default=None, description="Optional user identifier for audit logging")
    force_fallback: bool = Field(
        default=False,
        description="Force deterministic non-LLM fallback (useful for testing or offline environments)",
    )
    calculated_at: Optional[str] = Field(
        default=None,
        description="Optional ISO 8601 UTC timestamp override for deterministic replay",
    )

