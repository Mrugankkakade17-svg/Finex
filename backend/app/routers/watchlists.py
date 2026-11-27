"""Production API routes for user-owned watchlists and items."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status

from app.auth.principal import Principal, get_current_principal
from app.core.responses import APIResponse
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistUpdate,
)
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/api/v1/watchlists", tags=["Watchlists"])
watchlist_service = WatchlistService()


def _get_service() -> WatchlistService:
    return watchlist_service


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_watchlist(
    request: Request,
    payload: WatchlistCreate,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    result = service.create_watchlist(principal.user_id, payload)
    return APIResponse.success(
        message="Watchlist created successfully",
        data=result.model_dump(),
        correlation_id=correlation,
        status_code=status.HTTP_201_CREATED,
    )


@router.get("")
async def list_watchlists(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    items = service.list_watchlists(principal.user_id)
    return APIResponse.success(
        message="Watchlists retrieved successfully",
        data={"items": [it.model_dump() for it in items], "count": len(items)},
        correlation_id=correlation,
    )


@router.get("/{watchlist_id}")
async def get_watchlist(
    request: Request,
    watchlist_id: str,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    result = service.get_watchlist(principal.user_id, watchlist_id)
    return APIResponse.success(
        message="Watchlist retrieved successfully",
        data=result.model_dump(),
        correlation_id=correlation,
    )


@router.put("/{watchlist_id}")
async def update_watchlist(
    request: Request,
    watchlist_id: str,
    payload: WatchlistUpdate,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    result = service.update_watchlist(principal.user_id, watchlist_id, payload)
    return APIResponse.success(
        message="Watchlist updated successfully",
        data=result.model_dump(),
        correlation_id=correlation,
    )


@router.delete("/{watchlist_id}")
async def delete_watchlist(
    request: Request,
    watchlist_id: str,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    service.delete_watchlist(principal.user_id, watchlist_id)
    return APIResponse.success(
        message="Watchlist deleted successfully",
        data={"watchlist_id": watchlist_id, "deleted": True},
        correlation_id=correlation,
    )


@router.post("/{watchlist_id}/items", status_code=status.HTTP_201_CREATED)
async def add_watchlist_item(
    request: Request,
    watchlist_id: str,
    payload: WatchlistItemCreate,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    item = service.add_item(principal.user_id, watchlist_id, payload)
    return APIResponse.success(
        message="Item added to watchlist successfully",
        data=item.model_dump(),
        correlation_id=correlation,
        status_code=status.HTTP_201_CREATED,
    )


@router.put("/{watchlist_id}/items/{instrument_id}")
async def put_watchlist_item(
    request: Request,
    watchlist_id: str,
    instrument_id: str,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    """Idempotently add or update item by instrument_id path parameter."""
    correlation = getattr(request.state, "correlation_id", "unknown")
    item = service.add_item(
        principal.user_id, watchlist_id, WatchlistItemCreate(instrument_id=instrument_id)
    )
    return APIResponse.success(
        message="Item saved in watchlist successfully",
        data=item.model_dump(),
        correlation_id=correlation,
    )


@router.get("/{watchlist_id}/items")
async def list_watchlist_items(
    request: Request,
    watchlist_id: str,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    items = service.list_items(principal.user_id, watchlist_id)
    return APIResponse.success(
        message="Watchlist items retrieved successfully",
        data={"items": [it.model_dump() for it in items], "count": len(items)},
        correlation_id=correlation,
    )


@router.delete("/{watchlist_id}/items/{instrument_id}")
async def remove_watchlist_item(
    request: Request,
    watchlist_id: str,
    instrument_id: str,
    principal: Principal = Depends(get_current_principal),
    service: WatchlistService = Depends(_get_service),
):
    correlation = getattr(request.state, "correlation_id", "unknown")
    service.remove_item(principal.user_id, watchlist_id, instrument_id)
    return APIResponse.success(
        message="Item removed from watchlist successfully",
        data={"watchlist_id": watchlist_id, "instrument_id": instrument_id, "removed": True},
        correlation_id=correlation,
    )
