"""Authenticated, owner-scoped digital-twin summary endpoint."""

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request

from app.auth.principal import Principal, get_current_principal
from app.config.settings import get_settings
from app.core.responses import APIResponse
from app.repositories.paper_trading_repository import PostgresPaperTradingRepository
from app.repositories.spending_repository import spending_repository
from app.services.market_service import market_service
from app.services.paper_trading_service import PaperTradingService
from app.services.portfolio_service import portfolio_service
from app.services.twin_service import TwinService

router = APIRouter(
    prefix="/api/v1/twin",
    tags=["Sprint 4 - Digital Twin"],
    dependencies=[Depends(get_current_principal)],
)


def get_twin_service() -> TwinService:
    settings = get_settings()
    return TwinService(
        portfolio_source=portfolio_service,
        paper_source=PaperTradingService(
            repository=PostgresPaperTradingRepository(settings),
            quotes=market_service,
            settings=settings,
        ),
        spending_source=spending_repository,
    )


@router.get("", summary="Get labelled net-worth figures, runway, and liabilities")
async def get_twin(
    request: Request,
    as_of_date: date | None = Query(
        default=None, description="Optional ISO reference date (YYYY-MM-DD)."
    ),
    principal: Principal = Depends(get_current_principal),
    service: TwinService = Depends(get_twin_service),
):
    """Return separate source-labelled values for the authenticated user."""
    data = await service.snapshot(principal.user_id, as_of=as_of_date)
    return APIResponse.success(
        message="Digital twin snapshot retrieved",
        data=data,
        correlation_id=getattr(request.state, "correlation_id", str(uuid4())),
        data_status="CACHED",
    )

