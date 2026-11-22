"""
Router for Sprint 4: Goal Planning, Projections, and Scenario Modelling.
Applies deterministic compounding formulas outside the LLM.
"""

from typing import Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.principal import Principal, get_current_principal
from app.core.responses import APIResponse
from app.schemas.sprint4_paper_goals import (
    GoalCreateRequest,
    GoalResponse,
)
from app.services.goal_service import goal_service

router = APIRouter(
    prefix="/api/v1/goals",
    tags=["Sprint 4 - Goals & Planning"],
    dependencies=[Depends(get_current_principal)],
)

# Backwards-compatible test/inspection seam. Route data is repository-owned.
_goals_db: Dict[str, GoalResponse] = {}
_calculate_goal_projections = goal_service.calculate_goal_projections


@router.post("", summary="Create a new financial goal with projections")
def create_goal(
    goal_in: GoalCreateRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    goal = goal_service.create_goal(principal.user_id, goal_in)
    _goals_db[goal.goal_id] = goal

    return APIResponse.success(
        message="Goal created and projections calculated successfully",
        data=goal.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


@router.get("", summary="List all saved financial goals")
def list_goals(
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    goals = goal_service.list_goals(principal.user_id)
    return APIResponse.success(
        message="Goals retrieved successfully",
        data=[goal.model_dump(mode="json") for goal in goals],
        correlation_id=correlation_id,
    )


@router.get("/{goal_id}", summary="Get goal details and projections by ID")
def get_goal(
    goal_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    goal = goal_service.get_goal(principal.user_id, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")

    return APIResponse.success(
        message="Goal details retrieved",
        data=goal.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
