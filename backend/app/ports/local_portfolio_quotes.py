"""Immutable synchronous catalogue and synthetic quote snapshot ports."""

from typing import Protocol

from app.domain.local_portfolio import (
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioQuoteSnapshot,
)


class LocalPortfolioCatalogPort(Protocol):
    def snapshot(self) -> LocalPortfolioCatalogSnapshot: ...


class LocalPortfolioQuotePort(Protocol):
    def snapshot(self, instrument_ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot: ...
