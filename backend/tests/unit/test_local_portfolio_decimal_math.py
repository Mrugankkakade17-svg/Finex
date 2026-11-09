"""Public pure-math assertions written before the candidate implementation."""

from datetime import datetime, timezone
from decimal import ROUND_DOWN, DefaultContext, Inexact, Rounded, getcontext, localcontext
from itertools import count
from uuid import uuid4

import pytest

from app.domain.local_portfolio import (
    LocalHoldingRecord,
    LocalPortfolioRecord,
)
from app.ports.adapters.synthetic_local_portfolio import (
    SyntheticLocalPortfolioCatalog,
    SyntheticLocalPortfolioQuotes,
)
from app.services.local_portfolio_math import calculate_portfolio_metrics

NOW = datetime(2026, 10, 11, 18, tzinfo=timezone.utc)
PORTFOLIO = LocalPortfolioRecord("synthetic-owner", str(uuid4()), "Training", None, "USD", NOW, NOW)
HOLDING_SEQUENCE = count(1)


def holding(instrument: str, quantity: str, cost: str) -> LocalHoldingRecord:
    return LocalHoldingRecord(
        PORTFOLIO.user_id,
        PORTFOLIO.portfolio_id,
        f"00000000-0000-4000-8000-{next(HOLDING_SEQUENCE):012x}",
        instrument,
        quantity,
        cost,
        "USD",
        NOW,
        NOW,
    )


def metrics(rows: tuple[LocalHoldingRecord, ...]):
    quotes = SyntheticLocalPortfolioQuotes().snapshot(tuple(row.instrument_id for row in rows))
    return calculate_portfolio_metrics(
        PORTFOLIO, rows, SyntheticLocalPortfolioCatalog().snapshot(), quotes if rows else None, NOW
    )


def test_two_asset_gain_vector_and_exact_strings() -> None:
    result = metrics(
        (holding("SYN:AAPL", "10.000000", "150.0000"), holding("SYN:BND", "25.000000", "80.0000"))
    )
    assert result.valuation_status == "COMPLETE"
    assert result.totals.cost_basis == "3500.00"
    assert result.totals.market_value == "4000.00"
    assert result.totals.gain_loss == "500.00"
    assert result.totals.gain_loss_percent == "14.29"
    assert [row.weight_percent for row in result.holdings] == ["50.00", "50.00"]
    assert result.totals.concentration_percent == "50.00"
    assert result.totals.hhi == "0.500000"
    assert result.totals.educational_spread_percent == "50.00"
    assert result.source_type == "SYNTHETIC" and result.fixture_as_of == "2026-01-01T00:00:00Z"
    assert result.calculated_at == NOW.isoformat()


def test_loss_and_single_position_concentration() -> None:
    result = metrics((holding("SYN:MSFT", "5.000000", "500.0000"),))
    assert (
        result.totals.cost_basis,
        result.totals.market_value,
        result.totals.gain_loss,
        result.totals.gain_loss_percent,
    ) == ("2500.00", "2000.00", "-500.00", "-20.00")
    assert (
        result.totals.concentration_percent,
        result.totals.hhi,
        result.totals.educational_spread_percent,
    ) == ("100.00", "1.000000", "0.00")


def test_three_equal_holdings_use_unrounded_ratios_without_a_residual() -> None:
    result = metrics(
        (
            holding("SYN:AAPL", "1.000000", "200.0000"),
            holding("SYN:MSFT", "0.500000", "400.0000"),
            holding("SYN:BND", "2.500000", "80.0000"),
        )
    )
    assert result.totals.market_value == "600.00"
    assert [row.weight_percent for row in result.holdings] == ["33.33"] * 3
    assert result.totals.hhi == "0.333333"
    assert result.totals.educational_spread_percent == "66.67"
    assert result.totals.allocation_by_asset_class is not None
    assert [
        (row.group, row.market_value, row.weight_percent)
        for row in result.totals.allocation_by_asset_class
    ] == [("BOND", "200.00", "33.33"), ("EQUITY", "400.00", "66.67")]


def test_default_catalogue_row_rounding_reconciles_not_raw_aggregate() -> None:
    result = metrics(
        (holding("SYN:AAPL", "0.005025", "100.0000"), holding("SYN:BND", "0.012563", "40.0000"))
    )
    assert [(row.cost_basis, row.market_value) for row in result.holdings] == [
        ("0.50", "1.01"),
        ("0.50", "1.01"),
    ]
    assert (
        result.totals.cost_basis,
        result.totals.market_value,
        result.totals.gain_loss,
        result.totals.gain_loss_percent,
    ) == ("1.00", "2.02", "1.02", "102.00")


@pytest.mark.parametrize(
    "rows",
    [
        (),
        (holding("SYN:AAPL", "0.000001", "0.0000"),),
        (holding("SYN:AAPL", "1.000000", "0.0000"),),
    ],
)
def test_zero_cost_always_has_null_gain_percentage(rows: tuple[LocalHoldingRecord, ...]) -> None:
    result = metrics(rows)
    assert result.totals.gain_loss_percent is None
    assert result.totals.cost_basis == "0.00"
    assert result.valuation_status == ("EMPTY" if not rows else "COMPLETE")


def test_zero_value_with_positive_cost_keeps_negative_gain_percentage() -> None:
    result = metrics((holding("SYN:AAPL", "0.000001", "1000000.0000"),))
    assert result.valuation_status == "COMPLETE"
    assert (
        result.totals.cost_basis,
        result.totals.market_value,
        result.totals.gain_loss,
        result.totals.gain_loss_percent,
    ) == ("1.00", "0.00", "-1.00", "-100.00")
    assert result.holdings[0].weight_percent is None
    assert result.totals.hhi is None and result.totals.educational_spread_percent is None
    assert result.totals.allocation_by_sector is not None
    assert result.totals.allocation_by_sector[0].weight_percent is None


@pytest.mark.parametrize("priced", [True, False])
def test_partial_and_all_missing_never_renormalize_or_substitute(priced: bool) -> None:
    rows = ((holding("SYN:AAPL", "10.000000", "150.0000"),) if priced else ()) + (
        holding("SYN:UNAVAILABLE", "1.000000", "5.0000"),
    )
    result = metrics(rows)
    assert result.valuation_status == ("INCOMPLETE" if priced else "UNAVAILABLE")
    assert result.totals.cost_basis == ("1505.00" if priced else "5.00")
    assert result.totals.market_value is None and result.totals.gain_loss is None
    assert result.totals.allocation_by_asset_class is None
    assert result.totals.concentration_percent is None and result.totals.hhi is None
    assert result.totals.educational_spread_percent is None
    assert all(row.weight_percent is None for row in result.holdings)
    assert result.missing_instrument_ids == ["SYN:UNAVAILABLE"]
    missing = result.holdings[-1]
    assert missing.quote.unit_price is None and missing.quote.quote_as_of is None
    assert missing.market_value is None and missing.gain_loss_percent is None
    if priced:
        assert result.holdings[0].market_value == "2000.00"
        assert result.holdings[0].gain_loss_percent == "33.33"


def test_maximum_cost_and_global_decimal_context_are_preserved() -> None:
    before = getcontext().copy()
    result = metrics((holding("SYN:AAPL", "1000000.000000", "1000000.0000"),))
    assert result.totals.cost_basis == "1000000000000.00"
    assert result.totals.market_value == "200000000.00"
    assert getcontext().prec == before.prec and getcontext().rounding == before.rounding
    assert getcontext().flags == before.flags


def test_ambient_precision_rounding_and_inexact_trap_cannot_change_the_formula() -> None:
    with localcontext() as ambient:
        ambient.prec = 2
        ambient.rounding = ROUND_DOWN
        ambient.Emin = -2
        ambient.Emax = 2
        ambient.traps[Inexact] = True
        ambient.traps[Rounded] = True
        before = ambient.copy()
        result = metrics(
            (
                holding("SYN:AAPL", "10.000000", "150.0000"),
                holding("SYN:BND", "25.000000", "80.0000"),
            )
        )
        assert result.totals.gain_loss_percent == "14.29"
        assert ambient.prec == before.prec and ambient.rounding == before.rounding
        assert ambient.flags == before.flags and ambient.traps == before.traps
        assert ambient.Emin == before.Emin and ambient.Emax == before.Emax
        assert ambient.capitals == before.capitals and ambient.clamp == before.clamp


def test_mutable_default_context_cannot_change_frozen_math_or_current_context() -> None:
    saved_default = DefaultContext.copy()
    saved_current = getcontext().copy()
    try:
        DefaultContext.prec = 2
        DefaultContext.rounding = ROUND_DOWN
        DefaultContext.Emin = -2
        DefaultContext.Emax = 2
        DefaultContext.capitals = 0
        DefaultContext.clamp = 1
        DefaultContext.flags[Inexact] = True
        DefaultContext.flags[Rounded] = True
        DefaultContext.traps[Inexact] = True
        DefaultContext.traps[Rounded] = True
        result = metrics(
            (
                holding("SYN:AAPL", "10.000000", "150.0000"),
                holding("SYN:BND", "25.000000", "80.0000"),
            )
        )
        assert result.totals.gain_loss_percent == "14.29"
        assert result.totals.market_value == "4000.00"
        current = getcontext()
        assert (
            current.prec,
            current.rounding,
            current.Emin,
            current.Emax,
            current.capitals,
            current.clamp,
        ) == (
            saved_current.prec,
            saved_current.rounding,
            saved_current.Emin,
            saved_current.Emax,
            saved_current.capitals,
            saved_current.clamp,
        )
        assert current.flags == saved_current.flags and current.traps == saved_current.traps
    finally:
        DefaultContext.prec = saved_default.prec
        DefaultContext.rounding = saved_default.rounding
        DefaultContext.Emin = saved_default.Emin
        DefaultContext.Emax = saved_default.Emax
        DefaultContext.capitals = saved_default.capitals
        DefaultContext.clamp = saved_default.clamp
        for signal, value in saved_default.flags.items():
            DefaultContext.flags[signal] = value
        for signal, value in saved_default.traps.items():
            DefaultContext.traps[signal] = value
