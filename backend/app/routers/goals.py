"""
Router for Sprint 4: Goal Planning, Projections, and Scenario Modelling.
Applies deterministic compounding formulas outside the LLM.
"""

from decimal import Decimal
from typing import Dict, List
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from app.core.responses import APIResponse
from app.schemas.sprint4_paper_goals import (
    GoalCreateRequest,
    GoalResponse,
    GoalProjection,
)

router = APIRouter(prefix="/api/v1/goals", tags=["Sprint 4 - Goals & Planning"])

_goals_db: Dict[str, GoalResponse] = {}


def _calculate_goal_projections(
    current_amount: Decimal,
    monthly_contribution: Decimal,
    horizon_years: int,
    annual_rate_pct: Decimal,
    target_amount: Decimal,
) -> tuple[Decimal, List[GoalProjection], bool]:
    """Deterministic compound interest with regular monthly deposits."""
    r_monthly = (annual_rate_pct / Decimal("100")) / Decimal("12")
    balance = current_amount
    total_contributions = current_amount
    projections: List[GoalProjection] = []

    for year in range(1, horizon_years + 1):
        for _ in range(12):
            balance = (balance + monthly_contribution) * (Decimal("1") + r_monthly)
            total_contributions += monthly_contribution
        
        growth = balance - total_contributions
        projections.append(
            GoalProjection(
                year=year,
                projected_balance=balance.quantize(Decimal("0.01")),
                contributions_total=total_contributions.quantize(Decimal("0.01")),
                growth_total=growth.quantize(Decimal("0.01")),
            )
        )

    final_bal = projections[-1].projected_balance if projections else current_amount
    is_on_track = final_bal >= target_amount
    return final_bal, projections, is_on_track


@router.post("", summary="Create a new financial goal with projections")
def create_goal(goal_in: GoalCreateRequest, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    goal_id = f"goal-{uuid4().hex[:8]}"

    final_bal, projections, is_on_track = _calculate_goal_projections(
        current_amount=goal_in.current_amount,
        monthly_contribution=goal_in.monthly_contribution,
        horizon_years=goal_in.horizon_years,
        annual_rate_pct=goal_in.expected_annual_return_pct,
        target_amount=goal_in.target_amount,
    )

    diff = final_bal - goal_in.target_amount

    goal = GoalResponse(
        goal_id=goal_id,
        title=goal_in.title,
        target_amount=goal_in.target_amount,
        current_amount=goal_in.current_amount,
        horizon_years=goal_in.horizon_years,
        monthly_contribution=goal_in.monthly_contribution,
        expected_annual_return_pct=goal_in.expected_annual_return_pct,
        projected_final_amount=final_bal,
        shortfall_or_surplus=diff.quantize(Decimal("0.01")),
        is_on_track=is_on_track,
        assumptions_statement="Deterministic model based on constant monthly compounding. No guarantee of future performance.",
        projections=projections,
    )
    _goals_db[goal_id] = goal

    return APIResponse.success(
        message="Goal created and projections calculated successfully",
        data=goal.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


@router.get("", summary="List all saved financial goals")
def list_goals(request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    return APIResponse.success(
        message="Goals retrieved successfully",
        data=[g.model_dump(mode="json") for g in _goals_db.values()],
        correlation_id=correlation_id,
    )


@router.get("/{goal_id}", summary="Get goal details and projections by ID")
def get_goal(goal_id: str, request: Request):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    if goal_id not in _goals_db:
        raise HTTPException(status_code=404, detail="Goal not found.")
    
    return APIResponse.success(
        message="Goal details retrieved",
        data=_goals_db[goal_id].model_dump(mode="json"),
        correlation_id=correlation_id,
    )
