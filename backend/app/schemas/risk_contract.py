"""OpenAPI DTOs for the #146 logical contract and #161 HTTP boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from app.schemas.envelope import ErrorDetail, ErrorEnvelope


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class RiskAnswer(StrictDTO):
    question_id: StrictStr = Field(min_length=1, max_length=32)
    answer_code: StrictStr = Field(min_length=1, max_length=32)


class RiskContractRequest(StrictDTO):
    questionnaire_id: StrictStr = Field(min_length=1, max_length=80)
    questionnaire_version: StrictStr = Field(min_length=1, max_length=32)
    answers: list[RiskAnswer] = Field(max_length=64)


class RiskCategoryDTO(StrictDTO):
    code: Literal["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]
    label: Literal["Conservative", "Moderate", "Aggressive"]


class RiskLimitation(StrictDTO):
    code: Literal["EDUCATIONAL_SELF_REPORTED_PROFILE"]
    message: str


class InformationalTension(StrictDTO):
    code: Literal["CAPACITY_BELOW_WILLINGNESS", "WILLINGNESS_BELOW_CAPACITY"]
    message: str


class RiskContractResult(StrictDTO):
    contract_version: Literal["s2-risk-contract/v1.0"]
    questionnaire_id: Literal["risk_questionnaire_v1"]
    questionnaire_version: Literal["v1"]
    scoring_version: Literal["deterministic_v1.0.0"]
    willingness_score: float = Field(ge=0, le=100)
    capacity_score: float = Field(ge=0, le=100)
    composite_score: float = Field(ge=0, le=100)
    risk_category: RiskCategoryDTO
    calculated_at: str = Field(description="Server-generated ISO-8601 UTC calculation timestamp.")
    limitation: RiskLimitation
    informational_tension: InformationalTension | None = None


class EducationalExplanation(StrictDTO):
    summary: str
    dimensions: str
    method: str
    questionnaire_version: str
    scoring_version: str
    calculated_at: str
    limitation: str


class RiskSubmissionResponse(StrictDTO):
    assessment: RiskContractResult
    explanation: EducationalExplanation
    scope: Literal["local_educational_pilot"] = "local_educational_pilot"
    persisted: Literal[False] = False


class QuestionOption(StrictDTO):
    code: str
    label: str


class QuestionDefinition(StrictDTO):
    question_id: str
    dimension: Literal["willingness", "capacity"]
    text: str
    options: list[QuestionOption]


class QuestionnaireResponse(StrictDTO):
    contract_version: Literal["s2-risk-contract/v1.0"] = "s2-risk-contract/v1.0"
    questionnaire_id: Literal["risk_questionnaire_v1"] = "risk_questionnaire_v1"
    questionnaire_version: Literal["v1"] = "v1"
    questions: list[QuestionDefinition]
    limitation: RiskLimitation


RiskErrorCode = Literal[
    "MALFORMED_ANSWER",
    "UNSUPPORTED_QUESTIONNAIRE_VERSION",
    "DUPLICATE_QUESTION_ANSWER",
    "UNKNOWN_QUESTION_ID",
    "MISSING_REQUIRED_QUESTION",
    "INVALID_ANSWER_CODE",
    "ANSWER_NOT_PERMITTED_FOR_QUESTION",
    "LOCAL_PILOT_ONLY",
    "RISK_ASSESSMENT_UNAVAILABLE",
]


class RiskErrorDetail(ErrorDetail):
    code: RiskErrorCode


class RiskErrorEnvelope(ErrorEnvelope):
    error_code: RiskErrorCode
    error: RiskErrorDetail
    detail: str = Field(description="Legacy-compatible duplicate of the safe message.")
