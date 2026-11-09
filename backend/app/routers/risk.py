"""FastAPI router for FinEx AI Risk Profiling and Structured Explanation (S2-AI-02)."""

from ai.risk.explanation import evaluate_and_explain, explain_risk_assessment
from ai.risk.schemas import (
    RiskAssessmentRequest,
    RiskExplanationRequest,
)
from ai.risk.scoring import calculate_risk_score
from fastapi import APIRouter, Depends, Request, status

from app.auth.dependencies import get_current_user
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.routers.risk_contract import require_local_risk_pilot
from app.schemas.envelope import utc_now_iso
from app.schemas.risk import LegacyRiskAssessmentRequest
from app.services import risk_service

router = APIRouter(
    prefix="/api/v1/risk",
    tags=["Risk Profiling & AI Explanation"],
)


@router.get("/questions")
def get_risk_questions(
    request: Request,
    user: dict = Depends(get_current_user),
):
    result = risk_service.get_risk_questions()

    return APIResponse.success(
        message="Risk questions retrieved successfully",
        data=result,
        correlation_id=request.state.correlation_id,
        data_as_of=utc_now_iso(),
        data_status="LIVE",
    )


@router.post("/assessments")
def create_risk_assessment(
    request: Request,
    assessment: LegacyRiskAssessmentRequest,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]

    result = risk_service.create_risk_assessment(
        user_id=user_id,
        questionnaire_version=assessment.questionnaire_version,
        answers=[answer.model_dump() for answer in assessment.answers],
    )

    return APIResponse.success(
        message="Risk assessment completed successfully",
        data=result,
        correlation_id=request.state.correlation_id,
        data_as_of=utc_now_iso(),
        data_status="LIVE",
    )


@router.post(
    "/evaluate",
    summary="Deterministically calculate risk profile score and breakdown",
    dependencies=[Depends(require_local_risk_pilot)],
)
def evaluate_risk(
    request: Request,
    payload: RiskAssessmentRequest,
):
    """Calculates deterministic risk scores across Willingness and Capacity dimensions."""
    try:
        result = calculate_risk_score(
            answers=payload.answers,
            questionnaire_id=payload.questionnaire_id,
            version=payload.version,
            user_id=payload.user_id,
            calculated_at=payload.calculated_at,
        )
        return APIResponse.success(
            message="Risk assessment calculated successfully",
            data=result.model_dump(),
            correlation_id=getattr(request.state, "correlation_id", "unknown"),
        )
    except ValueError:
        raise FinExException(
            message="Invalid risk assessment input.",
            error_code="INVALID_RISK_ASSESSMENT_INPUT",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        raise FinExException(
            message="The risk score could not be calculated.",
            error_code="RISK_SCORING_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/explain",
    summary="Generate structured beginner-friendly explanation for a risk assessment",
    dependencies=[Depends(require_local_risk_pilot)],
)
def explain_risk(
    request: Request,
    payload: RiskExplanationRequest,
):
    """Generates structured, beginner-friendly explanation citing key factors and disclaimers."""
    try:
        if payload.assessment is not None:
            explanation = explain_risk_assessment(
                assessment=payload.assessment,
                answers=payload.answers,
                force_fallback=payload.force_fallback,
                generated_at=payload.calculated_at,
            )
            data = explanation.model_dump()
        elif payload.answers is not None:
            combined = evaluate_and_explain(
                request=payload,
                force_fallback=payload.force_fallback,
            )
            data = combined.explanation.model_dump()
        else:
            raise ValueError("Either 'assessment' or 'answers' must be provided in request payload")

        return APIResponse.success(
            message="Risk explanation generated successfully",
            data=data,
            correlation_id=getattr(request.state, "correlation_id", "unknown"),
        )
    except ValueError:
        raise FinExException(
            message="Invalid explanation request.",
            error_code="INVALID_EXPLANATION_REQUEST",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        raise FinExException(
            message="The explanation could not be generated.",
            error_code="EXPLANATION_GENERATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@router.post(
    "/evaluate-and-explain",
    summary="One-shot deterministic risk evaluation and structured explanation",
    dependencies=[Depends(require_local_risk_pilot)],
)
def evaluate_and_explain_risk(
    request: Request,
    payload: RiskAssessmentRequest,
):
    """Performs deterministic scoring and generates structured beginner-friendly explanation."""
    try:
        combined = evaluate_and_explain(
            request=payload,
            force_fallback=False,
        )
        return APIResponse.success(
            message="Risk assessment and explanation completed successfully",
            data=combined.model_dump(),
            correlation_id=getattr(request.state, "correlation_id", "unknown"),
        )
    except ValueError:
        raise FinExException(
            message="Invalid risk assessment input.",
            error_code="INVALID_RISK_ASSESSMENT_INPUT",
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:
        raise FinExException(
            message="The assessment and explanation could not be generated.",
            error_code="RISK_EVALUATION_EXPLANATION_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
