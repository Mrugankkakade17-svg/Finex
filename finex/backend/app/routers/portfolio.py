from typing import cast

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.core.responses import APIResponse
from app.schemas.envelope import DataStatus
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioUpdate,
)
from app.services.portfolio_service import portfolio_service

router = APIRouter(prefix="/api/v1/portfolios", tags=["Portfolio"])


@router.post("", status_code=201)
async def create_portfolio(
    data: PortfolioCreate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    portfolio = await portfolio_service.create_portfolio(user_id, data)

    return APIResponse.success(
        message="Portfolio created successfully",
        data=portfolio.model_dump(),
        status_code=201,
        correlation_id=request.state.correlation_id,
    )


@router.get("")
async def list_portfolios(
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    portfolios = await portfolio_service.list_portfolios(user_id)

    return APIResponse.success(
        message="Portfolios retrieved successfully",
        data=[p.model_dump() for p in portfolios],
        correlation_id=request.state.correlation_id,
    )


@router.get("/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    portfolio = await portfolio_service.get_portfolio(portfolio_id, user_id)

    return APIResponse.success(
        message="Portfolio retrieved successfully",
        data=portfolio.model_dump(),
        correlation_id=request.state.correlation_id,
    )


@router.put("/{portfolio_id}")
async def update_portfolio(
    portfolio_id: str,
    data: PortfolioUpdate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    portfolio = await portfolio_service.update_portfolio(portfolio_id, user_id, data)

    return APIResponse.success(
        message="Portfolio updated successfully",
        data=portfolio.model_dump(),
        correlation_id=request.state.correlation_id,
    )


@router.delete("/{portfolio_id}")
async def delete_portfolio(
    portfolio_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    await portfolio_service.delete_portfolio(portfolio_id, user_id)

    return APIResponse.success(
        message="Portfolio deleted successfully",
        data={"deleted": True, "portfolio_id": portfolio_id},
        correlation_id=request.state.correlation_id,
    )


# ---------------------------------------------------------------------------
# Holdings Endpoints
# ---------------------------------------------------------------------------


@router.post("/{portfolio_id}/holdings", status_code=201)
async def add_holding(
    portfolio_id: str,
    data: HoldingCreate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    holding = await portfolio_service.add_holding(portfolio_id, user_id, data)

    return APIResponse.success(
        message="Holding added successfully",
        data=holding.model_dump(),
        status_code=201,
        correlation_id=request.state.correlation_id,
    )


@router.get("/{portfolio_id}/holdings")
async def list_holdings(
    portfolio_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    holdings = await portfolio_service.list_holdings(portfolio_id, user_id)

    return APIResponse.success(
        message="Holdings retrieved successfully",
        data=[h.model_dump() for h in holdings],
        correlation_id=request.state.correlation_id,
    )


@router.put("/{portfolio_id}/holdings/{holding_id}")
async def update_holding(
    portfolio_id: str,
    holding_id: str,
    data: HoldingUpdate,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    holding = await portfolio_service.update_holding(holding_id, portfolio_id, user_id, data)

    return APIResponse.success(
        message="Holding updated successfully",
        data=holding.model_dump(),
        correlation_id=request.state.correlation_id,
    )


@router.delete("/{portfolio_id}/holdings/{holding_id}")
async def delete_holding(
    portfolio_id: str,
    holding_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    await portfolio_service.delete_holding(holding_id, portfolio_id, user_id)

    return APIResponse.success(
        message="Holding removed successfully",
        data={"deleted": True, "holding_id": holding_id},
        correlation_id=request.state.correlation_id,
    )


@router.get("/{portfolio_id}/summary")
async def get_portfolio_summary(
    portfolio_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    user_id = user["user_id"]
    summary = await portfolio_service.get_portfolio_summary(portfolio_id, user_id)

    return APIResponse.success(
        message="Portfolio summary calculated successfully",
        data=summary.model_dump(),
        correlation_id=request.state.correlation_id,
        data_status=cast(DataStatus, summary.data_status),
    )
