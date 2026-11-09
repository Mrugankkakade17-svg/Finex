# backend/app/schemas/c1.py
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# The mandatory standard response envelope metadata
class MetaData(BaseModel):
    correlationId: str
    apiVersion: str = "v1"
    dataAsOf: Optional[str] = None
    dataStatus: str = "LIVE"


# The mandatory standard response wrapper
class APIResponse(BaseModel, Generic[T]):
    data: T
    meta: MetaData


# Schema for creating a new portfolio (POR-01)
class PortfolioCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field("MANUAL", pattern="^(MANUAL|PAPER)$")
    base_currency: str = Field("USD", min_length=3, max_length=3)


# Schema for adding a holding to a portfolio (POR-02)
class HoldingRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=10)
    quantity: float = Field(..., gt=0)
    average_cost: float = Field(..., ge=0)
    currency: str = Field("USD", min_length=3, max_length=3)


# Schema for the portfolio response data
class PortfolioResponse(BaseModel):
    portfolio_id: str
    user_id: str
    name: str
    type: str
    base_currency: str
    status: str
    created_at: str
