"""Deterministic display-value arithmetic for owned manual synthetic holdings only."""

from dataclasses import dataclass
from datetime import datetime
from decimal import (
    ROUND_HALF_UP,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from typing import Literal

from app.domain.local_portfolio import (
    HOLDING_LIMIT,
    LocalCatalogUnavailable,
    LocalHoldingRecord,
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteRecord,
    LocalPortfolioQuoteSnapshot,
    LocalPortfolioRecord,
    LocalQuoteUnavailable,
    validate_holding_record,
    validate_portfolio_record,
)
from app.ports.adapters.synthetic_local_portfolio import (
    validate_catalogue_snapshot,
    validate_quote_snapshot,
)
from app.schemas.local_portfolio import (
    LocalPortfolioAllocation,
    LocalPortfolioMetricHolding,
    LocalPortfolioMetricQuote,
    LocalPortfolioMetrics,
    LocalPortfolioTotals,
)
from app.services.local_authorization import utc_now

_CENT = Decimal("0.01")
_HHI_UNIT = Decimal("0.000001")
_ZERO = Decimal(0)
_HUNDRED = Decimal(100)


def _text(number: Decimal, unit: Decimal = _CENT) -> str:
    rounded = number.quantize(unit, rounding=ROUND_HALF_UP)
    return format(abs(rounded) if rounded == 0 else rounded, "f")


def _gain_percent(gain: Decimal, cost: Decimal) -> str | None:
    return _text(_HUNDRED * gain / cost) if cost > 0 else None


@dataclass(frozen=True)
class _CalculatedHolding:
    record: LocalHoldingRecord
    instrument: LocalPortfolioInstrument
    quote: LocalPortfolioQuoteRecord
    cost: Decimal
    value: Decimal | None


def _allocations(groups: dict[str, Decimal], total: Decimal) -> list[LocalPortfolioAllocation]:
    return [
        LocalPortfolioAllocation(
            group=group,
            market_value=_text(value),
            weight_percent=_text(_HUNDRED * value / total) if total > 0 else None,
        )
        for group, value in sorted(groups.items())
    ]


def calculate_portfolio_metrics(
    portfolio: LocalPortfolioRecord,
    holdings: tuple[LocalHoldingRecord, ...],
    catalogue: LocalPortfolioCatalogSnapshot,
    quotes: LocalPortfolioQuoteSnapshot | None,
    calculated_at: datetime,
) -> LocalPortfolioMetrics:
    """Round each row once, sum displayed cents, and never renormalize missing quotes."""
    validate_portfolio_record(portfolio)
    utc_now(lambda: calculated_at)
    if type(holdings) is not tuple or len(holdings) > HOLDING_LIMIT:
        raise ValueError("A bounded immutable holding snapshot is required.")
    for row in holdings:
        validate_holding_record(row, user_id=portfolio.user_id, portfolio_id=portfolio.portfolio_id)
    if len({r.holding_id for r in holdings}) != len(holdings) or (
        len({r.instrument_id for r in holdings}) != len(holdings)
    ):
        raise ValueError("Holding identities must be unique.")
    catalogue = validate_catalogue_snapshot(catalogue)
    instruments = {r.instrument_id: r for r in catalogue.items}
    if any(row.instrument_id not in instruments for row in holdings):
        raise LocalCatalogUnavailable()
    ordered = tuple(sorted(holdings, key=lambda row: (row.created_at, row.holding_id)))
    requested = tuple(row.instrument_id for row in ordered)
    if ordered:
        if quotes is None:
            raise LocalQuoteUnavailable()
        snapshot = validate_quote_snapshot(quotes, requested)
        quote_rows = {q.instrument_id: q for q in snapshot.quotes}
    else:
        if quotes is not None:
            raise LocalQuoteUnavailable()
        quote_rows = {}

    # A fresh local context also avoids inherited traps/precision changing the frozen arithmetic.
    with localcontext(
        Context(
            prec=50,
            rounding=ROUND_HALF_UP,
            Emin=-999999,
            Emax=999999,
            capitals=1,
            clamp=0,
            flags=[],
            traps=[InvalidOperation, DivisionByZero, Overflow],
        )
    ):
        calculated: list[_CalculatedHolding] = []
        for row in ordered:
            quote = quote_rows[row.instrument_id]
            cost = (Decimal(row.quantity) * Decimal(row.average_cost)).quantize(_CENT)
            value = (
                (Decimal(row.quantity) * Decimal(quote.unit_price)).quantize(_CENT)
                if quote.unit_price is not None
                else None
            )
            calculated.append(
                _CalculatedHolding(row, instruments[row.instrument_id], quote, cost, value)
            )
        missing = sorted(row.record.instrument_id for row in calculated if row.value is None)
        state: Literal["COMPLETE", "EMPTY", "INCOMPLETE", "UNAVAILABLE"]
        if not calculated:
            state = "EMPTY"
        elif not missing:
            state = "COMPLETE"
        else:
            state = "UNAVAILABLE" if len(missing) == len(calculated) else "INCOMPLETE"
        complete = not missing
        total_cost = sum((row.cost for row in calculated), _ZERO)
        total_value = (
            sum((row.value for row in calculated if row.value is not None), _ZERO)
            if complete
            else None
        )
        raw_hhi = (
            sum(
                ((row.value / total_value) ** 2 for row in calculated if row.value is not None),
                _ZERO,
            )
            if total_value is not None and total_value > 0
            else None
        )
        rows: list[LocalPortfolioMetricHolding] = []
        asset_values: dict[str, Decimal] = {}
        sector_values: dict[str, Decimal] = {}
        for entry in calculated:
            gain = entry.value - entry.cost if entry.value is not None else None
            weight = (
                _text(_HUNDRED * entry.value / total_value)
                if entry.value is not None and total_value is not None and total_value > 0
                else None
            )
            rows.append(
                LocalPortfolioMetricHolding(
                    holding_version="holding.v1",
                    portfolio_id=portfolio.portfolio_id,
                    holding_id=entry.record.holding_id,
                    instrument_id=entry.record.instrument_id,
                    display_name=entry.instrument.display_name,
                    asset_class=entry.instrument.asset_class,
                    sector=entry.instrument.sector,
                    currency="USD",
                    quantity=entry.record.quantity,
                    average_cost=entry.record.average_cost,
                    cost_basis=_text(entry.cost),
                    quote=LocalPortfolioMetricQuote(
                        unit_price=entry.quote.unit_price,
                        data_status="CACHED"
                        if entry.quote.unit_price is not None
                        else "UNAVAILABLE",
                        quote_as_of="2026-01-01T00:00:00Z"
                        if entry.quote.unit_price is not None
                        else None,
                        reason=None
                        if entry.quote.unit_price is not None
                        else "SYNTHETIC_QUOTE_UNAVAILABLE",
                    ),
                    market_value=_text(entry.value) if entry.value is not None else None,
                    gain_loss=_text(gain) if gain is not None else None,
                    gain_loss_percent=_gain_percent(gain, entry.cost) if gain is not None else None,
                    weight_percent=weight,
                )
            )
            if entry.value is not None:
                asset_values[entry.instrument.asset_class] = (
                    asset_values.get(entry.instrument.asset_class, _ZERO) + entry.value
                )
                sector_values[entry.instrument.sector] = (
                    sector_values.get(entry.instrument.sector, _ZERO) + entry.value
                )
        total_gain = total_value - total_cost if total_value is not None else None
        maximum = max((row.value for row in calculated if row.value is not None), default=_ZERO)
        totals = LocalPortfolioTotals(
            cost_basis=_text(total_cost),
            market_value=_text(total_value) if total_value is not None else None,
            gain_loss=_text(total_gain) if total_gain is not None else None,
            gain_loss_percent=_gain_percent(total_gain, total_cost)
            if total_gain is not None
            else None,
            allocation_by_asset_class=_allocations(asset_values, total_value)
            if total_value is not None
            else None,
            allocation_by_sector=_allocations(sector_values, total_value)
            if total_value is not None
            else None,
            concentration_percent=_text(_HUNDRED * maximum / total_value)
            if total_value is not None and total_value > 0
            else None,
            hhi=_text(raw_hhi, _HHI_UNIT) if raw_hhi is not None else None,
            educational_spread_percent=_text(_HUNDRED * (1 - raw_hhi))
            if raw_hhi is not None
            else None,
        )
        return LocalPortfolioMetrics(
            scope="local_educational_application",
            contract_version="local.v1",
            metrics_version="portfolio_metrics.v1",
            formula_version="manual_portfolio_math.v1",
            catalog_version="synthetic_catalog.v1",
            quote_snapshot_version="synthetic_quotes.v1",
            portfolio_id=portfolio.portfolio_id,
            currency="USD",
            valuation_status=state,
            source="finex.synthetic.portfolio",
            source_type="SYNTHETIC",
            fixture_as_of="2026-01-01T00:00:00Z",
            calculated_at=calculated_at.isoformat(),
            missing_instrument_ids=missing,
            limitations=[
                "SYNTHETIC_QUOTES_NOT_MARKET_DATA",
                "MANUAL_HOLDINGS_NOT_BROKER_POSITIONS",
                "SPREAD_IS_ALLOCATION_ONLY",
                "NO_FUND_LOOKTHROUGH_OR_SUITABILITY",
            ],
            holdings=rows,
            totals=totals,
        )
