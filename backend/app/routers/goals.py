"""
Router for Sprint 4: Goal Planning, Projections, Contributions, and Progress.
Applies deterministic compounding formulas outside the LLM.
"""

from datetime import date
from typing import Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.principal import Principal, get_current_principal
from app.core.responses import APIResponse
from app.schemas.sprint4_paper_goals import (
    GoalContributionCreateRequest,
    GoalCreateRequest,
    GoalDeleteResponse,
    GoalResponse,
    GoalUpdateRequest,
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
    """Create a financial goal and persist deterministic annual projections."""
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
    """List all financial goals owned by the authenticated principal."""
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
    """Retrieve one principal-scoped financial goal and its projections."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    goal = goal_service.get_goal(principal.user_id, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")

    return APIResponse.success(
        message="Goal details retrieved",
        data=goal.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


@router.put("/{goal_id}", summary="Update a financial goal and recalculate projections")
def update_goal(
    goal_id: str,
    goal_in: GoalUpdateRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Update a principal-scoped goal and persist recalculated projections."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    updated = goal_service.update_goal(principal.user_id, goal_id, goal_in)
    if updated is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    _goals_db[updated.goal_id] = updated

    return APIResponse.success(
        message="Goal updated and projections recalculated successfully",
        data=updated.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


@router.delete("/{goal_id}", summary="Delete a financial goal")
def delete_goal(
    goal_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Delete a principal-scoped goal along with its projections and contributions."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    deleted = goal_service.delete_goal(principal.user_id, goal_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Goal not found.")
    _goals_db.pop(goal_id, None)

    return APIResponse.success(
        message="Goal deleted successfully",
        data=GoalDeleteResponse(goal_id=goal_id, deleted=True).model_dump(mode="json"),
        correlation_id=correlation_id,
    )


@router.post("/{goal_id}/contributions", summary="Record a contribution toward a goal")
def record_goal_contribution(
    goal_id: str,
    contribution_in: GoalContributionCreateRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """Record a contribution toward a principal-scoped goal and recalculate progress."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    result = goal_service.record_contribution(principal.user_id, goal_id, contribution_in)
    if result is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    _goals_db[result.goal.goal_id] = result.goal

    return APIResponse.success(
        message="Goal contribution recorded successfully",
        data=result.model_dump(mode="json"),
        correlation_id=correlation_id,
    )


@router.get("/{goal_id}/contributions", summary="List contributions recorded for a goal")
def list_goal_contributions(
    goal_id: str,
    request: Request,
    principal: Principal = Depends(get_current_principal),
):
    """List recorded contributions for a principal-scoped goal."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    contributions = goal_service.list_contributions(principal.user_id, goal_id)
    if contributions is None:
        raise HTTPException(status_code=404, detail="Goal not found.")

    return APIResponse.success(
        message="Goal contributions retrieved successfully",
        data=[item.model_dump(mode="json") for item in contributions],
        correlation_id=correlation_id,
    )


@router.get("/{goal_id}/progress", summary="Get deterministic goal progress and savings plan")
def get_goal_progress(
    goal_id: str,
    request: Request,
    as_of_date: Optional[date] = Query(
        default=None,
        description="Optional ISO reference date (YYYY-MM-DD) for progress calculation.",
    ),
    principal: Principal = Depends(get_current_principal),
):
    """Retrieve goal progress, contribution totals, and required monthly contribution."""
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    try:
        progress = goal_service.get_goal_progress(principal.user_id, goal_id, as_of_date=as_of_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if progress is None:
        raise HTTPException(status_code=404, detail="Goal not found.")

    return APIResponse.success(
        message="Goal progress retrieved successfully",
        data=progress.model_dump(mode="json"),
        correlation_id=correlation_id,
    )
