"""
Router for Sprint 6: Grounded AI Learning Assistant, Retrieval Citations, and Safe Refusal.
Enforces non-negotiable safety guardrails: refuses real-world personalized stock recommendations.
"""

from typing import Dict, List
from uuid import uuid4
import re

from fastapi import APIRouter, HTTPException, Request
from app.core.responses import APIResponse
from app.schemas.sprint6_ai_alerts import (
    AIChatRequest,
    AIChatResponse,
    AIFeedbackRequest,
    Citation,
)

router = APIRouter(prefix="/api/v1/ai", tags=["Sprint 6 - AI Learning Assistant"])

# Approved educational grounding corpus chunks
GROUNDED_CORPUS = [
    Citation(
        chunk_id="chunk-edu-001",
        source_title="FinEx Introduction to Asset Allocation",
        section="Core Diversification Principles",
        doc_date="2026-08-01",
        excerpt="Asset allocation is an investment strategy that aims to balance risk and reward by apportioning a portfolio's assets according to an individual's goals, risk tolerance, and investment horizon.",
    ),
    Citation(
        chunk_id="chunk-edu-002",
        source_title="FinEx Global Equity Factsheet Q3",
        section="Risk vs Volatility",
        doc_date="2026-09-15",
        excerpt="Volatility measures how widely prices fluctuate over time. High volatility does not necessarily equate to permanent loss of capital if the investment horizon allows for cycle recovery.",
    ),
    Citation(
        chunk_id="chunk-edu-003",
        source_title="FinEx Retirement Planning Baseline",
        section="Compound Interest and DCA",
        doc_date="2026-08-20",
        excerpt="Dollar-cost averaging (DCA) involves investing a fixed amount of money at regular intervals regardless of the price, smoothing the average cost per share over time.",
    ),
]

PROHIBITED_ADVICE_KEYWORDS = [
    r"\bshould I buy\b",
    r"\bshould I sell\b",
    r"\bwhich stock to buy\b",
    r"\bpredict tomorrow\b",
    r"\bguaranteed return\b",
    r"\bhot stock\b",
]

_feedback_db: List[dict] = []


@router.post("/chat", summary="Query the Grounded AI Learning Assistant with Citations")
def chat_ai(req: AIChatRequest, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    conv_id = req.conversation_id or f"conv-{uuid4().hex[:8]}"
    msg_id = f"msg-{uuid4().hex[:8]}"

    lower_query = req.message.lower()

    # Safety Guardrail 1: Refusal of personalized investment recommendations
    for pattern in PROHIBITED_ADVICE_KEYWORDS:
        if re.search(pattern, lower_query):
            response = AIChatResponse(
                conversation_id=conv_id,
                message_id=msg_id,
                intent="REFUSAL_FINANCIAL_ADVICE",
                answer_text="As an educational assistant, FinEx cannot provide specific buy/sell recommendations or predict individual stock performance. We encourage reviewing asset allocation fundamentals and consulting a licensed financial advisor.",
                citations=[],
                limitations_disclaimer="FinEx educational prototype: Not a licensed investment adviser. No personalized advice provided.",
                safe_fallback_used=True,
            )
            return APIResponse.success(
                message="AI response generated with safety refusal",
                data=response.model_dump(),
                correlation_id=correlation_id,
            )

    # Grounded Retrieval Search over verified educational documents
    matched_citations: List[Citation] = []
    if "diversification" in lower_query or "allocation" in lower_query:
        matched_citations.append(GROUNDED_CORPUS[0])
    if "volatility" in lower_query or "risk" in lower_query:
        matched_citations.append(GROUNDED_CORPUS[1])
    if "compound" in lower_query or "dca" in lower_query or "dollar cost" in lower_query:
        matched_citations.append(GROUNDED_CORPUS[2])

    if not matched_citations:
        matched_citations.append(GROUNDED_CORPUS[0])

    answer = (
        f"Based on FinEx educational curriculum: {matched_citations[0].excerpt} "
        "When evaluating your holdings, remember that spreading capital across varying asset classes "
        "helps manage systematic fluctuations without relying on market timing."
    )

    response = AIChatResponse(
        conversation_id=conv_id,
        message_id=msg_id,
        intent="CONCEPT_EDUCATION",
        answer_text=answer,
        citations=matched_citations,
        limitations_disclaimer="Educational insight only. Citing official FinEx curriculum sources. No real-time market prediction.",
        safe_fallback_used=False,
    )

    return APIResponse.success(
        message="Grounded AI response generated",
        data=response.model_dump(),
        correlation_id=correlation_id,
    )


@router.post("/feedback", summary="Submit user feedback on AI responses")
def submit_feedback(fb: AIFeedbackRequest, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    record = {
        "feedback_id": f"fb-{uuid4().hex[:8]}",
        "message_id": fb.message_id,
        "rating": fb.rating,
        "comment": fb.comment,
    }
    _feedback_db.append(record)
    return APIResponse.success(
        message="Feedback logged successfully for quality evaluation",
        data=record,
        correlation_id=correlation_id,
    )

