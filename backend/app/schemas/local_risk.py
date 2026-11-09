"""Strict saved-risk DTOs, separate from the stateless compatibility pilot."""

from typing import Annotated, Literal

from pydantic import Field, JsonValue, StrictStr

from app.schemas.risk_contract import (
    EducationalExplanation,
    InformationalTension,
    QuestionDefinition,
    RiskAnswer,
    RiskContractRequest,
    RiskContractResult,
    RiskLimitation,
    StrictDTO,
)

UUID4_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
CanonicalUUID4 = Annotated[StrictStr, Field(min_length=36, max_length=36, pattern=UUID4_PATTERN)]


class LocalRiskInput(RiskContractRequest):
    """Only these three logical input fields are passed to the approved scorer."""


class LocalRiskSubmitRequest(LocalRiskInput):
    idempotency_key: CanonicalUUID4


class LocalRiskScope(StrictDTO):
    scope: Literal["local_educational_application"] = "local_educational_application"
    contract_version: Literal["local.v1"] = "local.v1"


class LocalRiskQuestionnaire(LocalRiskScope):
    questionnaire_id: Literal["risk_questionnaire_v1"] = "risk_questionnaire_v1"
    questionnaire_version: Literal["v1"] = "v1"
    scoring_version: Literal["deterministic_v1.0.0"] = "deterministic_v1.0.0"
    explanation_version: Literal["educational_v1.0.0"] = "educational_v1.0.0"
    rules_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    questions: list[QuestionDefinition]
    limitation: RiskLimitation


class LocalRiskDraft(LocalRiskScope):
    questionnaire_id: Literal["risk_questionnaire_v1"] = "risk_questionnaire_v1"
    questionnaire_version: Literal["v1"] = "v1"
    answers: list[RiskAnswer] = Field(max_length=10)
    updated_at: StrictStr | None


class LocalSavedRiskResult(RiskContractResult):
    # Saved history requires this key even when there is no informational tension.
    informational_tension: InformationalTension | None = Field(...)


class LocalSavedRiskAssessment(LocalRiskScope):
    persisted: Literal[True] = True
    assessment_id: CanonicalUUID4
    created_at: StrictStr
    input: LocalRiskInput
    assessment: LocalSavedRiskResult
    explanation: EducationalExplanation
    explanation_version: Literal["educational_v1.0.0"] = "educational_v1.0.0"
    rules_sha256: StrictStr = Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)
    rules_snapshot: dict[str, JsonValue]


class LocalRiskHistory(LocalRiskScope):
    items: list[LocalSavedRiskAssessment] = Field(max_length=50)
    next_cursor: Annotated[StrictStr, Field(pattern=r"^[1-9][0-9]*$", max_length=19)] | None
