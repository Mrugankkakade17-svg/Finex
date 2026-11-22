"""
Service layer for Sprint 6 Grounded AI Assistant and Safe Refusal Guardrails (S1-MI01).
Enforces safety refusal on direct financial advice queries and persists feedback
scoped to principals.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.repositories.ai_feedback_repository import (
    AIFeedbackRepository,
    ai_feedback_repository,
)
from app.schemas.sprint6_ai_alerts import (
    AIChatResponse,
    AIFeedbackRequest,
    Citation,
)

# Approved educational grounding corpus chunks
GROUNDED_CORPUS: List[Citation] = [
    Citation(
        chunk_id="chunk-edu-001",
        source_title="FinEx Introduction to Asset Allocation",
        section="Core Diversification Principles",
        doc_date="2026-08-01",
        excerpt=(
            "Asset allocation is an investment strategy that aims to balance risk and "
            "reward by apportioning a portfolio's assets according to an individual's goals, "
            "risk tolerance, and investment horizon."
        ),
    ),
    Citation(
        chunk_id="chunk-edu-002",
        source_title="FinEx Global Equity Factsheet Q3",
        section="Risk vs Volatility",
        doc_date="2026-09-15",
        excerpt=(
            "Volatility measures how widely prices fluctuate over time. High volatility "
            "does not necessarily equate to permanent loss of capital if the investment "
            "horizon allows for cycle recovery."
        ),
    ),
    Citation(
        chunk_id="chunk-edu-003",
        source_title="FinEx Retirement Planning Baseline",
        section="Compound Interest and DCA",
        doc_date="2026-08-20",
        excerpt=(
            "Dollar-cost averaging (DCA) involves investing a fixed amount of money at regular "
            "intervals regardless of the price, smoothing the average cost per share over time."
        ),
    ),
]

PROHIBITED_ADVICE_KEYWORDS: List[str] = [
    r"\bshould I buy\b",
    r"\bshould I sell\b",
    r"\bwhich stock to buy\b",
    r"\bpredict tomorrow\b",
    r"\bguaranteed return\b",
    r"\bhot stock\b",
]

COMPILED_PROHIBITED_PATTERNS: List[re.Pattern] = [
    re.compile(pattern, re.IGNORECASE) for pattern in PROHIBITED_ADVICE_KEYWORDS
]


class AIService:
    """Business logic for grounded AI responses, safety refusal guardrails, and feedback."""

    def __init__(self, feedback_repo: Optional[AIFeedbackRepository] = None) -> None:
        self.feedback_repo = feedback_repo or ai_feedback_repository
        self.grounded_corpus = GROUNDED_CORPUS
        self.prohibited_patterns = COMPILED_PROHIBITED_PATTERNS

    def generate_chat_response(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        portfolio_context_id: Optional[str] = None,
    ) -> AIChatResponse:
        """
        Process chat query through safety refusal guardrails and educational retriever.
        Refuses direct buy/sell/predict/guarantee advice.
        """
        conv_id = conversation_id or f"conv-{uuid4().hex[:8]}"
        msg_id = f"msg-{uuid4().hex[:8]}"
        lower_query = query.lower()

        # Guardrail: Check prohibited financial advice patterns (case-insensitive)
        for pattern in self.prohibited_patterns:
            if pattern.search(query):
                return AIChatResponse(
                    conversation_id=conv_id,
                    message_id=msg_id,
                    intent="REFUSAL_FINANCIAL_ADVICE",
                    answer_text=(
                        "As an educational assistant, FinEx cannot provide specific buy/sell "
                        "recommendations or predict individual stock performance. We encourage "
                        "reviewing asset allocation fundamentals and consulting a licensed "
                        "financial advisor."
                    ),
                    citations=[],
                    limitations_disclaimer=(
                        "FinEx educational prototype: Not a licensed investment adviser. "
                        "No personalized advice provided."
                    ),
                    safe_fallback_used=True,
                )

        # Grounded retrieval search over approved educational documents
        matched_citations: List[Citation] = []
        if "diversification" in lower_query or "allocation" in lower_query:
            matched_citations.append(self.grounded_corpus[0])
        if "volatility" in lower_query or "risk" in lower_query:
            matched_citations.append(self.grounded_corpus[1])
        if "compound" in lower_query or "dca" in lower_query or "dollar cost" in lower_query:
            matched_citations.append(self.grounded_corpus[2])

        if not matched_citations:
            matched_citations.append(self.grounded_corpus[0])

        answer = (
            f"Based on FinEx educational curriculum: {matched_citations[0].excerpt} "
            "When evaluating your holdings, remember that spreading capital across varying "
            "asset classes helps manage systematic fluctuations without relying on market timing."
        )

        return AIChatResponse(
            conversation_id=conv_id,
            message_id=msg_id,
            intent="CONCEPT_EDUCATION",
            answer_text=answer,
            citations=matched_citations,
            limitations_disclaimer=(
                "Educational insight only. Citing official FinEx curriculum sources. "
                "No real-time market prediction."
            ),
            safe_fallback_used=False,
        )

    def submit_feedback(
        self,
        user_id: str,
        feedback_req: AIFeedbackRequest,
    ) -> Dict[str, Any]:
        """Validate and persist feedback record strictly scoped to user_id."""
        return self.feedback_repo.create_feedback(
            user_id=user_id,
            message_id=feedback_req.message_id,
            rating=feedback_req.rating,
            comment=feedback_req.comment,
        )

    def list_feedback(
        self,
        user_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve feedback records for the authenticated user."""
        return self.feedback_repo.list_feedback_by_user(user_id=user_id, limit=limit)

    def get_feedback(
        self,
        user_id: str,
        feedback_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a single feedback record scoped to the authenticated user."""
        return self.feedback_repo.get_feedback(user_id=user_id, feedback_id=feedback_id)


ai_service = AIService()
