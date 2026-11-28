"""Pydantic schemas for the production watchlists API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WatchlistCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100, description="Watchlist name")


class WatchlistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100, description="Updated watchlist name")


class WatchlistItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument_id: str = Field(
        ..., min_length=1, max_length=32, description="Security symbol or instrument identifier"
    )


class WatchlistItemResponse(BaseModel):
    instrument_id: str
    added_at: str


class WatchlistSummaryResponse(BaseModel):
    watchlist_id: str
    name: str
    created_at: str
    updated_at: str
    item_count: int = 0


class WatchlistResponse(BaseModel):
    watchlist_id: str
    name: str
    created_at: str
    updated_at: str
    item_count: int = 0
    items: list[WatchlistItemResponse] = Field(default_factory=list)
