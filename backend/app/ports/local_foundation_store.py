"""Only S3 persistence capabilities plus current S1 authorization reads."""

from typing import Protocol

from app.domain.local_foundation import (
    PaperAccountRecord,
    PaperOpeningRecord,
    WatchlistItemRecord,
    WatchlistRecord,
)
from app.ports.local_authorization import AuthorizationTransaction, TransactionStore


class LocalFoundationTransaction(AuthorizationTransaction, Protocol):
    def watchlists(self, user_id: str, limit: int) -> list[WatchlistRecord]: ...

    def watchlist(self, user_id: str, watchlist_id: str) -> WatchlistRecord | None: ...

    def insert_watchlist(self, record: WatchlistRecord) -> None: ...

    def update_watchlist(self, record: WatchlistRecord) -> bool: ...

    def delete_watchlist(self, user_id: str, watchlist_id: str) -> bool: ...

    def items(self, user_id: str, watchlist_id: str, limit: int) -> list[WatchlistItemRecord]: ...

    def item(
        self, user_id: str, watchlist_id: str, instrument_id: str
    ) -> WatchlistItemRecord | None: ...

    def insert_item(self, record: WatchlistItemRecord) -> None: ...

    def delete_item(self, user_id: str, watchlist_id: str, instrument_id: str) -> bool: ...

    def account(self, user_id: str) -> PaperAccountRecord | None: ...

    def opening(
        self, user_id: str, account_id: str, ledger_id: str
    ) -> PaperOpeningRecord | None: ...

    def insert_account_with_opening(
        self, account: PaperAccountRecord, entry: PaperOpeningRecord
    ) -> None: ...

    def ledger(
        self, user_id: str, account_id: str, after_sequence: int, limit: int
    ) -> list[PaperOpeningRecord]: ...


class LocalFoundationStore(TransactionStore[LocalFoundationTransaction], Protocol):
    pass
