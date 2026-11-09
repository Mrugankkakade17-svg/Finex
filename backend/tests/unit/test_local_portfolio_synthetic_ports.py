"""Synthetic-only immutable source and strict runtime-shape RED assertions."""

from dataclasses import FrozenInstanceError, replace

import pytest

from app.domain.local_portfolio import (
    LocalCatalogUnavailable,
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteRecord,
    LocalPortfolioQuoteSnapshot,
    LocalQuoteUnavailable,
)
from app.ports.adapters.synthetic_local_portfolio import (
    SyntheticLocalPortfolioCatalog,
    SyntheticLocalPortfolioQuotes,
    validate_catalogue_snapshot,
    validate_quote_snapshot,
)


def test_default_catalogue_is_sorted_finite_readonly_and_no_quote_is_live() -> None:
    snapshot = SyntheticLocalPortfolioCatalog().snapshot()
    assert [row.instrument_id for row in snapshot.items] == [
        "SYN:AAPL",
        "SYN:BND",
        "SYN:MSFT",
        "SYN:UNAVAILABLE",
    ]
    assert snapshot.catalog_version == "synthetic_catalog.v1" and snapshot.currency == "USD"
    with pytest.raises(FrozenInstanceError):
        snapshot.currency = "EUR"  # type: ignore[misc]
    requested = ("SYN:MSFT", "SYN:UNAVAILABLE")
    quote = SyntheticLocalPortfolioQuotes().snapshot(requested)
    assert [row.instrument_id for row in quote.quotes] == list(requested)
    assert quote.source_type == "SYNTHETIC"
    assert quote.fixture_as_of == "2026-01-01T00:00:00Z"
    assert quote.quotes[0].unit_price == "400.0000"
    assert quote.quotes[1].unit_price is None
    assert quote.quotes[1].reason == "SYNTHETIC_QUOTE_UNAVAILABLE"
    assert all(row.data_status != "LIVE" for row in quote.quotes)


@pytest.mark.parametrize(
    "mode",
    [
        "version",
        "currency",
        "empty",
        "too_many",
        "duplicate",
        "instrument",
        "name",
        "class",
        "sector",
        "untrimmed",
    ],
)
def test_runtime_catalogue_corruption_is_not_silently_accepted(mode: str) -> None:
    item = LocalPortfolioInstrument("SYN:AAPL", "Synthetic", "EQUITY", "GENERAL", "USD")
    snapshot = LocalPortfolioCatalogSnapshot("synthetic_catalog.v1", "USD", (item,))
    if mode == "version":
        snapshot = replace(snapshot, catalog_version="v0")
    elif mode == "currency":
        snapshot = replace(snapshot, currency="EUR")
    elif mode == "empty":
        snapshot = replace(snapshot, items=())
    elif mode == "too_many":
        snapshot = replace(
            snapshot, items=tuple(replace(item, instrument_id=f"SYN:T{i}") for i in range(129))
        )
    elif mode == "duplicate":
        snapshot = replace(snapshot, items=(item, item))
    else:
        fields = {
            "instrument": "instrument_id",
            "name": "display_name",
            "class": "asset_class",
            "sector": "sector",
            "untrimmed": "display_name",
        }
        values = {
            "instrument": "aapl",
            "name": "",
            "class": "Equity",
            "sector": "x" * 33,
            "untrimmed": " Synthetic ",
        }
        snapshot = replace(snapshot, items=(replace(item, **{fields[mode]: values[mode]}),))
    with pytest.raises(LocalCatalogUnavailable):
        validate_catalogue_snapshot(snapshot)


@pytest.mark.parametrize(
    "mode",
    [
        "version",
        "source",
        "source_type",
        "as_of",
        "missing",
        "duplicate",
        "unexpected",
        "zero",
        "too_large",
        "precision",
        "live",
        "reason",
        "quote_time",
        "missing_reason",
        "missing_time",
    ],
)
def test_runtime_quote_corruption_is_not_an_ordinary_missing_quote(mode: str) -> None:
    item = LocalPortfolioQuoteRecord("SYN:AAPL", "200.0000", "CACHED", "2026-01-01T00:00:00Z", None)
    snapshot = LocalPortfolioQuoteSnapshot(
        "synthetic_quotes.v1",
        "finex.synthetic.portfolio",
        "SYNTHETIC",
        "2026-01-01T00:00:00Z",
        (item,),
    )
    top = {
        "version": ("quote_snapshot_version", "v0"),
        "source": ("source", "vendor"),
        "source_type": ("source_type", "LIVE"),
        "as_of": ("fixture_as_of", "today"),
    }
    if mode in top:
        key, value = top[mode]
        snapshot = replace(snapshot, **{key: value})
    elif mode == "missing":
        snapshot = replace(snapshot, quotes=())
    elif mode == "duplicate":
        snapshot = replace(snapshot, quotes=(item, item))
    elif mode == "unexpected":
        snapshot = replace(snapshot, quotes=(replace(item, instrument_id="SYN:MSFT"),))
    elif mode.startswith("missing_"):
        missing = replace(
            item,
            unit_price=None,
            data_status="UNAVAILABLE",
            quote_as_of=None,
            reason="SYNTHETIC_QUOTE_UNAVAILABLE",
        )
        missing = (
            replace(missing, reason=None)
            if mode == "missing_reason"
            else replace(missing, quote_as_of="2026-01-01T00:00:00Z")
        )
        snapshot = replace(snapshot, quotes=(missing,))
    else:
        fields = {
            "zero": "unit_price",
            "too_large": "unit_price",
            "precision": "unit_price",
            "live": "data_status",
            "reason": "reason",
            "quote_time": "quote_as_of",
        }
        values = {
            "zero": "0.0000",
            "too_large": "1000000.0001",
            "precision": "200.00000",
            "live": "LIVE",
            "reason": "SYNTHETIC_QUOTE_UNAVAILABLE",
            "quote_time": "today",
        }
        snapshot = replace(snapshot, quotes=(replace(item, **{fields[mode]: values[mode]}),))
    with pytest.raises(LocalQuoteUnavailable):
        validate_quote_snapshot(snapshot, ("SYN:AAPL",))


@pytest.mark.parametrize("wrong", [None, True, {}, "not-a-snapshot", ()])
def test_injected_runtime_wrong_snapshot_types_have_opaque_failures(wrong: object) -> None:
    with pytest.raises(LocalCatalogUnavailable):
        validate_catalogue_snapshot(wrong)
    with pytest.raises(LocalQuoteUnavailable):
        validate_quote_snapshot(wrong, ("SYN:AAPL",))


def test_mutable_collections_are_not_immutable_catalogue_or_quote_snapshots() -> None:
    catalogue = SyntheticLocalPortfolioCatalog().snapshot()
    quote = SyntheticLocalPortfolioQuotes().snapshot(("SYN:AAPL",))
    with pytest.raises(LocalCatalogUnavailable):
        validate_catalogue_snapshot(replace(catalogue, items=list(catalogue.items)))
    with pytest.raises(LocalQuoteUnavailable):
        validate_quote_snapshot(replace(quote, quotes=list(quote.quotes)), ("SYN:AAPL",))


@pytest.mark.parametrize("wrong", [False, 1, 1.0, "200", "200.00000", "NaN", "Infinity"])
def test_quote_prices_never_coerce_equal_numeric_or_nonfinite_types(wrong: object) -> None:
    quote = SyntheticLocalPortfolioQuotes().snapshot(("SYN:AAPL",))
    with pytest.raises(LocalQuoteUnavailable):
        validate_quote_snapshot(
            replace(quote, quotes=(replace(quote.quotes[0], unit_price=wrong),)), ("SYN:AAPL",)
        )
