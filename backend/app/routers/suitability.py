"""Suitability Engine Router (S3-LI01).

Exposes versioned endpoints for:
- Target educational allocation by risk category or questionnaire scoring
- Portfolio allocation drift calculation
- Educational rebalance plan generation with proxy benchmark instruments
- Strict user-isolation and ownership verification
"""

from typing import cast

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.core.responses import APIResponse
from app.schemas.envelope import DataStatus
from app.schemas.suitability import (
    SuitabilityRebalanceRequest,
    SuitabilityTargetRequest,
)
from app.services.portfolio_service import portfolio_service
from app.services.suitability_service import suitability_service

router = APIRouter(prefix="/api/v1/suitability", tags=["Suitability"])


@router.post("/allocation", status_code=200)
async def get_target_allocation(
    data: SuitabilityTargetRequest,
    request: Request,
):
    """Retrieve target allocation model, asset-class weights, and proxy benchmarks.

    Accepts either direct risk_category or questionnaire_answers evaluated by ai.risk.
    """
    category, _ = suitability_service.resolve_risk_category(
        risk_category=data.risk_category,
        questionnaire_answers=data.questionnaire_answers,
    )
    result = suitability_service.get_target_allocation(category)

    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return APIResponse.success(
        message="Target allocation retrieved successfully",
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
        data_status=cast(DataStatus, "LIVE"),
    )


@router.get("/allocation/{risk_category}", status_code=200)
async def get_target_allocation_by_category(
    risk_category: str,
    request: Request,
):
    """Direct lookup of target allocation model by risk category string."""
    result = suitability_service.get_target_allocation(risk_category)

    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return APIResponse.success(
        message="Target allocation retrieved successfully",
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
        data_status=cast(DataStatus, "LIVE"),
    )


@router.post("/rebalance", status_code=200)
async def evaluate_rebalance_plan(
    data: SuitabilityRebalanceRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Calculate portfolio allocation drift and generate deterministic educational rebalance plan.

    Enforces strict user isolation when portfolio_id is provided.
    """
    user_id = user["user_id"]
    portfolio_summary = None

    if data.portfolio_id:
        # Strictly verify ownership and fetch authenticated user's portfolio summary
        # Raises 404 PORTFOLIO_NOT_FOUND if user does not own portfolio or if it doesn't exist
        portfolio_summary = await portfolio_service.get_portfolio_summary(
            data.portfolio_id, user_id
        )

    result = suitability_service.evaluate_suitability_rebalance(
        request=data,
        portfolio_summary=portfolio_summary,
    )

    correlation_id = getattr(request.state, "correlation_id", "unknown")
    return APIResponse.success(
        message="Suitability rebalance plan generated successfully",
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
        data_status=cast(DataStatus, "LIVE"),
    )
