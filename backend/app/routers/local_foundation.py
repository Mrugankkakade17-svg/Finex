"""Twelve current-authorized S3 routes; no public/global market or order API."""

import json
import re
import unicodedata
from threading import Lock
from typing import Annotated, Any, Callable

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BeforeValidator

from app.auth.local_boundary import require_local_application
from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.core.responses import APIResponse
from app.domain.local_application import Clock, LocalStoreUnavailable
from app.domain.local_foundation import PUBLIC_INTEGER_MAX
from app.domain.local_portfolio import LocalCatalogUnavailable, LocalQuoteUnavailable
from app.ports.adapters.sqlite_local_foundation import SQLiteLocalFoundationStore
from app.ports.local_foundation_store import LocalFoundationStore
from app.ports.local_portfolio_quotes import LocalPortfolioCatalogPort, LocalPortfolioQuotePort
from app.routers.local_application import local_bearer
from app.schemas.envelope import SuccessEnvelope
from app.schemas.local_foundation import (
    EmptyFoundationRequest,
    FoundationErrorEnvelope,
    MarketQuoteData,
    MarketSearchData,
    PaperAccountData,
    PaperLedgerData,
    PaperOpenRequest,
    WatchlistCollectionData,
    WatchlistData,
    WatchlistDeletedData,
    WatchlistItemData,
    WatchlistItemRemovedData,
    WatchlistRequest,
)
from app.schemas.local_portfolio import InstrumentId, Uuid4
from app.services.local_authorization import utc_clock, validate_token
from app.services.local_foundation_service import FoundationResult, LocalFoundationService

ResourceId = Annotated[Uuid4, Path(min_length=36, max_length=36)]
SyntheticId = Annotated[InstrumentId, Path(min_length=5, max_length=36)]
ERRORS: dict[int | str, dict[str, Any]] = {
    code: {"model": FoundationErrorEnvelope} for code in (401, 403, 404, 409, 422, 503)
}
EMPTY_BODY_DOCS: dict[str, Any] = {
    "requestBody": {
        "required": False,
        "content": {"application/json": {"schema": EmptyFoundationRequest.model_json_schema()}},
    }
}


def validation_failure() -> FinExException:
    return FinExException(
        "The request contains invalid fields or controls.", "VALIDATION_ERROR", 422
    )


def normalized_query(value: object) -> object:
    if isinstance(value, str):
        if any(unicodedata.category(character) == "Cc" for character in value):
            raise ValueError("Search controls are invalid")
        return value.strip()
    return value


SearchQuery = Annotated[str, Query(max_length=80), BeforeValidator(normalized_query)]


def _controls(request: Request, allowed: set[str]) -> None:
    seen: set[str] = set()
    for key, _ in request.query_params.multi_items():
        if key not in allowed or key in seen:
            raise validation_failure()
        seen.add(key)


def _integer_control(request: Request, field: str, default: int, lower: int, upper: int) -> int:
    value = request.query_params.get(field)
    if value is None:
        return default
    if re.fullmatch(r"(?:0|[1-9][0-9]{0,15})", value, flags=re.ASCII) is None:
        raise validation_failure()
    integer = int(value)
    if not lower <= integer <= upper:
        raise validation_failure()
    return integer


def no_query(request: Request) -> None:
    _controls(request, set())


async def empty_body(request: Request) -> EmptyFoundationRequest:
    body = await request.body()
    if body:
        try:
            if len(body) > 262_144:
                raise ValueError
            decoded = json.loads(body.decode("utf-8"))
            if type(decoded) is not dict or decoded:
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            raise validation_failure() from None
    return EmptyFoundationRequest()


def storage_unavailable() -> FinExException:
    return FinExException(
        "Local storage is unavailable. Nothing was confirmed saved; please retry.",
        "LOCAL_STORE_UNAVAILABLE",
        503,
    )


def get_local_foundation_service(
    request: Request,
    token: str = Depends(local_bearer),
    _: None = Depends(require_local_application),
) -> LocalFoundationService:
    validate_token(token)
    state = request.app.state
    lock: Lock = state.local_foundation_service_lock
    with lock:
        if state.local_foundation_service is None:
            settings: Settings = state.settings
            store: LocalFoundationStore | None = state.local_foundation_store
            if store is None:
                if (
                    state.local_application_store is not None
                    or state.local_risk_store is not None
                    or state.local_portfolio_store is not None
                ):
                    raise storage_unavailable()
                store = SQLiteLocalFoundationStore(settings.local_db_path)
            clock: Clock = state.local_clock if state.local_clock is not None else utc_clock
            catalogue: LocalPortfolioCatalogPort | None = state.local_portfolio_catalogue
            quotes: LocalPortfolioQuotePort | None = state.local_portfolio_quotes
            state.local_foundation_service = LocalFoundationService(
                store, clock, catalogue=catalogue, quotes=quotes
            )
        service: LocalFoundationService = state.local_foundation_service
    return service


def respond(
    request: Request, operation: Callable[[], FoundationResult], message: str, *, status: int = 200
) -> JSONResponse:
    try:
        result = operation()
    except LocalStoreUnavailable:
        raise storage_unavailable() from None
    except LocalCatalogUnavailable:
        raise FinExException(
            "The local synthetic instrument catalogue is unavailable. Please retry later.",
            "LOCAL_CATALOG_UNAVAILABLE",
            503,
        ) from None
    except LocalQuoteUnavailable:
        raise FinExException(
            "Synthetic quote timing could not be confirmed. Please retry later.",
            "LOCAL_QUOTE_UNAVAILABLE",
            503,
        ) from None
    return APIResponse.success(
        data=result.data.model_dump(mode="json"),
        message=message,
        status_code=status,
        correlation_id=request.state.correlation_id,
        data_status=result.data_status,
        data_as_of=result.data_as_of,
    )


router = APIRouter()
market = APIRouter(
    prefix="/api/v1/local-market",
    tags=["Synthetic local market"],
    dependencies=[Depends(require_local_application)],
)
watchlists = APIRouter(
    prefix="/api/v1/local-watchlists",
    tags=["Owned local watchlists"],
    dependencies=[Depends(require_local_application), Depends(no_query)],
)
paper = APIRouter(
    prefix="/api/v1/local-paper/account",
    tags=["Explicit simulated account opening"],
    dependencies=[Depends(require_local_application)],
)


@market.get("/instruments", response_model=SuccessEnvelope[MarketSearchData], responses=ERRORS)
def search(
    request: Request,
    query: SearchQuery = "",
    limit: int = Query(20, ge=1, le=20),
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    _controls(request, {"query", "limit"})
    limit = _integer_control(request, "limit", 20, 1, 20)
    return respond(
        request,
        lambda: service.search(token, query, limit),
        "Supported synthetic teaching instruments",
    )


@market.get(
    "/quotes/{instrument_id}",
    response_model=SuccessEnvelope[MarketQuoteData],
    responses=ERRORS,
    dependencies=[Depends(no_query)],
)
def quote(
    request: Request,
    instrument_id: SyntheticId,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.quote(token, instrument_id),
        "Synthetic teaching quote, not a live market price",
    )


@watchlists.get("", response_model=SuccessEnvelope[WatchlistCollectionData], responses=ERRORS)
def lists(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(request, lambda: service.lists(token), "Owned watchlists")


@watchlists.post(
    "", status_code=201, response_model=SuccessEnvelope[WatchlistData], responses=ERRORS
)
def create_list(
    request: Request,
    payload: WatchlistRequest,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.create_list(token, payload), "Owned watchlist created", status=201
    )


@watchlists.get("/{watchlist_id}", response_model=SuccessEnvelope[WatchlistData], responses=ERRORS)
def saved_list(
    request: Request,
    watchlist_id: ResourceId,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(request, lambda: service.list(token, watchlist_id), "Owned watchlist")


@watchlists.put("/{watchlist_id}", response_model=SuccessEnvelope[WatchlistData], responses=ERRORS)
def update_list(
    request: Request,
    watchlist_id: ResourceId,
    payload: WatchlistRequest,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.update_list(token, watchlist_id, payload), "Owned watchlist saved"
    )


@watchlists.delete(
    "/{watchlist_id}",
    response_model=SuccessEnvelope[WatchlistDeletedData],
    responses=ERRORS,
    openapi_extra=EMPTY_BODY_DOCS,
)
def delete_list(
    request: Request,
    watchlist_id: ResourceId,
    token: str = Depends(local_bearer),
    _: EmptyFoundationRequest = Depends(empty_body),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.delete_list(token, watchlist_id), "Owned watchlist deleted"
    )


@watchlists.put(
    "/{watchlist_id}/items/{instrument_id}",
    response_model=SuccessEnvelope[WatchlistItemData],
    responses=ERRORS,
    openapi_extra=EMPTY_BODY_DOCS,
)
def add_item(
    request: Request,
    watchlist_id: ResourceId,
    instrument_id: SyntheticId,
    token: str = Depends(local_bearer),
    _: EmptyFoundationRequest = Depends(empty_body),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.add_item(token, watchlist_id, instrument_id),
        "Supported instrument saved in owned watchlist",
    )


@watchlists.delete(
    "/{watchlist_id}/items/{instrument_id}",
    response_model=SuccessEnvelope[WatchlistItemRemovedData],
    responses=ERRORS,
    openapi_extra=EMPTY_BODY_DOCS,
)
def remove_item(
    request: Request,
    watchlist_id: ResourceId,
    instrument_id: SyntheticId,
    token: str = Depends(local_bearer),
    _: EmptyFoundationRequest = Depends(empty_body),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request,
        lambda: service.remove_item(token, watchlist_id, instrument_id),
        "Supported instrument removed from owned watchlist",
    )


@paper.get(
    "",
    response_model=SuccessEnvelope[PaperAccountData],
    responses=ERRORS,
    dependencies=[Depends(no_query)],
)
def account(
    request: Request,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(request, lambda: service.account(token), "Controlled simulated account state")


@paper.post(
    "/open",
    response_model=SuccessEnvelope[PaperAccountData],
    responses=ERRORS,
    dependencies=[Depends(no_query)],
)
def open_account(
    request: Request,
    payload: PaperOpenRequest,
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    return respond(
        request, lambda: service.open_account(token, payload), "Controlled simulated account opened"
    )


@paper.get("/ledger", response_model=SuccessEnvelope[PaperLedgerData], responses=ERRORS)
def ledger(
    request: Request,
    limit: int = Query(100, ge=1, le=100),
    after_sequence: int = Query(0, ge=0, le=PUBLIC_INTEGER_MAX),
    token: str = Depends(local_bearer),
    service: LocalFoundationService = Depends(get_local_foundation_service),
) -> JSONResponse:
    _controls(request, {"limit", "after_sequence"})
    limit = _integer_control(request, "limit", 100, 1, 100)
    after_sequence = _integer_control(request, "after_sequence", 0, 0, PUBLIC_INTEGER_MAX)
    return respond(
        request,
        lambda: service.ledger(token, limit, after_sequence),
        "Owned immutable simulated opening ledger",
    )


router.include_router(market)
router.include_router(watchlists)
router.include_router(paper)
