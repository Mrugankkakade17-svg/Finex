"""
Schemas for Sprint 4: Simulated Order Execution, Cash Ledger, Positions, and Goal Planning.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

OrderSide = Literal["BUY", "SELL"]
OrderStatus = Literal["PENDING", "FILLED", "REJECTED", "CANCELLED"]


def _reject_datetime_for_date(value: Any) -> Any:
    if isinstance(value, datetime):
        raise ValueError("Expected an ISO calendar date (YYYY-MM-DD), not a datetime.")
    return value


def _require_finite_decimal(value: Decimal) -> Decimal:
    if not value.is_finite():
        raise ValueError("Monetary and rate values must be finite decimals.")
    return value


class PaperOrderRequest(BaseModel):
    instrument_id: str = Field(
        ..., min_length=1, max_length=20, description="Security symbol, e.g. AAPL, SPY"
    )
    side: OrderSide = Field(..., description="BUY or SELL")
    quantity: int = Field(..., gt=0, le=100000, description="Positive integer quantity")
    idempotency_key: str = Field(
        ...,
        min_length=10,
        max_length=100,
        description="Unique client key to prevent duplicate orders",
    )


class PaperOrderResponse(BaseModel):
    order_id: str
    instrument_id: str
    side: OrderSide
    quantity: int
    executed_price: Decimal
    total_amount: Decimal
    status: OrderStatus
    timestamp: str
    simulation_notice: str = "SIMULATION ONLY: No real money or broker execution involved."


class CashLedgerEntry(BaseModel):
    entry_id: str
    timestamp: str
    entry_type: Literal["DEPOSIT", "BUY", "SELL", "RESET", "CORRECTION"]
    amount: Decimal
    balance_after: Decimal
    description: str


class PaperPosition(BaseModel):
    instrument_id: str
    quantity: int
    average_cost: Decimal
    current_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal
    unrealized_pnl_pct: Decimal


class PaperAccountSummary(BaseModel):
    account_id: str
    cash_balance: Decimal
    portfolio_value: Decimal
    total_equity: Decimal
    positions: List[PaperPosition] = Field(default_factory=list)
    recent_transactions: List[CashLedgerEntry] = Field(default_factory=list)
    currency: str = "USD"
    is_simulated: bool = True


# Goal Planning Schemas
class GoalCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    target_amount: Decimal = Field(..., gt=0)
    current_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    horizon_years: int = Field(..., gt=0, le=50)
    monthly_contribution: Decimal = Field(default=Decimal("0.00"), ge=0)
    expected_annual_return_pct: Decimal = Field(default=Decimal("6.0"), ge=0, le=30)
    target_date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Goal title must not be blank.")
        return cleaned

    @field_validator(
        "target_amount",
        "current_amount",
        "monthly_contribution",
        "expected_annual_return_pct",
    )
    @classmethod
    def _validate_decimals(cls, value: Decimal) -> Decimal:
        return _require_finite_decimal(value)

    @field_validator("target_date", mode="before")
    @classmethod
    def _validate_target_date(cls, value: Any) -> Any:
        return _reject_datetime_for_date(value)


class GoalUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=100)
    target_amount: Optional[Decimal] = Field(default=None, gt=0)
    current_amount: Optional[Decimal] = Field(default=None, ge=0)
    horizon_years: Optional[int] = Field(default=None, gt=0, le=50)
    monthly_contribution: Optional[Decimal] = Field(default=None, ge=0)
    expected_annual_return_pct: Optional[Decimal] = Field(default=None, ge=0, le=30)
    target_date: Optional[date] = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Goal title must not be blank.")
        return cleaned

    @field_validator(
        "target_amount",
        "current_amount",
        "monthly_contribution",
        "expected_annual_return_pct",
    )
    @classmethod
    def _validate_decimals(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is None:
            return None
        return _require_finite_decimal(value)

    @field_validator("target_date", mode="before")
    @classmethod
    def _validate_target_date(cls, value: Any) -> Any:
        return _reject_datetime_for_date(value)

    @model_validator(mode="after")
    def _validate_non_empty_update(self) -> "GoalUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one goal field must be provided for update.")
        non_nullable = (
            "title",
            "target_amount",
            "current_amount",
            "horizon_years",
            "monthly_contribution",
            "expected_annual_return_pct",
        )
        for field_name in non_nullable:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"Field '{field_name}' cannot be null.")
        return self


class GoalProjection(BaseModel):
    year: int
    projected_balance: Decimal
    contributions_total: Decimal
    growth_total: Decimal


class GoalResponse(BaseModel):
    goal_id: str
    title: str
    target_amount: Decimal
    current_amount: Decimal
    horizon_years: int
    monthly_contribution: Decimal
    expected_annual_return_pct: Decimal
    projected_final_amount: Decimal
    shortfall_or_surplus: Decimal
    is_on_track: bool
    assumptions_statement: str = (
        "Deterministic model based on constant monthly compounding. "
        "No guarantee of future performance."
    )
    projections: List[GoalProjection] = Field(default_factory=list)
    target_date: Optional[date] = None


class GoalContributionCreateRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    contribution_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    note: Optional[str] = Field(default=None, max_length=200)

    @field_validator("amount")
    @classmethod
    def _validate_amount(cls, value: Decimal) -> Decimal:
        return _require_finite_decimal(value)

    @field_validator("contribution_date", mode="before")
    @classmethod
    def _validate_contribution_date(cls, value: Any) -> Any:
        return _reject_datetime_for_date(value)

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class GoalContributionResponse(BaseModel):
    contribution_id: str
    goal_id: str
    amount: Decimal
    contribution_date: date
    note: Optional[str] = None
    created_at: str


class GoalProgressResponse(BaseModel):
    goal_id: str
    title: str
    target_amount: Decimal
    current_amount: Decimal
    remaining_amount: Decimal
    surplus_amount: Decimal
    progress_pct: Decimal
    total_contributed: Decimal
    contributions_count: int
    last_contribution_date: Optional[date] = None
    as_of_date: date
    target_date: Optional[date] = None
    horizon_years: int
    months_remaining: int
    is_overdue: bool
    is_completed: bool
    configured_monthly_contribution: Decimal
    expected_annual_return_pct: Decimal
    required_monthly_contribution: Optional[Decimal] = None
    monthly_contribution_gap: Optional[Decimal] = None
    is_on_track: bool
    formula_summary: str
    assumptions_statement: str


class GoalContributionRecordResponse(BaseModel):
    contribution: GoalContributionResponse
    goal: GoalResponse
    progress: GoalProgressResponse


class GoalDeleteResponse(BaseModel):
    goal_id: str
    deleted: bool = True
