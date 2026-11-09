"""
Schemas for Sprint 4: Simulated Order Execution, Cash Ledger, Positions, and Goal Planning.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, List, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

OrderSide = Literal["BUY", "SELL"]
OrderStatus = Literal["PENDING", "FILLED", "REJECTED", "CANCELLED"]


class PaperOrderRequest(BaseModel):
    instrument_id: str = Field(..., min_length=1, max_length=20, description="Security symbol, e.g. AAPL, SPY")
    side: OrderSide = Field(..., description="BUY or SELL")
    quantity: int = Field(..., gt=0, le=100000, description="Positive integer quantity")
    idempotency_key: str = Field(..., min_length=10, max_length=100, description="Unique client key to prevent duplicate orders")


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
    assumptions_statement: str = "Deterministic model based on constant monthly compounding. No guarantee of future performance."
    projections: List[GoalProjection] = Field(default_factory=list)
