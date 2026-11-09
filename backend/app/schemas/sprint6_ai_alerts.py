"""
Schemas for Sprint 6: Grounded AI Learning Assistant, Feedback, and Smart Alert Rules / Notifications.
"""

from datetime import datetime, timezone
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

IntentType = Literal[
    "CONCEPT_EDUCATION",
    "PORTFOLIO_EXPLANATION",
    "COMPARISON",
    "GENERAL_QUERY",
    "REFUSAL_UNSUPPORTED",
    "REFUSAL_FINANCIAL_ADVICE",
]


class Citation(BaseModel):
    chunk_id: str
    source_title: str
    section: str
    doc_date: str
    excerpt: str


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    conversation_id: Optional[str] = None
    portfolio_context_id: Optional[str] = None


class AIChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    intent: IntentType
    answer_text: str
    citations: List[Citation] = Field(default_factory=list)
    limitations_disclaimer: str
    model_version: str = "finex-grounded-rag-v1"
    prompt_version: str = "prompts/ai_assistant_v1.md"
    safe_fallback_used: bool = False


class AIFeedbackRequest(BaseModel):
    message_id: str
    rating: Literal["THUMBS_UP", "THUMBS_DOWN"]
    comment: Optional[str] = Field(default=None, max_length=500)


class AlertRuleCreate(BaseModel):
    rule_name: str = Field(..., min_length=2, max_length=80)
    condition_type: Literal["PRICE_THRESHOLD", "PCT_CHANGE", "CONCENTRATION_LIMIT", "GOAL_OFF_TRACK"]
    target_symbol_or_goal: str = Field(..., min_length=1, max_length=40)
    comparison_operator: Literal["GT", "LT", "GTE", "LTE", "EQ"]
    threshold_value: float
    cooldown_minutes: int = Field(default=60, ge=5, le=1440)


class AlertRule(BaseModel):
    rule_id: str
    rule_name: str
    condition_type: str
    target_symbol_or_goal: str
    comparison_operator: str
    threshold_value: float
    cooldown_minutes: int
    is_active: bool = True
    created_at: str


class NotificationItem(BaseModel):
    notification_id: str
    rule_id: Optional[str]
    title: str
    body: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    created_at: str
    is_read: bool = False

