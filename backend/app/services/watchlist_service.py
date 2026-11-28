"""Service layer for production watchlist domain operations."""

from __future__ import annotations

from fastapi import HTTPException, status

from app.repositories.watchlist_repository import WatchlistRepository
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistResponse,
    WatchlistSummaryResponse,
    WatchlistUpdate,
)


class WatchlistService:
    def __init__(self, repository: WatchlistRepository | None = None) -> None:
        self.repository = repository or WatchlistRepository()

    def create_watchlist(self, user_id: str, data: WatchlistCreate) -> WatchlistResponse:
        name = data.name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Watchlist name cannot be empty",
            )
        # Check current count constraint (max 10 watchlists per user per FinEx spec)
        current_lists = self.repository.list_watchlists(user_id)
        if len(current_lists) >= 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum of 10 watchlists reached",
            )

        record = self.repository.create_watchlist(user_id, name)
        return WatchlistResponse(**record)

    def list_watchlists(self, user_id: str) -> list[WatchlistSummaryResponse]:
        records = self.repository.list_watchlists(user_id)
        return [WatchlistSummaryResponse(**r) for r in records]

    def get_watchlist(self, user_id: str, watchlist_id: str) -> WatchlistResponse:
        record = self.repository.get_watchlist(user_id, watchlist_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )
        return WatchlistResponse(**record)

    def update_watchlist(
        self, user_id: str, watchlist_id: str, data: WatchlistUpdate
    ) -> WatchlistResponse:
        name = data.name.strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Watchlist name cannot be empty",
            )
        record = self.repository.update_watchlist(user_id, watchlist_id, name)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )
        return WatchlistResponse(**record)

    def delete_watchlist(self, user_id: str, watchlist_id: str) -> None:
        deleted = self.repository.delete_watchlist(user_id, watchlist_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )

    def add_item(
        self, user_id: str, watchlist_id: str, data: WatchlistItemCreate
    ) -> WatchlistItemResponse:
        instrument_id = data.instrument_id.strip().upper()
        if not instrument_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Instrument ID cannot be empty",
            )
        watchlist = self.repository.get_watchlist(user_id, watchlist_id)
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )
        if watchlist["item_count"] >= 100 and not any(
            it["instrument_id"] == instrument_id for it in watchlist["items"]
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum of 100 items per watchlist reached",
            )

        item = self.repository.add_item(user_id, watchlist_id, instrument_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )
        return WatchlistItemResponse(**item)

    def list_items(self, user_id: str, watchlist_id: str) -> list[WatchlistItemResponse]:
        items = self.repository.list_items(user_id, watchlist_id)
        if items is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )
        return [WatchlistItemResponse(**it) for it in items]

    def remove_item(self, user_id: str, watchlist_id: str, instrument_id: str) -> None:
        clean_instrument = instrument_id.strip().upper()
        watchlist = self.repository.get_watchlist(user_id, watchlist_id)
        if not watchlist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Watchlist not found",
            )
        # Idempotent removal per FinEx spec
        self.repository.remove_item(user_id, watchlist_id, clean_instrument)
