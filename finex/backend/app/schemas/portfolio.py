from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.envelope import DataStatus


class AssetClass(str, Enum):
    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    CASH = "CASH"
    CRYPTO = "CRYPTO"
    COMMODITY = "COMMODITY"
    REAL_ESTATE = "REAL_ESTATE"


class PortfolioType(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    RETIREMENT = "RETIREMENT"
    GROWTH = "GROWTH"
    BALANCED = "BALANCED"
    CONSERVATIVE = "CONSERVATIVE"
    TRADING = "TRADING"


# ---------------------------------------------------------------------------
# Holdings Schemas
# ---------------------------------------------------------------------------


class HoldingCreate(BaseModel):
    symbol: str = Field(
        ...,
        description="Ticker symbol (e.g. AAPL, MSFT, BND)",
        min_length=1,
        max_length=20,
    )
    asset_class: AssetClass = Field(
        default=AssetClass.EQUITY,
        description="Asset class category",
    )
    sector: Optional[str] = Field(
        None,
        description="Industry sector (e.g. Technology, Healthcare)",
    )
    quantity: float = Field(..., gt=0, description="Quantity held (must be greater than 0)")
    avg_buy_price: float = Field(..., ge=0, description="Average cost basis per share / unit")
    notes: Optional[str] = Field(None, max_length=500, description="Optional notes for holding")

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, v: str) -> str:
        return v.strip().upper()


class HoldingUpdate(BaseModel):
    quantity: Optional[float] = Field(None, gt=0, description="Updated quantity held")
    avg_buy_price: Optional[float] = Field(None, ge=0, description="Updated average buy price")
    sector: Optional[str] = Field(None, description="Updated industry sector")
    asset_class: Optional[AssetClass] = Field(None, description="Updated asset class")
    notes: Optional[str] = Field(None, max_length=500)


class HoldingResponse(BaseModel):
    holding_id: str
    portfolio_id: str
    user_id: str
    symbol: str
    asset_class: AssetClass
    sector: Optional[str] = "General"
    quantity: float
    avg_buy_price: float
    current_price: float
    current_value: float
    total_cost: float
    unrealized_gain_loss: float
    unrealized_gain_loss_pct: float
    weight_pct: float
    is_stale: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Portfolio Schemas
# ---------------------------------------------------------------------------


class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Portfolio name")
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional description",
    )
    portfolio_type: PortfolioType = Field(
        default=PortfolioType.INDIVIDUAL,
        description="Type of portfolio",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="Base currency ISO code",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Portfolio name cannot be empty or whitespace only")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        return v.strip().upper()


class PortfolioUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    portfolio_type: Optional[PortfolioType] = None
    currency: Optional[str] = Field(None, min_length=3, max_length=3)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if not cleaned:
                raise ValueError("Portfolio name cannot be empty or whitespace only")
            return cleaned
        return v


class PortfolioResponse(BaseModel):
    portfolio_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    portfolio_type: PortfolioType
    currency: str
    total_value: float = 0.0
    total_cost: float = 0.0
    total_gain_loss: float = 0.0
    total_gain_loss_pct: float = 0.0
    holdings_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Allocation & Summary Schemas
# ---------------------------------------------------------------------------


class AllocationItem(BaseModel):
    category: str
    value: float
    percentage: float


class PortfolioSummaryResponse(BaseModel):
    portfolio_id: str
    name: str
    currency: str
    total_value: float
    total_cost: float
    total_gain_loss: float
    total_gain_loss_pct: float
    holdings_count: int
    data_status: DataStatus = "LIVE"
    asset_allocation: List[AllocationItem]
    sector_allocation: List[AllocationItem]
    top_performers: List[HoldingResponse]
