"""Authenticated paper trading API backed by the append-only paper ledger."""

from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Request

from app.auth.principal import Principal, get_current_principal
from app.config.settings import get_settings
from app.core.responses import APIResponse
from app.repositories.paper_trading_repository import PostgresPaperTradingRepository
from app.schemas.paper import PaperAccount, PaperOrder, PaperOrderRequest
from app.services.market_service import market_service
from app.services.paper_trading_service import PaperTradingService

router = APIRouter(
    prefix="/api/v1/paper",
    tags=["Sprint 2 - Paper Trading"],
    dependencies=[Depends(get_current_principal)],
)


def get_paper_trading_service() -> PaperTradingService:
    settings = get_settings()
    return PaperTradingService(
        repository=PostgresPaperTradingRepository(settings),
        quotes=market_service,
        settings=settings,
    )


def _correlation(request: Request) -> str:
    return getattr(request.state, "correlation_id", str(uuid4()))


@router.get("/account", summary="Get the authenticated user's paper account and positions")
def get_account(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    account = PaperAccount.model_validate(service.get_account(principal.user_id))
    return APIResponse.success(
        message="Paper account retrieved",
        data=account.model_dump(mode="json"),
        correlation_id=_correlation(request),
        data_status="CACHED",
    )


@router.get("/positions", summary="List the authenticated user's open paper positions")
def get_positions(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    account = PaperAccount.model_validate(service.get_account(principal.user_id))
    return APIResponse.success(
        message="Paper positions retrieved",
        data=[position.model_dump(mode="json") for position in account.positions],
        correlation_id=_correlation(request),
        data_status="CACHED",
    )


@router.get("/orders", summary="List recent paper orders")
def get_orders(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    principal: Principal = Depends(get_current_principal),
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    orders = [
        PaperOrder.model_validate(row)
        for row in service.list_orders(principal.user_id, limit=limit)
    ]
    return APIResponse.success(
        message="Paper orders retrieved",
        data=[order.model_dump(mode="json") for order in orders],
        correlation_id=_correlation(request),
        data_status="CACHED",
    )


@router.post("/orders", status_code=201, summary="Place an idempotent paper market order")
async def place_order(
    order: PaperOrderRequest,
    request: Request,
    principal: Principal = Depends(get_current_principal),
    service: PaperTradingService = Depends(get_paper_trading_service),
):
    record, created = await service.submit_order(principal.user_id, order)
    response = PaperOrder.model_validate(service.order_dict(record))
    return APIResponse.success(
        message="Paper order filled" if created else "Paper order replayed",
        data=response.model_dump(mode="json"),
        status_code=201 if created else 200,
        correlation_id=_correlation(request),
        data_status=response.quote_freshness,
    )
