"""Compare legacy and local portfolio math on shared deterministic fixtures."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.domain.local_portfolio import (  # noqa: E402
    FIXTURE_AS_OF,
    QUOTE_SNAPSHOT_VERSION,
    QUOTE_SOURCE,
    QUOTE_SOURCE_TYPE,
    LocalHoldingRecord,
    LocalPortfolioQuoteRecord,
    LocalPortfolioQuoteSnapshot,
    LocalPortfolioRecord,
)
from app.ports.adapters.synthetic_local_portfolio import (  # noqa: E402
    SyntheticLocalPortfolioCatalog,
)
from app.services.local_portfolio_math import calculate_portfolio_metrics  # noqa: E402
from app.services.portfolio_math import compute_portfolio_valuations  # noqa: E402

NOW = datetime(2026, 10, 11, 18, 0, 0, tzinfo=timezone.utc)
PORTFOLIO_ID = "00000000-0000-4000-8000-000000000001"


@dataclass(frozen=True)
class ParityHolding:
    instrument_id: str
    symbol: str
    quantity: str
    average_cost: str
    current_price: str
    asset_class: str
    sector: str


SHARED_FIXTURES: tuple[tuple[str, tuple[ParityHolding, ...]], ...] = (
    (
        "gain",
        (
            ParityHolding(
                "SYN:AAPL",
                "AAPL",
                "10.000000",
                "150.0000",
                "200.0000",
                "EQUITY",
                "Technology",
            ),
        ),
    ),
    (
        "loss",
        (
            ParityHolding(
                "SYN:MSFT",
                "MSFT",
                "5.000000",
                "500.0000",
                "400.0000",
                "EQUITY",
                "Technology",
            ),
        ),
    ),
    (
        "two_asset",
        (
            ParityHolding(
                "SYN:AAPL",
                "AAPL",
                "10.000000",
                "150.0000",
                "200.0000",
                "EQUITY",
                "Technology",
            ),
            ParityHolding(
                "SYN:BND",
                "BND",
                "25.000000",
                "80.0000",
                "80.0000",
                "FIXED_INCOME",
                "Government",
            ),
        ),
    ),
    (
        "fractional_rounding",
        (
            ParityHolding(
                "SYN:AAPL",
                "AAPL",
                "0.005025",
                "100.0000",
                "200.0000",
                "EQUITY",
                "Technology",
            ),
            ParityHolding(
                "SYN:BND",
                "BND",
                "0.012563",
                "40.0000",
                "80.0000",
                "FIXED_INCOME",
                "Government",
            ),
        ),
    ),
)


def _money(value: object) -> str:
    decimal = Decimal(str(value)).quantize(Decimal("0.01"))
    return format(decimal, ".2f")


def _legacy_result(
    holdings: tuple[ParityHolding, ...],
) -> dict[str, object]:
    raw = [
        {
            "holding_id": f"h-{index}",
            "portfolio_id": PORTFOLIO_ID,
            "user_id": "synthetic-owner",
            "symbol": row.symbol,
            "asset_class": row.asset_class,
            "sector": row.sector,
            "quantity": float(row.quantity),
            "avg_buy_price": float(row.average_cost),
        }
        for index, row in enumerate(holdings, start=1)
    ]
    quotes = {row.symbol: float(row.current_price) for row in holdings}
    total_value, total_cost, gain_loss, gain_pct, evaluated = compute_portfolio_valuations(
        raw, quotes
    )
    return {
        "cost_basis": _money(total_cost),
        "market_value": _money(total_value),
        "gain_loss": _money(gain_loss),
        "gain_loss_percent": _money(gain_pct),
        "weights": [_money(row.weight_pct) for row in evaluated],
    }


def _local_result(holdings: tuple[ParityHolding, ...]) -> dict[str, object]:
    portfolio = LocalPortfolioRecord(
        "synthetic-owner",
        PORTFOLIO_ID,
        "Parity",
        None,
        "USD",
        NOW,
        NOW,
    )
    local_holdings = tuple(
        LocalHoldingRecord(
            "synthetic-owner",
            PORTFOLIO_ID,
            f"00000000-0000-4000-8000-{index:012x}",
            row.instrument_id,
            row.quantity,
            row.average_cost,
            "USD",
            NOW,
            NOW,
        )
        for index, row in enumerate(holdings, start=1)
    )
    catalogue = SyntheticLocalPortfolioCatalog().snapshot()
    quotes = LocalPortfolioQuoteSnapshot(
        QUOTE_SNAPSHOT_VERSION,
        QUOTE_SOURCE,
        QUOTE_SOURCE_TYPE,
        FIXTURE_AS_OF,
        tuple(
            LocalPortfolioQuoteRecord(
                row.instrument_id,
                row.current_price,
                "CACHED",
                FIXTURE_AS_OF,
                None,
            )
            for row in holdings
        ),
    )
    result = calculate_portfolio_metrics(portfolio, local_holdings, catalogue, quotes, NOW)
    return {
        "cost_basis": result.totals.cost_basis,
        "market_value": result.totals.market_value,
        "gain_loss": result.totals.gain_loss,
        "gain_loss_percent": result.totals.gain_loss_percent,
        "weights": [row.weight_percent for row in result.holdings],
        "prices_used": [row.quote.unit_price for row in result.holdings],
    }


def compare_fixtures() -> dict[str, object]:
    """Return fixture results and explicit parity differences."""
    comparisons: list[dict[str, object]] = []
    mismatches: list[str] = []
    canonical = "app.services.local_portfolio_math.calculate_portfolio_metrics"

    for fixture_name, holdings in SHARED_FIXTURES:
        legacy = _legacy_result(holdings)
        local = _local_result(holdings)
        differences = {
            key: {"legacy": legacy[key], "canonical": local[key]}
            for key in legacy
            if legacy[key] != local[key]
        }
        if differences:
            mismatches.append(fixture_name)
        comparisons.append(
            {
                "fixture": fixture_name,
                "legacy": legacy,
                "canonical": {key: local[key] for key in legacy},
                "prices_used": {
                    "legacy": [row.current_price for row in holdings],
                    "canonical": local["prices_used"],
                },
                "differences": differences,
            }
        )

    return {
        "canonical_module": canonical,
        "reason": "Decimal exactness, isolated context, and bounded canonical decimal strings",
        "comparisons": comparisons,
        "mismatching_fixtures": mismatches,
    }


def main() -> int:
    print(json.dumps(compare_fixtures(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
