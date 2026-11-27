"""Request and response schemas for authenticated paper trading."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PaperSide = Literal["BUY", "SELL"]
PaperExchange = Literal["NYSE", "NASDAQ"]


class PaperOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instrument_id: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.^_-]+$")
    exchange: PaperExchange = "NASDAQ"
    side: PaperSide
    quantity: int = Field(gt=0, le=100_000, strict=True)
    idempotency_key: str = Field(min_length=10, max_length=100)


class PaperOrder(BaseModel):
    order_id: str
    instrument_id: str
    exchange: PaperExchange
    side: PaperSide
    quantity: int
    executed_price: Decimal
    notional: Decimal
    fee: Decimal
    cash_delta: Decimal
    status: Literal["FILLED"]
    quote_freshness: Literal["LIVE", "DELAYED", "CACHED"]
    quote_as_of: str | None = None
    created_at: str
    simulation_notice: str = "SIMULATION ONLY: no real money or broker execution."


class PaperPosition(BaseModel):
    instrument_id: str
    exchange: PaperExchange
    quantity: int
    average_cost: Decimal
    last_price: Decimal
    market_value: Decimal
    unrealized_pnl: Decimal


class PaperAccount(BaseModel):
    account_id: str
    currency: Literal["USD"] = "USD"
    cash_balance: Decimal
    portfolio_value: Decimal
    total_equity: Decimal
    positions: list[PaperPosition] = Field(default_factory=list)
    recent_orders: list[PaperOrder] = Field(default_factory=list)
    is_simulated: Literal[True] = True
