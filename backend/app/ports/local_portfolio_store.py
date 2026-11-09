"""Owned manual portfolio capabilities within shared authorization transactions."""

from typing import Protocol

from app.domain.local_portfolio import LocalHoldingRecord, LocalPortfolioRecord
from app.ports.local_authorization import AuthorizationTransaction, TransactionStore


class LocalPortfolioTransaction(AuthorizationTransaction, Protocol):
    def get_portfolio(self, user_id: str, portfolio_id: str) -> LocalPortfolioRecord | None: ...

    def list_portfolios(self, user_id: str, *, limit: int) -> list[LocalPortfolioRecord]: ...

    def count_portfolios(self, user_id: str) -> int: ...

    def insert_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord: ...

    def update_portfolio(self, record: LocalPortfolioRecord) -> LocalPortfolioRecord: ...

    def delete_portfolio(self, user_id: str, portfolio_id: str) -> bool: ...

    def get_holding(
        self, user_id: str, portfolio_id: str, holding_id: str
    ) -> LocalHoldingRecord | None: ...

    def list_holdings(
        self, user_id: str, portfolio_id: str, *, limit: int
    ) -> list[LocalHoldingRecord]: ...

    def count_holdings(self, user_id: str, portfolio_id: str) -> int: ...

    def get_holding_by_instrument(
        self, user_id: str, portfolio_id: str, instrument_id: str
    ) -> LocalHoldingRecord | None: ...

    def insert_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord: ...

    def update_holding(self, record: LocalHoldingRecord) -> LocalHoldingRecord: ...

    def delete_holding(self, user_id: str, portfolio_id: str, holding_id: str) -> bool: ...


class LocalPortfolioStore(TransactionStore[LocalPortfolioTransaction], Protocol):
    """A dedicated capability; never infer it from an unrelated injected store."""
