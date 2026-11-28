"""Build a labelled financial snapshot without mixing account types or currencies."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def _money(value: object) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise ValueError("Financial snapshot values must be finite.")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _transaction_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def calculate_runway(
    cash_balance: Decimal | int | str,
    transactions: Iterable[Any],
    *,
    as_of: date,
    lookback_days: int = 90,
) -> dict[str, object]:
    """Estimate runway from labelled cash and recent observed spending only."""
    if lookback_days < 1:
        raise ValueError("lookback_days must be positive.")
    cash = _money(cash_balance)
    if cash < 0:
        raise ValueError("cash_balance must be non-negative.")
    start = as_of - timedelta(days=lookback_days - 1)
    expenses = ZERO
    for transaction in transactions:
        day = _transaction_date(transaction.date)
        amount = _money(transaction.amount)
        if start <= day <= as_of and amount > 0:
            expenses += amount
    monthly_burn = (expenses / Decimal(lookback_days) * Decimal("30.4375")).quantize(
        CENT, rounding=ROUND_HALF_UP
    )
    months = (
        (cash / monthly_burn).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if monthly_burn
        else None
    )
    return {
        "cash_amount": cash,
        "cash_label": "persistent paper account cash",
        "monthly_expenses_estimate": monthly_burn,
        "monthly_expenses_period_days": lookback_days,
        "estimated_months": months,
        "as_of_date": as_of,
        "status": "ESTIMATE" if monthly_burn else "INSUFFICIENT_SPENDING_HISTORY",
    }


class TwinService:
    """Orchestrate owner-scoped sources; keep reported values separately labelled."""

    def __init__(self, portfolio_source: Any, paper_source: Any, spending_source: Any) -> None:
        self.portfolio_source = portfolio_source
        self.paper_source = paper_source
        self.spending_source = spending_source

    async def snapshot(self, user_id: str, *, as_of: date | None = None) -> dict[str, object]:
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required.")
        today = as_of or date.today()
        portfolios = await self.portfolio_source.list_portfolios(user_id)
        paper = self.paper_source.get_account(user_id)
        transactions = self.spending_source.list_transactions(user_id)

        manual_by_currency: dict[str, Decimal] = {}
        for portfolio in portfolios:
            currency = portfolio.currency.upper()
            manual_by_currency[currency] = manual_by_currency.get(currency, ZERO) + _money(
                portfolio.total_value
            )

        figures = [
            {
                "label": "manual investment assets",
                "source": "manual_portfolios",
                "currency": currency,
                "amount": amount.quantize(CENT),
                "kind": "assets",
            }
            for currency, amount in sorted(manual_by_currency.items())
        ]
        figures.append(
            {
                "label": "paper account equity (cash plus paper positions)",
                "source": "paper_account",
                "currency": str(paper.get("currency", "USD")).upper(),
                "amount": _money(paper["total_equity"]),
                "kind": "simulated_assets",
            }
        )
        return {
            "as_of_date": today,
            "figures": figures,
            "combined_net_worth": None,
            "combined_net_worth_note": (
                "Not calculated: source figures are separate, currencies may differ, "
                "and liabilities are not recorded."
            ),
            "runway": calculate_runway(paper["cash_balance"], transactions, as_of=today),
            "liabilities": {
                "reported_amount": None,
                "currency": None,
                "items": [],
                "complete": False,
                "note": "Liability records are not available in the current data model.",
            },
            "excluded_sources": [
                {
                    "source": "legacy_shared_simulation",
                    "reason": "The legacy in-memory demo account is shared and has no owner scope.",
                }
            ],
        }


__all__ = ["TwinService", "calculate_runway"]

