"""Owned manual portfolios; synthetic valuation is never live market data."""

from threading import Lock
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse

from app.auth.local_boundary import require_local_application
from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.domain.local_application import Clock, LocalStoreUnavailable
from app.domain.local_portfolio import LocalCatalogUnavailable, LocalQuoteUnavailable
from app.ports.adapters.sqlite_local_portfolio_store import SQLiteLocalPortfolioStore
from app.ports.local_portfolio_quotes import LocalPortfolioCatalogPort, LocalPortfolioQuotePort
from app.ports.local_portfolio_store import LocalPortfolioStore
from app.routers.local_application import local_bearer
from app.schemas.envelope import DataStatus, ErrorEnvelope, SuccessEnvelope
from app.schemas.local_portfolio import (
    LocalHolding,
    LocalHoldingCreateRequest,
    LocalHoldingDeletion,
    LocalHoldingList,
    LocalHoldingUpdateRequest,
    LocalPortfolio,
    LocalPortfolioCatalog,
    LocalPortfolioDeletion,
    LocalPortfolioList,
    LocalPortfolioMetrics,
    LocalPortfolioRequest,
    LocalPortfolioScope,
)
from app.schemas.local_risk import UUID4_PATTERN
from app.services.local_authorization import utc_clock, validate_token
from app.services.local_portfolio_service import LocalPortfolioService

ResourceId = Annotated[str, Path(pattern=UUID4_PATTERN, min_length=36, max_length=36)]
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 422, 503)
}


def storage_unavailable() -> FinExException:
    return FinExException(
        message="Local storage is unavailable. Nothing was confirmed saved; please retry.",
        error_code="LOCAL_STORE_UNAVAILABLE",
        status_code=503,
    )


def get_local_portfolio_service(
    request: Request,
    token: str = Depends(local_bearer),
    _: None = Depends(require_local_application),
) -> LocalPortfolioService:
    # Validate before lazy construction, including when another injected capability is absent.
    validate_token(token)
    state = request.app.state
    lock: Lock = state.local_portfolio_service_lock
    with lock:
        if state.local_portfolio_service is None:
            settings: Settings = state.settings
            store: LocalPortfolioStore | None = state.local_portfolio_store
            if store is None:
                if (
                    state.local_application_store is not None
                    or state.local_risk_store is not None
                    or state.local_foundation_store is not None
                ):
                    raise storage_unavailable()
                store = SQLiteLocalPortfolioStore(settings.local_db_path)
            clock: Clock = state.local_clock if state.local_clock is not None else utc_clock
            catalogue: LocalPortfolioCatalogPort | None = state.local_portfolio_catalogue
            quotes: LocalPortfolioQuotePort | None = state.local_portfolio_quotes
            service = LocalPortfolioService(store, clock, catalogue=catalogue, quotes=quotes)
            state.local_portfolio_service = service
        service = state.local_portfolio_service
    return service


def respond(
    request: Request,
    operation: Callable[[], LocalPortfolioScope],
    message: str,
    *,
    status_code: int = 200,
) -> JSONResponse:
    try:
        result = operation()
    except LocalStoreUnavailable:
        raise storage_unavailable() from None
    except LocalCatalogUnavailable:
        raise FinExException(
            message="The local synthetic instrument catalogue is unavailable. Please retry later.",
            error_code="LOCAL_CATALOG_UNAVAILABLE",
            status_code=503,
        ) from None
    except LocalQuoteUnavailable:
        raise FinExException(
            message="The local synthetic quote snapshot is unavailable. "
            "No valuation was confirmed.",
            error_code="LOCAL_QUOTE_UNAVAILABLE",
            status_code=503,
        ) from None
    data_status: DataStatus = "CACHED"
    data_as_of: str | None = None
    if isinstance(result, (LocalPortfolio, LocalHolding)):
        data_as_of = result.updated_at
    elif isinstance(result, LocalPortfolioMetrics):
        if result.valuation_status == "COMPLETE":
            data_as_of = result.fixture_as_of
        elif result.valuation_status in {"INCOMPLETE", "UNAVAILABLE"}:
            data_status = "UNAVAILABLE"
    return APIResponse.success(
        message=message,
        data=result.model_dump(mode="json"),
        status_code=status_code,
        correlation_id=request.state.correlation_id,
        data_status=data_status,
        data_as_of=data_as_of,
    )


router = APIRouter(
    prefix="/api/v1/local-portfolios",
    tags=["Persistent local manual portfolios"],
    dependencies=[Depends(require_local_application)],
)


@router.get("/instruments", response_model=SuccessEnvelope[LocalPortfolioCatalog], responses=ERRORS)
def catalogue(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(request, lambda: service.catalogue(token), "Supported synthetic instruments")


@router.post("", status_code=201, response_model=SuccessEnvelope[LocalPortfolio], responses=ERRORS)
def create_portfolio(
    request: Request,
    payload: LocalPortfolioRequest,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.create_portfolio(token, payload),
        "Owned manual portfolio created",
        status_code=201,
    )


@router.get("", response_model=SuccessEnvelope[LocalPortfolioList], responses=ERRORS)
def portfolios(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(request, lambda: service.portfolios(token), "Owned manual portfolios")


@router.get("/{portfolio_id}", response_model=SuccessEnvelope[LocalPortfolio], responses=ERRORS)
def portfolio(
    request: Request,
    portfolio_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.portfolio(token, portfolio_id), "Owned manual portfolio"
    )


@router.put("/{portfolio_id}", response_model=SuccessEnvelope[LocalPortfolio], responses=ERRORS)
def update_portfolio(
    request: Request,
    portfolio_id: ResourceId,
    payload: LocalPortfolioRequest,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.update_portfolio(token, portfolio_id, payload),
        "Owned manual portfolio saved",
    )


@router.delete(
    "/{portfolio_id}", response_model=SuccessEnvelope[LocalPortfolioDeletion], responses=ERRORS
)
def delete_portfolio(
    request: Request,
    portfolio_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.delete_portfolio(token, portfolio_id),
        "Owned manual portfolio deleted",
    )


@router.post(
    "/{portfolio_id}/holdings",
    status_code=201,
    response_model=SuccessEnvelope[LocalHolding],
    responses=ERRORS,
)
def create_holding(
    request: Request,
    portfolio_id: ResourceId,
    payload: LocalHoldingCreateRequest,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.create_holding(token, portfolio_id, payload),
        "Owned manual holding created",
        status_code=201,
    )


@router.get(
    "/{portfolio_id}/holdings", response_model=SuccessEnvelope[LocalHoldingList], responses=ERRORS
)
def holdings(
    request: Request,
    portfolio_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.holdings(token, portfolio_id), "Owned manual portfolio holdings"
    )


@router.get(
    "/{portfolio_id}/holdings/{holding_id}",
    response_model=SuccessEnvelope[LocalHolding],
    responses=ERRORS,
)
def holding(
    request: Request,
    portfolio_id: ResourceId,
    holding_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.holding(token, portfolio_id, holding_id),
        "Owned manual portfolio holding",
    )


@router.put(
    "/{portfolio_id}/holdings/{holding_id}",
    response_model=SuccessEnvelope[LocalHolding],
    responses=ERRORS,
)
def update_holding(
    request: Request,
    portfolio_id: ResourceId,
    holding_id: ResourceId,
    payload: LocalHoldingUpdateRequest,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.update_holding(token, portfolio_id, holding_id, payload),
        "Owned manual portfolio holding saved",
    )


@router.delete(
    "/{portfolio_id}/holdings/{holding_id}",
    response_model=SuccessEnvelope[LocalHoldingDeletion],
    responses=ERRORS,
)
def delete_holding(
    request: Request,
    portfolio_id: ResourceId,
    holding_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.delete_holding(token, portfolio_id, holding_id),
        "Owned manual portfolio holding deleted",
    )


@router.get(
    "/{portfolio_id}/metrics",
    response_model=SuccessEnvelope[LocalPortfolioMetrics],
    responses=ERRORS,
)
def metrics(
    request: Request,
    portfolio_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalPortfolioService = Depends(get_local_portfolio_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.metrics(token, portfolio_id),
        "Synthetic manual portfolio calculation",
    )
