"""Finite immutable synthetic examples; no provider, clock refresh or network boundary."""

import re

from app.domain.local_portfolio import (
    CATALOG_LIMIT,
    CATALOG_VERSION,
    FIXTURE_AS_OF,
    QUOTE_SNAPSHOT_VERSION,
    QUOTE_SOURCE,
    QUOTE_SOURCE_TYPE,
    LocalCatalogUnavailable,
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteRecord,
    LocalPortfolioQuoteSnapshot,
    LocalQuoteUnavailable,
    canonical_instrument_id,
    price_units,
)

_CATALOGUE = LocalPortfolioCatalogSnapshot(
    CATALOG_VERSION,
    "USD",
    (
        LocalPortfolioInstrument(
            "SYN:AAPL", "Synthetic Apple example", "EQUITY", "TECHNOLOGY", "USD"
        ),
        LocalPortfolioInstrument(
            "SYN:BND", "Synthetic bond-fund example", "BOND", "FIXED_INCOME", "USD"
        ),
        LocalPortfolioInstrument(
            "SYN:MSFT", "Synthetic Microsoft example", "EQUITY", "TECHNOLOGY", "USD"
        ),
        LocalPortfolioInstrument(
            "SYN:UNAVAILABLE", "Synthetic unavailable-price example", "EQUITY", "GENERAL", "USD"
        ),
    ),
)
_PRICES: dict[str, str | None] = {
    "SYN:AAPL": "200.0000",
    "SYN:BND": "80.0000",
    "SYN:MSFT": "400.0000",
    "SYN:UNAVAILABLE": None,
}


def validate_catalogue_snapshot(snapshot: object) -> LocalPortfolioCatalogSnapshot:
    """Reject malformed injection rather than silently dropping unsupported entries."""
    try:
        if not isinstance(snapshot, LocalPortfolioCatalogSnapshot) or (
            type(snapshot.catalog_version) is not str
            or snapshot.catalog_version != CATALOG_VERSION
            or type(snapshot.currency) is not str
            or snapshot.currency != "USD"
            or type(snapshot.items) is not tuple
            or not 1 <= len(snapshot.items) <= CATALOG_LIMIT
        ):
            raise ValueError
        seen: set[str] = set()
        for item in snapshot.items:
            if not isinstance(item, LocalPortfolioInstrument):
                raise ValueError
            canonical_instrument_id(item.instrument_id)
            if item.instrument_id in seen or (
                type(item.display_name) is not str
                or not 1 <= len(item.display_name) <= 100
                or item.display_name != item.display_name.strip()
                or type(item.asset_class) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", item.asset_class) is None
                or type(item.sector) is not str
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", item.sector) is None
                or type(item.currency) is not str
                or item.currency != "USD"
            ):
                raise ValueError
            seen.add(item.instrument_id)
        return snapshot
    except Exception:
        raise LocalCatalogUnavailable() from None


def validate_quote_snapshot(
    snapshot: object, instrument_ids: tuple[str, ...]
) -> LocalPortfolioQuoteSnapshot:
    """One immutable batch describes exactly, and only, the requested instruments."""
    try:
        if type(instrument_ids) is not tuple or len(instrument_ids) != len(set(instrument_ids)):
            raise ValueError
        for instrument in instrument_ids:
            canonical_instrument_id(instrument)
        if not isinstance(snapshot, LocalPortfolioQuoteSnapshot) or (
            type(snapshot.quote_snapshot_version) is not str
            or snapshot.quote_snapshot_version != QUOTE_SNAPSHOT_VERSION
            or type(snapshot.source) is not str
            or snapshot.source != QUOTE_SOURCE
            or type(snapshot.source_type) is not str
            or snapshot.source_type != QUOTE_SOURCE_TYPE
            or type(snapshot.fixture_as_of) is not str
            or snapshot.fixture_as_of != FIXTURE_AS_OF
            or type(snapshot.quotes) is not tuple
            or len(snapshot.quotes) != len(instrument_ids)
        ):
            raise ValueError
        seen: set[str] = set()
        for quote in snapshot.quotes:
            if not isinstance(quote, LocalPortfolioQuoteRecord):
                raise ValueError
            canonical_instrument_id(quote.instrument_id)
            if quote.instrument_id in seen or quote.instrument_id not in instrument_ids:
                raise ValueError
            seen.add(quote.instrument_id)
            if type(quote.data_status) is not str:
                raise ValueError
            if quote.data_status == "CACHED":
                price_units(quote.unit_price)
                if type(quote.quote_as_of) is not str or (
                    quote.quote_as_of != FIXTURE_AS_OF or quote.reason is not None
                ):
                    raise ValueError
            elif quote.data_status == "UNAVAILABLE":
                if (
                    quote.unit_price is not None
                    or quote.quote_as_of is not None
                    or (
                        type(quote.reason) is not str
                        or quote.reason != "SYNTHETIC_QUOTE_UNAVAILABLE"
                    )
                ):
                    raise ValueError
            else:
                raise ValueError
        if seen != set(instrument_ids):
            raise ValueError
        return snapshot
    except Exception:
        raise LocalQuoteUnavailable() from None


class SyntheticLocalPortfolioCatalog:
    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        return _CATALOGUE


class SyntheticLocalPortfolioQuotes:
    def snapshot(self, instrument_ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        try:
            rows = tuple(
                LocalPortfolioQuoteRecord(
                    instrument,
                    _PRICES[instrument],
                    "CACHED" if _PRICES[instrument] is not None else "UNAVAILABLE",
                    FIXTURE_AS_OF if _PRICES[instrument] is not None else None,
                    None if _PRICES[instrument] is not None else "SYNTHETIC_QUOTE_UNAVAILABLE",
                )
                for instrument in instrument_ids
            )
            return validate_quote_snapshot(
                LocalPortfolioQuoteSnapshot(
                    QUOTE_SNAPSHOT_VERSION, QUOTE_SOURCE, QUOTE_SOURCE_TYPE, FIXTURE_AS_OF, rows
                ),
                instrument_ids,
            )
        except Exception:
            raise LocalQuoteUnavailable() from None
