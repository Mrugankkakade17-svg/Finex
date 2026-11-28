"""Pydantic schemas for the FinEx Suitability Engine (S3-LI01).

Supports:
- Risk category to educational target allocation
- Portfolio allocation drift calculation
- Deterministic educational rebalance plan generation
- Invariants validation and educational disclaimer transparency
"""

from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from ai.risk.schemas import QuestionAnswer
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.exceptions import SuitabilityException


class RiskCategoryEnum(str, Enum):
    """Canonical risk categories aligned with S2-DAT-02, S3-MR01, and ai.risk."""

    CONSERVATIVE = "CONSERVATIVE"
    MODERATE = "MODERATE"
    AGGRESSIVE = "AGGRESSIVE"

    @classmethod
    def from_str(cls, value: str) -> "RiskCategoryEnum":
        """Normalize and parse case-insensitive risk category string."""
        cleaned = value.strip().upper()
        if cleaned in ("CONSERVATIVE", "CONSERVATIVE_V1"):
            return cls.CONSERVATIVE
        if cleaned in ("MODERATE", "MODERATE_V1"):
            return cls.MODERATE
        if cleaned in ("AGGRESSIVE", "AGGRESSIVE_V1"):
            return cls.AGGRESSIVE
        raise SuitabilityException(
            f"Unsupported risk category '{value}'. Supported categories: {[e.value for e in cls]}",
            error_code="INVALID_RISK_CATEGORY",
            status_code=400,
        )


class AssetClassEnum(str, Enum):
    """Approved asset classes from S3-MR01 allocation model reference."""

    EQUITY = "EQUITY"
    FIXED_INCOME = "FIXED_INCOME"
    CASH = "CASH"


class TargetAllocationItem(BaseModel):
    """An individual asset class target within an educational allocation model."""

    model_config = ConfigDict(extra="forbid")

    asset_class: str = Field(
        ..., description="Asset class identifier (e.g., EQUITY, FIXED_INCOME, CASH)"
    )
    target_weight: Decimal = Field(
        ..., ge=Decimal("0.0"), le=Decimal("1.0"), description="Target fraction [0.0, 1.0]"
    )
    target_pct: Decimal = Field(
        ..., ge=Decimal("0.0"), le=Decimal("100.0"), description="Target percentage [0.0, 100.0]"
    )
    benchmark_symbol: str = Field(..., description="Approved benchmark ETF or index proxy symbol")
    benchmark_name: str = Field(..., description="Human-readable description of proxy benchmark")


class TargetAllocationResponse(BaseModel):
    """Authoritative target allocation result envelope for a given risk category."""

    model_config = ConfigDict(extra="forbid")

    risk_category: str = Field(..., description="Target risk category")
    model_code: str = Field(
        ..., description="Reference allocation model code (e.g. CONSERVATIVE_V1)"
    )
    model_name: str = Field(..., description="Human-readable model name")
    version: str = Field(default="v1", description="Model version")
    description: str = Field(..., description="Educational allocation assumptions and context")
    allocations: List[TargetAllocationItem] = Field(..., description="Target allocation items")
    invariants_satisfied: bool = Field(
        default=True, description="Flag indicating mathematical invariants hold"
    )
    educational_disclaimer: str = Field(..., description="Required educational boundary disclosure")


class CurrentAllocationItem(BaseModel):
    """An asset class observation from a current portfolio."""

    model_config = ConfigDict(extra="forbid")

    asset_class: str = Field(..., description="Asset class identifier")
    weight: Decimal = Field(
        ...,
        ge=Decimal("0.0"),
        description="Weight (fraction [0.0, 1.0] or percentage [0.0, 100.0])",
    )
    value: Optional[Decimal] = Field(
        default=None, ge=Decimal("0.0"), description="Optional monetary value"
    )

    @field_validator("asset_class")
    @classmethod
    def validate_asset_class(cls, v: str) -> str:
        cleaned = v.strip().upper()
        if not cleaned:
            raise ValueError("asset_class cannot be empty")
        return cleaned


class AllocationDriftItem(BaseModel):
    """Drift calculation for an individual asset class."""

    model_config = ConfigDict(extra="forbid")

    asset_class: str = Field(..., description="Asset class identifier")
    current_weight: Decimal = Field(..., description="Current fraction of portfolio")
    current_pct: Decimal = Field(..., description="Current percentage of portfolio")
    target_weight: Decimal = Field(..., description="Target fraction of portfolio")
    target_pct: Decimal = Field(..., description="Target percentage of portfolio")
    drift: Decimal = Field(..., description="Drift fraction (current_weight - target_weight)")
    drift_pct: Decimal = Field(..., description="Drift in percentage points")
    status: Literal["OVERWEIGHT", "UNDERWEIGHT", "BALANCED"] = Field(
        ..., description="Drift status relative to target"
    )
    action: Literal["INCREASE", "REDUCE", "HOLD"] = Field(
        ..., description="Recommended adjustment direction"
    )


class RebalancePlanItem(BaseModel):
    """Educational rebalance recommendation for an individual asset class or proxy."""

    model_config = ConfigDict(extra="forbid")

    asset_class: str = Field(..., description="Asset class identifier")
    current_weight: Decimal = Field(..., description="Current fraction of portfolio")
    target_weight: Decimal = Field(..., description="Target fraction of portfolio")
    drift: Decimal = Field(..., description="Drift fraction")
    adjustment_weight: Decimal = Field(
        ..., description="Required adjustment fraction (-drift = target - current)"
    )
    direction: Literal["INCREASE", "REDUCE", "HOLD"] = Field(..., description="Rebalance direction")
    indicative_amount: Optional[Decimal] = Field(
        default=None,
        description="Indicative rebalance amount in currency, if portfolio value provided",
    )
    benchmark_symbol: Optional[str] = Field(
        default=None, description="Approved proxy ETF or index symbol"
    )
    benchmark_name: Optional[str] = Field(
        default=None, description="Approved proxy benchmark description"
    )
    explanation: str = Field(..., description="Clear educational rationale for the adjustment")


class SuitabilityTargetRequest(BaseModel):
    """Request envelope to resolve target allocation by risk category or questionnaire."""

    model_config = ConfigDict(extra="forbid")

    risk_category: Optional[str] = Field(
        default=None,
        description="Direct risk category string ('CONSERVATIVE', 'MODERATE', 'AGGRESSIVE')",
    )
    questionnaire_answers: Optional[List[QuestionAnswer]] = Field(
        default=None,
        description="Optional questionnaire answers evaluated by existing ai.risk scoring engine",
    )


class SuitabilityRebalanceRequest(BaseModel):
    """Request envelope to calculate portfolio drift and generate educational rebalance plan."""

    model_config = ConfigDict(extra="forbid")

    risk_category: Optional[str] = Field(
        default=None,
        description="Target risk category (if omitted, questionnaire_answers must be provided)",
    )
    questionnaire_answers: Optional[List[QuestionAnswer]] = Field(
        default=None,
        description="Questionnaire answers to derive risk category via ai.risk scoring engine",
    )
    portfolio_id: Optional[str] = Field(
        default=None,
        description="User portfolio UUID to retrieve current holdings with user isolation",
    )
    current_allocation: Optional[List[CurrentAllocationItem]] = Field(
        default=None,
        description="Explicit current allocation items when portfolio_id is not used",
    )
    portfolio_value: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("0.0"),
        description="Optional total portfolio value for calculating indicative amounts",
    )
    drift_threshold: Decimal = Field(
        default=Decimal("0.01"),
        ge=Decimal("0.0"),
        le=Decimal("0.5"),
        description="Threshold (fraction, e.g. 0.01 = 1%) below which drift is BALANCED",
    )


class SuitabilityRebalanceResponse(BaseModel):
    """Authoritative response envelope for suitability drift and rebalance evaluation."""

    model_config = ConfigDict(extra="forbid")

    risk_category: str = Field(..., description="Target risk category")
    model_code: str = Field(..., description="Target allocation model code")
    portfolio_id: Optional[str] = Field(
        default=None, description="Evaluated portfolio UUID, if provided"
    )
    portfolio_value: Optional[Decimal] = Field(
        default=None, description="Evaluated total portfolio value, if known"
    )
    risk_score_summary: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Summary of ai.risk assessment scoring if questionnaire was evaluated",
    )
    drift_summary: List[AllocationDriftItem] = Field(
        ..., description="Per-asset-class drift metrics"
    )
    rebalance_plan: List[RebalancePlanItem] = Field(
        ..., description="Per-asset-class educational rebalance actions"
    )
    max_drift: Decimal = Field(
        ..., description="Maximum absolute drift fraction across all asset classes"
    )
    rebalance_required: bool = Field(
        ..., description="True if any asset class drift exceeds drift_threshold"
    )
    is_empty_portfolio: bool = Field(
        default=False, description="True if portfolio has zero value or no holdings"
    )
    educational_disclaimer: str = Field(..., description="Required educational boundary disclosure")
