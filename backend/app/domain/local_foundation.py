"""Owned S3 records; no provider, HTTP, binary-float money or execution authority."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from app.domain.local_portfolio import canonical_instrument_id, canonical_uuid4

FOUNDATION_VERSION: Final = "market_foundation.v1"
WATCHLIST_LIMIT: Final = 10
WATCHLIST_ITEM_LIMIT: Final = 100
OPENING_CENTS: Final = 1_000_000
MAX_CASH_CENTS: Final = 10_000_000_000_000_000
PUBLIC_INTEGER_MAX: Final = 9_007_199_254_740_991


@dataclass(frozen=True)
class WatchlistRecord:
    user_id: str
    watchlist_id: str
    name: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class WatchlistItemRecord:
    user_id: str
    watchlist_id: str
    instrument_id: str
    added_at: datetime


@dataclass(frozen=True)
class PaperAccountRecord:
    user_id: str
    account_id: str
    opening_ledger_id: str
    currency: str
    opening_cash_cents: int
    cash_balance_cents: int
    created_at: datetime


@dataclass(frozen=True)
class PaperOpeningRecord:
    user_id: str
    account_id: str
    ledger_id: str
    sequence: int
    cash_delta_cents: int
    cash_after_cents: int
    created_at: datetime


def owner(value: object, expected: str | None = None) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("Invalid owned record")
    if expected is not None and value != expected:
        raise ValueError("Owned record mismatch")


def utc_record(value: object) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("Invalid owned UTC time")


def validate_watchlist(record: WatchlistRecord, expected: str | None = None) -> WatchlistRecord:
    if not isinstance(record, WatchlistRecord):
        raise ValueError("Invalid watchlist record")
    owner(record.user_id, expected)
    canonical_uuid4(record.watchlist_id)
    if (
        type(record.name) is not str
        or record.name != record.name.strip()
        or not 1 <= len(record.name) <= 100
    ):
        raise ValueError("Invalid watchlist name")
    utc_record(record.created_at)
    utc_record(record.updated_at)
    if record.updated_at < record.created_at:
        raise ValueError("Invalid watchlist ordering")
    return record


def validate_item(record: WatchlistItemRecord, expected: str | None = None) -> WatchlistItemRecord:
    if not isinstance(record, WatchlistItemRecord):
        raise ValueError("Invalid watchlist item")
    owner(record.user_id, expected)
    canonical_uuid4(record.watchlist_id)
    canonical_instrument_id(record.instrument_id)
    utc_record(record.added_at)
    return record


def validate_account(record: PaperAccountRecord, expected: str | None = None) -> PaperAccountRecord:
    if not isinstance(record, PaperAccountRecord):
        raise ValueError("Invalid simulated account")
    owner(record.user_id, expected)
    canonical_uuid4(record.account_id)
    canonical_uuid4(record.opening_ledger_id)
    if record.currency != "USD" or type(record.currency) is not str:
        raise ValueError("Invalid simulated currency")
    if type(record.opening_cash_cents) is not int or record.opening_cash_cents != OPENING_CENTS:
        raise ValueError("Invalid simulated opening policy")
    if (
        type(record.cash_balance_cents) is not int
        or not 0 <= record.cash_balance_cents <= MAX_CASH_CENTS
    ):
        raise ValueError("Invalid simulated cash units")
    utc_record(record.created_at)
    return record


def validate_opening(
    record: PaperOpeningRecord, expected: str | None = None, *, new: bool = False
) -> PaperOpeningRecord:
    if not isinstance(record, PaperOpeningRecord):
        raise ValueError("Invalid simulated opening")
    owner(record.user_id, expected)
    canonical_uuid4(record.account_id)
    canonical_uuid4(record.ledger_id)
    if type(record.sequence) is not int or not (
        record.sequence == 0 if new else 1 <= record.sequence <= PUBLIC_INTEGER_MAX
    ):
        raise ValueError("Invalid simulated sequence")
    if type(record.cash_delta_cents) is not int or record.cash_delta_cents != OPENING_CENTS:
        raise ValueError("Invalid simulated opening delta")
    if type(record.cash_after_cents) is not int or record.cash_after_cents != OPENING_CENTS:
        raise ValueError("Invalid simulated opening balance")
    utc_record(record.created_at)
    return record


def money_text(cents: int) -> str:
    if type(cents) is not int or not 0 <= cents <= MAX_CASH_CENTS:
        raise ValueError("Invalid simulated money units")
    whole, fractional = divmod(cents, 100)
    return f"{whole}.{fractional:02d}"
