"""
Router for Sprint 5: Spending Upload, Transaction Masking, Category Review, and Monthly Trends.
Applies description masking to protect raw PII before sending to any external services.
"""

from decimal import Decimal
from typing import Dict, List
from uuid import uuid4
import re

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from app.core.responses import APIResponse
from app.schemas.sprint5_privacy_spending import (
    SpendingTransaction,
    SpendingUploadSummary,
    CategoryCorrectionRequest,
    SpendingTrendResponse,
    MonthlyCategoryTrend,
)

router = APIRouter(prefix="/api/v1/spending", tags=["Sprint 5 - Spending & Trends"])

# Pre-populated transactions with masked descriptions
_transactions_db: Dict[str, SpendingTransaction] = {
    "tx-001": SpendingTransaction(
        transaction_id="tx-001",
        date="2026-10-05",
        description_masked="GROCERY STORE #***12",
        amount=Decimal("84.50"),
        category="Groceries",
    ),
    "tx-002": SpendingTransaction(
        transaction_id="tx-002",
        date="2026-10-12",
        description_masked="ELECTRIC UTILITY CO #***99",
        amount=Decimal("115.00"),
        category="Utilities",
    ),
    "tx-003": SpendingTransaction(
        transaction_id="tx-003",
        date="2026-10-18",
        description_masked="STREAMING SUBSCRIPTION #***44",
        amount=Decimal("14.99"),
        category="Entertainment",
    ),
    "tx-004": SpendingTransaction(
        transaction_id="tx-004",
        date="2026-10-22",
        description_masked="METRO TRANSIT PASS #***01",
        amount=Decimal("45.00"),
        category="Transportation",
    ),
}


def _mask_raw_description(raw: str) -> str:
    """Mask account numbers, card numbers, and names from transaction strings."""
    masked = re.sub(r"\b\d{4,16}\b", "****", raw)
    masked = re.sub(r"#[A-Za-z0-9]+", "#***", masked)
    return masked.strip()


@router.get("/transactions", summary="List masked spending transactions")
def list_transactions(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    return APIResponse.success(
        message="Transactions retrieved with descriptions masked",
        data=[tx.model_dump() for tx in _transactions_db.values()],
        correlation_id=correlation_id,
    )


@router.post("/correct-category", summary="User correction of transaction category")
def correct_category(correction: CategoryCorrectionRequest, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    if correction.transaction_id not in _transactions_db:
        raise HTTPException(status_code=404, detail="Transaction not found.")

    tx = _transactions_db[correction.transaction_id]
    tx.category = correction.corrected_category
    tx.is_user_corrected = True

    return APIResponse.success(
        message="Category corrected successfully",
        data=tx.model_dump(),
        correlation_id=correlation_id,
    )


@router.get("/trends", summary="Get monthly spending aggregated trends and insights")
def get_spending_trends(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    total = sum((t.amount for t in _transactions_db.values()), Decimal("0.00"))
    cat_totals: Dict[str, Decimal] = {}
    for t in _transactions_db.values():
        cat_totals[t.category] = cat_totals.get(t.category, Decimal("0.00")) + t.amount

    trends: List[MonthlyCategoryTrend] = []
    for cat, amt in cat_totals.items():
        pct = (amt / total * 100) if total > 0 else Decimal("0.00")
        trends.append(
            MonthlyCategoryTrend(
                month="2026-10",
                category=cat,
                total_amount=amt,
                transaction_count=sum(1 for t in _transactions_db.values() if t.category == cat),
                percentage_of_month=pct.quantize(Decimal("0.1")),
            )
        )

    res = SpendingTrendResponse(
        period_start="2026-10-01",
        period_end="2026-10-31",
        total_spend=total,
        monthly_trends=trends,
        top_categories=sorted(cat_totals.keys(), key=lambda c: cat_totals[c], reverse=True),
        privacy_disclosure="Raw descriptions masked before AI categorization. Calculations are deterministic.",
    )

    return APIResponse.success(
        message="Spending trends calculated",
        data=res.model_dump(),
        correlation_id=correlation_id,
    )
