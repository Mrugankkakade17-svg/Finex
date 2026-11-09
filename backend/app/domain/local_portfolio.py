"""Immutable manual-only portfolio records and exact bounded decimal units.

No HTTP, SQL, provider or binary-float dependency belongs in this domain.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

PORTFOLIO_VERSION = "portfolio.v1"
HOLDING_VERSION = "holding.v1"
METRICS_VERSION = "portfolio_metrics.v1"
FORMULA_VERSION = "manual_portfolio_math.v1"
CATALOG_VERSION = "synthetic_catalog.v1"
QUOTE_SNAPSHOT_VERSION = "synthetic_quotes.v1"
QUOTE_SOURCE = "finex.synthetic.portfolio"
QUOTE_SOURCE_TYPE = "SYNTHETIC"
FIXTURE_AS_OF = "2026-01-01T00:00:00Z"
PORTFOLIO_LIMIT = 20
HOLDING_LIMIT = 100
CATALOG_LIMIT = 128
QUANTITY_SCALE = 1_000_000
COST_SCALE = 10_000
MAX_QUANTITY_UNITS = 1_000_000_000_000
MAX_COST_UNITS = 10_000_000_000
_QUANTITY_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,6})\.[0-9]{6}")
_COST_PATTERN = re.compile(r"(?:0|[1-9][0-9]{0,6})\.[0-9]{4}")
_UUID4_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
_INSTRUMENT_PATTERN = re.compile(r"SYN:[A-Z][A-Z0-9_]{0,31}")


@dataclass(frozen=True)
class LocalPortfolioRecord:
    user_id: str
    portfolio_id: str
    name: str
    description: str | None
    currency: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LocalHoldingRecord:
    user_id: str
    portfolio_id: str
    holding_id: str
    instrument_id: str
    quantity: str
    average_cost: str
    currency: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class LocalPortfolioInstrument:
    instrument_id: str
    display_name: str
    asset_class: str
    sector: str
    currency: str


@dataclass(frozen=True)
class LocalPortfolioCatalogSnapshot:
    catalog_version: str
    currency: str
    items: tuple[LocalPortfolioInstrument, ...]


@dataclass(frozen=True)
class LocalPortfolioQuoteRecord:
    instrument_id: str
    unit_price: str | None
    data_status: str
    quote_as_of: str | None
    reason: str | None


@dataclass(frozen=True)
class LocalPortfolioQuoteSnapshot:
    quote_snapshot_version: str
    source: str
    source_type: str
    fixture_as_of: str
    quotes: tuple[LocalPortfolioQuoteRecord, ...]


class LocalCatalogUnavailable(Exception):
    """Opaque catalogue fault, never a user-facing provider exception."""


class LocalQuoteUnavailable(Exception):
    """Opaque snapshot configuration fault, not an ordinary missing price."""


def _units(value: object, pattern: re.Pattern[str], scale: int, minimum: int, maximum: int) -> int:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ValueError("Invalid canonical decimal text")
    whole, fraction = value.split(".", 1)
    result = int(whole) * scale + int(fraction)
    if not minimum <= result <= maximum:
        raise ValueError("Decimal units outside the allowed bounds")
    return result


def quantity_units(value: object) -> int:
    return _units(value, _QUANTITY_PATTERN, QUANTITY_SCALE, 1, MAX_QUANTITY_UNITS)


def cost_units(value: object) -> int:
    return _units(value, _COST_PATTERN, COST_SCALE, 0, MAX_COST_UNITS)


def price_units(value: object) -> int:
    return _units(value, _COST_PATTERN, COST_SCALE, 1, MAX_COST_UNITS)


def _text(value: object, scale: int, places: int, minimum: int, maximum: int) -> str:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid stored decimal units")
    whole, fraction = divmod(value, scale)
    return f"{whole}.{fraction:0{places}d}"


def quantity_text(value: object) -> str:
    return _text(value, QUANTITY_SCALE, 6, 1, MAX_QUANTITY_UNITS)


def cost_text(value: object) -> str:
    return _text(value, COST_SCALE, 4, 0, MAX_COST_UNITS)


def canonical_uuid4(value: object) -> str:
    if not isinstance(value, str) or _UUID4_PATTERN.fullmatch(value) is None:
        raise ValueError("Invalid canonical resource identifier")
    return value


def canonical_instrument_id(value: object) -> str:
    if not isinstance(value, str) or _INSTRUMENT_PATTERN.fullmatch(value) is None:
        raise ValueError("Invalid canonical instrument identifier")
    return value


def _owner(value: object, expected: str | None) -> None:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("Invalid internal owner")
    if expected is not None and value != expected:
        raise ValueError("Owned record mismatch")


def _record_times(created_at: object, updated_at: object) -> None:
    for value in (created_at, updated_at):
        if (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            raise ValueError("Invalid UTC record timestamp")
    if not isinstance(created_at, datetime) or not isinstance(updated_at, datetime):
        raise ValueError("Invalid record timestamp")
    if updated_at < created_at:
        raise ValueError("Record update precedes creation")


def validate_portfolio_record(
    record: LocalPortfolioRecord, *, user_id: str | None = None
) -> LocalPortfolioRecord:
    if not isinstance(record, LocalPortfolioRecord):
        raise ValueError("Invalid portfolio record")
    _owner(record.user_id, user_id)
    canonical_uuid4(record.portfolio_id)
    if (
        not isinstance(record.name, str)
        or record.name != record.name.strip()
        or not 1 <= len(record.name) <= 100
    ):
        raise ValueError("Invalid portfolio name")
    if record.description is not None and (
        not isinstance(record.description, str)
        or record.description != record.description.strip()
        or len(record.description) > 500
    ):
        raise ValueError("Invalid portfolio description")
    if record.currency != "USD":
        raise ValueError("Invalid portfolio currency")
    _record_times(record.created_at, record.updated_at)
    return record


def validate_holding_record(
    record: LocalHoldingRecord, *, user_id: str | None = None, portfolio_id: str | None = None
) -> LocalHoldingRecord:
    if not isinstance(record, LocalHoldingRecord):
        raise ValueError("Invalid holding record")
    _owner(record.user_id, user_id)
    canonical_uuid4(record.portfolio_id)
    if portfolio_id is not None and record.portfolio_id != portfolio_id:
        raise ValueError("Holding parent mismatch")
    canonical_uuid4(record.holding_id)
    canonical_instrument_id(record.instrument_id)
    quantity_units(record.quantity)
    cost_units(record.average_cost)
    if record.currency != "USD":
        raise ValueError("Invalid holding currency")
    _record_times(record.created_at, record.updated_at)
    return record
