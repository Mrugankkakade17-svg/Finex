from datetime import date, timedelta
from typing import Literal, cast

from fastapi import APIRouter, Depends, Query, Request

from app.auth.dependencies import get_current_user
from app.config.settings import get_settings
from app.core.responses import APIResponse
from app.schemas.envelope import DataStatus
from app.schemas.portfolio import (
    HoldingCreate,
    HoldingUpdate,
    PortfolioCreate,
    PortfolioUpdate,
)
from app.services.portfolio_analytics_service import (
    align_close_price_history,
    calculate_portfolio_analytics,
    fetch_close_price_history,
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
        data=portfolio.model_dump(mode="json"),
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
        data=[p.model_dump(mode="json") for p in portfolios],
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
        data=portfolio.model_dump(mode="json"),
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
        data=portfolio.model_dump(mode="json"),
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
        data=holding.model_dump(mode="json"),
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
        data=[h.model_dump(mode="json") for h in holdings],
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
        data=holding.model_dump(mode="json"),
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
        data=summary.model_dump(mode="json"),
        correlation_id=request.state.correlation_id,
        data_status=cast(DataStatus, summary.data_status),
    )


@router.get("/{portfolio_id}/analytics")
async def get_portfolio_analytics(
    portfolio_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
    benchmark: str = Query(default="SPY", min_length=1, max_length=20),
    top_n: int = Query(default=5, ge=1, le=100),
    confidence_level: Literal[0.95, 0.99] = Query(default=0.95),
):
    """Return current concentration plus history-dependent risk metrics."""
    portfolio = await portfolio_service.get_portfolio(portfolio_id, user["user_id"])
    holdings = await portfolio_service.list_holdings(portfolio_id, user["user_id"])
    settings = get_settings()
    symbols = [holding.symbol for holding in holdings]
    price_history: dict[str, list[float]] = {}
    benchmark_prices: list[float] | None = None
    if symbols:
        end_date = date.today()
        start_date = end_date - timedelta(days=365)
        try:
            market_history = fetch_close_price_history(
                [*symbols, benchmark],
                currency=portfolio.currency,
                start_date=start_date,
                end_date=end_date,
            )
            price_history, benchmark_prices = align_close_price_history(
                market_history, symbols, benchmark
            )
        except Exception:
            # Market history may not be provisioned in local or test environments.
            price_history, benchmark_prices = {}, None
    result = calculate_portfolio_analytics(
        portfolio_id=portfolio_id,
        holdings=[
            {
                "symbol": holding.symbol,
                "quantity": holding.quantity,
                "current_value": holding.current_value,
            }
            for holding in holdings
        ],
        price_history=price_history,
        benchmark_prices=benchmark_prices,
        benchmark_symbol=benchmark,
        confidence_level=confidence_level,
        top_n=top_n,
        risk_free_rate_annual=settings.analytics_risk_free_rate,
        risk_free_rate_source=settings.analytics_risk_free_rate_source,
        risk_free_rate_as_of=settings.analytics_risk_free_rate_as_of,
    )
    return APIResponse.success(
        message="Portfolio analytics calculated successfully",
        data=result,
        correlation_id=request.state.correlation_id,
        data_status="UNAVAILABLE" if result["status"] == "INSUFFICIENT_DATA" else "CACHED",
    )
