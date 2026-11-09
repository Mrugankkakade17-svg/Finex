"""
Schemas for Sprint 5: Privacy Controls, Consent Audit/Export/Delete, and Spending Analytics.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

PrivacyActionType = Literal["EXPORT", "DELETE", "REVOKE_CONSENT"]
PrivacyRequestStatus = Literal["PENDING", "PROCESSING", "COMPLETED", "REJECTED"]


class PrivacyActionRequest(BaseModel):
    action: PrivacyActionType
    reason: Optional[str] = Field(default=None, max_length=200)
    confirm_explicit: bool = Field(..., description="User must explicitly check confirmation")


class PrivacyActionResponse(BaseModel):
    request_id: str
    action: PrivacyActionType
    status: PrivacyRequestStatus
    requested_at: str
    message: str
    download_url: Optional[str] = None


class ConsentAuditRecord(BaseModel):
    consent_version: str
    granted_at: str
    revoked_at: Optional[str] = None
    is_active: bool
    privacy_notice_url: str = "/docs/privacy-policy-v1.md"


class SpendingTransaction(BaseModel):
    transaction_id: str
    date: str
    description_masked: str
    amount: Decimal
    category: str
    is_user_corrected: bool = False


class SpendingUploadSummary(BaseModel):
    upload_id: str
    filename: str
    total_rows_imported: int
    quarantined_rows: int
    total_spend_amount: Decimal
    categories_detected: List[str] = Field(default_factory=list)
    status: str = "PROCESSED"


class CategoryCorrectionRequest(BaseModel):
    transaction_id: str
    corrected_category: str = Field(..., min_length=2, max_length=50)


class MonthlyCategoryTrend(BaseModel):
    month: str
    category: str
    total_amount: Decimal
    transaction_count: int
    percentage_of_month: Decimal


class SpendingTrendResponse(BaseModel):
    period_start: str
    period_end: str
    total_spend: Decimal
    monthly_trends: List[MonthlyCategoryTrend] = Field(default_factory=list)
    top_categories: List[str] = Field(default_factory=list)
    privacy_disclosure: str = "Raw descriptions masked before AI categorization. Calculations are deterministic."

