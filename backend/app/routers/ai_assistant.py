"""
Router for Sprint 6: Grounded AI Learning Assistant, Retrieval Citations, and Safe Refusal.
Enforces non-negotiable safety guardrails: refuses real-world personalized stock recommendations.
All endpoints are strictly authenticated behind the current_principal dependency (S1-MI01).
"""

from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request

from app.auth.principal import Principal, get_current_principal
from app.core.responses import APIResponse
from app.schemas.sprint6_ai_alerts import (
    AIChatRequest,
    AIFeedbackRequest,
)
from app.services.ai_service import (
    COMPILED_PROHIBITED_PATTERNS,
    GROUNDED_CORPUS,
    PROHIBITED_ADVICE_KEYWORDS,
    ai_service,
)

__all__ = [
    "router",
    "COMPILED_PROHIBITED_PATTERNS",
    "GROUNDED_CORPUS",
    "PROHIBITED_ADVICE_KEYWORDS",
]

router = APIRouter(prefix="/api/v1/ai", tags=["Sprint 6 - AI Learning Assistant"])


@router.post("/chat", summary="Query the Grounded AI Learning Assistant with Citations")
def chat_ai(
    req: AIChatRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    response = ai_service.generate_chat_response(
        query=req.message,
        user_id=principal.user_id,
        conversation_id=req.conversation_id,
        portfolio_context_id=req.portfolio_context_id,
    )

    if response.intent == "REFUSAL_FINANCIAL_ADVICE":
        return APIResponse.success(
            message="AI response generated with safety refusal",
            data=response.model_dump(),
            correlation_id=correlation_id,
        )

    return APIResponse.success(
        message="Grounded AI response generated",
        data=response.model_dump(),
        correlation_id=correlation_id,
    )


@router.post("/feedback", summary="Submit user feedback on AI responses")
def submit_feedback(
    fb: AIFeedbackRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    record = ai_service.submit_feedback(user_id=principal.user_id, feedback_req=fb)

    return APIResponse.success(
        message="Feedback logged successfully for quality evaluation",
        data=record,
        correlation_id=correlation_id,
    )


@router.get("/feedback", summary="List user feedback on AI responses")
def list_feedback(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
) -> Dict[str, Any]:
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    records = ai_service.list_feedback(user_id=principal.user_id, limit=limit)

    return APIResponse.success(
        message="User feedback retrieved successfully",
        data=records,
        correlation_id=correlation_id,
    )
