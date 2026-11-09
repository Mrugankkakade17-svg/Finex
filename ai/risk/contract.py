"""Strict, non-networked boundary for the versioned Sprint 2 risk contract.

Numeric decisions delegate to the existing deterministic engine. This boundary
does not normalize unknown input, persist identity, call an LLM, or log answers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ai.risk.schemas import RiskAssessmentRequest
from ai.risk.scoring import RiskScoringEngine

CONTRACT_VERSION = "s2-risk-contract/v1.0"
LIMITATION_CODE = "EDUCATIONAL_SELF_REPORTED_PROFILE"
LIMITATION_MESSAGE = (
    "This educational profile is based on self-reported answers and is not individualized "
    "financial, legal, tax, or investment advice."
)
ERROR_MESSAGES = {
    "MALFORMED_ANSWER": "Malformed assessment request or answer.",
    "UNSUPPORTED_QUESTIONNAIRE_VERSION": "Unsupported questionnaire ID or version.",
    "DUPLICATE_QUESTION_ANSWER": "More than one answer was supplied for a question.",
    "UNKNOWN_QUESTION_ID": "The request contains an unknown question.",
    "MISSING_REQUIRED_QUESTION": "Every required question must have an answer.",
    "INVALID_ANSWER_CODE": "The request contains an undefined answer code.",
    "ANSWER_NOT_PERMITTED_FOR_QUESTION": "A known answer belongs to a different question.",
}


class RiskContractError(ValueError):
    """Stable, non-sensitive error shared by API and offline callers."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(ERROR_MESSAGES[code])


def _validate_input(
    payload: object, engine: RiskScoringEngine, *, require_complete: bool = True
) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {
        "questionnaire_id",
        "questionnaire_version",
        "answers",
    }:
        raise RiskContractError("MALFORMED_ANSWER")
    if not all(
        isinstance(payload[key], str) for key in ("questionnaire_id", "questionnaire_version")
    ):
        raise RiskContractError("MALFORMED_ANSWER")
    answers = payload["answers"]
    if not isinstance(answers, list):
        raise RiskContractError("MALFORMED_ANSWER")
    for answer in answers:
        if not isinstance(answer, dict) or set(answer) != {"question_id", "answer_code"}:
            raise RiskContractError("MALFORMED_ANSWER")
        if any(not isinstance(value, str) or not value.strip() for value in answer.values()):
            raise RiskContractError("MALFORMED_ANSWER")
    if (
        payload["questionnaire_id"] != engine.questionnaire_id
        or payload["questionnaire_version"] != engine.version_label
    ):
        raise RiskContractError("UNSUPPORTED_QUESTIONNAIRE_VERSION")
    question_ids = [answer["question_id"] for answer in answers]
    if len(question_ids) != len(set(question_ids)):
        raise RiskContractError("DUPLICATE_QUESTION_ANSWER")
    if set(question_ids) - set(engine.questions_by_id):
        raise RiskContractError("UNKNOWN_QUESTION_ID")
    if require_complete and set(engine.questions_by_id) - set(question_ids):
        raise RiskContractError("MISSING_REQUIRED_QUESTION")
    if any(answer["answer_code"] not in engine.answers_by_code for answer in answers):
        raise RiskContractError("INVALID_ANSWER_CODE")
    if any(
        engine.answers_by_code[answer["answer_code"]]["question_id"] != answer["question_id"]
        for answer in answers
    ):
        raise RiskContractError("ANSWER_NOT_PERMITTED_FOR_QUESTION")
    return payload


def validate_risk_input(
    payload: object, engine: RiskScoringEngine, *, require_complete: bool = True
) -> dict[str, Any]:
    """Validate a saved draft or submission without generating a numeric score.

    Partial drafts omit only the missing-question check. Defaults preserve the
    complete pilot's existing validation order and error vocabulary.
    """
    return _validate_input(payload, engine, require_complete=require_complete)


def evaluate_risk_contract(
    payload: object,
    *,
    calculated_at: datetime | str | None = None,
    engine: RiskScoringEngine | None = None,
) -> dict[str, Any]:
    """Return exactly the logical #146 result; timestamps are server-controlled."""
    engine = RiskScoringEngine() if engine is None else engine
    accepted = _validate_input(payload, engine)
    request = RiskAssessmentRequest(
        questionnaire_id=accepted["questionnaire_id"],
        version=accepted["questionnaire_version"],
        answers=accepted["answers"],
    )
    result = engine.evaluate(request, calculated_at=calculated_at)
    response = {
        "contract_version": CONTRACT_VERSION,
        "questionnaire_id": result.questionnaire_id,
        "questionnaire_version": result.version,
        "scoring_version": result.model_version,
        "willingness_score": result.willingness_score,
        "capacity_score": result.capacity_score,
        "composite_score": result.composite_score,
        "risk_category": {"code": result.risk_category_code, "label": result.risk_category.value},
        "calculated_at": result.calculated_at,
        "limitation": {"code": LIMITATION_CODE, "message": LIMITATION_MESSAGE},
    }
    # Informational only: distinguish different category bands, not tiny differences.
    willingness_category, _ = engine.map_to_category(result.willingness_score)
    capacity_category, _ = engine.map_to_category(result.capacity_score)
    if willingness_category != capacity_category:
        code = (
            "CAPACITY_BELOW_WILLINGNESS"
            if result.capacity_score < result.willingness_score
            else "WILLINGNESS_BELOW_CAPACITY"
        )
        response["informational_tension"] = {
            "code": code,
            "message": "The two self-reported dimensions are in different model bands. "
            "This is informational context, not a recommendation or suitability decision.",
        }
    return response


def educational_explanation(result: dict[str, Any]) -> dict[str, str]:
    """Describe a server-calculated result without changing scores or adding advice.

    Internal use only: API callers must not supply an unverified result here.
    """
    return {
        "summary": (
            f"The self-reported questionnaire produces the {result['risk_category']['label']} "
            f"model band with a composite score of {result['composite_score']:g}/100."
        ),
        "dimensions": (
            f"Willingness: {result['willingness_score']:g}/100; "
            f"capacity: {result['capacity_score']:g}/100. These describe the answers, "
            "not verified financial circumstances or suitability for an investment."
        ),
        "method": "Five willingness and five capacity answers are normalized to 0–100 "
        "and combined equally by deterministic rules; no model generates the numeric score.",
        "questionnaire_version": result["questionnaire_version"],
        "scoring_version": result["scoring_version"],
        "calculated_at": result["calculated_at"],
        "limitation": LIMITATION_MESSAGE,
    }
