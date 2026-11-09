"""Typed, stateless local-pilot HTTP adapter for Sprint 2 risk profiling."""

from typing import Any

from ai.risk.contract import (
    LIMITATION_CODE,
    LIMITATION_MESSAGE,
    RiskContractError,
    educational_explanation,
)
from ai.risk.scoring import RiskScoringEngine
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.config.settings import AppEnv
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.ports.assessment_scorer import AssessmentScorer
from app.schemas.envelope import SuccessEnvelope
from app.schemas.risk_contract import (
    QuestionnaireResponse,
    RiskContractRequest,
    RiskContractResult,
    RiskErrorEnvelope,
    RiskSubmissionResponse,
)
from app.services.risk_contract_service import get_assessment_scorer


def require_local_risk_pilot(request: Request) -> None:
    """No anonymous risk endpoint may become a deployed auth bypass."""
    if request.app.state.settings.app_env != AppEnv.LOCAL:
        raise FinExException(
            message="This stateless educational pilot is available only in local development.",
            error_code="LOCAL_PILOT_ONLY",
            status_code=403,
        )


router = APIRouter(
    prefix="/api/v1/risk-contract",
    tags=["Sprint 2 risk contract (local pilot)"],
    dependencies=[Depends(require_local_risk_pilot)],
)
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    code: {"model": RiskErrorEnvelope} for code in (400, 403, 422, 500)
}


@router.get(
    "/questionnaire",
    response_model=SuccessEnvelope[QuestionnaireResponse],
    responses=ERROR_RESPONSES,
    summary="Read the versioned educational questionnaire (local only)",
)
def questionnaire(request: Request) -> JSONResponse:
    try:
        engine = RiskScoringEngine()
        questions = [
            {
                "question_id": item["question_id"],
                "dimension": item["dimension"],
                "text": item["text"],
                "options": [
                    {"code": option["code"], "label": option["label"]} for option in item["answers"]
                ],
            }
            for item in engine.config["questions"]
        ]
        data = QuestionnaireResponse.model_validate(
            {
                "questions": questions,
                "limitation": {"code": LIMITATION_CODE, "message": LIMITATION_MESSAGE},
            }
        )
    except Exception:
        raise FinExException(
            message="The questionnaire is currently unavailable.",
            error_code="RISK_ASSESSMENT_UNAVAILABLE",
            status_code=500,
        ) from None
    return APIResponse.success(
        message="Versioned educational questionnaire",
        data=data.model_dump(mode="json"),
        correlation_id=request.state.correlation_id,
    )


@router.post(
    "/assessments",
    response_model=SuccessEnvelope[RiskSubmissionResponse],
    responses=ERROR_RESPONSES,
    summary="Calculate a versioned, non-persisted educational assessment (local only)",
    description="No identity, client-supplied score, or client timestamp is accepted. "
    "Scores/category are deterministic; server timestamps and correlation IDs may differ.",
)
def assess(
    request: Request,
    payload: RiskContractRequest,
    scorer: AssessmentScorer = Depends(get_assessment_scorer),
) -> JSONResponse:
    try:
        result = RiskContractResult.model_validate(scorer.score(payload.model_dump()))
        explanation = educational_explanation(result.model_dump(exclude_none=True))
        data = RiskSubmissionResponse.model_validate(
            {
                "assessment": result,
                "explanation": explanation,
            }
        )
    except RiskContractError as exc:
        raise FinExException(message=str(exc), error_code=exc.code, status_code=400) from None
    except Exception:
        raise FinExException(
            message="The assessment could not be calculated. Please retry.",
            error_code="RISK_ASSESSMENT_UNAVAILABLE",
            status_code=500,
        ) from None
    return APIResponse.success(
        message="Educational assessment calculated",
        data=data.model_dump(mode="json", exclude_none=True),
        correlation_id=request.state.correlation_id,
        data_as_of=result.calculated_at,
    )
