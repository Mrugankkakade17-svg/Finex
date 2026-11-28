from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.twin_service import TwinService, calculate_runway


def test_runway_uses_only_positive_expenses_inside_inclusive_lookback():
    transactions = [
        SimpleNamespace(date="2026-09-01", amount=Decimal("300.00")),
        SimpleNamespace(date="2026-09-02", amount=Decimal("310.00")),
        SimpleNamespace(date="2026-11-28", amount=Decimal("-200.00")),
    ]

    runway = calculate_runway("3000", transactions, as_of=date(2026, 11, 28), lookback_days=90)

    assert runway["monthly_expenses_estimate"] == Decimal("206.30")
    assert runway["estimated_months"] == Decimal("14.5")
    assert runway["status"] == "ESTIMATE"


def test_runway_without_expense_history_is_unknown_not_infinite():
    runway = calculate_runway("500", [], as_of=date(2026, 11, 28))

    assert runway["monthly_expenses_estimate"] == Decimal("0.00")
    assert runway["estimated_months"] is None
    assert runway["status"] == "INSUFFICIENT_SPENDING_HISTORY"


@pytest.mark.asyncio
async def test_snapshot_labels_manual_and_paper_figures_and_does_not_combine_them():
    class Portfolios:
        async def list_portfolios(self, user_id):
            assert user_id == "user-a"
            return [
                SimpleNamespace(currency="USD", total_value=1250),
                SimpleNamespace(currency="USD", total_value=Decimal("50.25")),
                SimpleNamespace(currency="EUR", total_value=Decimal("10")),
            ]

    class Paper:
        def get_account(self, user_id):
            assert user_id == "user-a"
            return {
                "cash_balance": Decimal("100"),
                "total_equity": Decimal("120"),
                "currency": "USD",
            }

    class Spending:
        def list_transactions(self, user_id):
            assert user_id == "user-a"
            return [SimpleNamespace(date="2026-11-28", amount=Decimal("30"))]

    snapshot = await TwinService(Portfolios(), Paper(), Spending()).snapshot(
        "user-a", as_of=date(2026, 11, 28)
    )

    assert snapshot["figures"] == [
        {
            "label": "manual investment assets",
            "source": "manual_portfolios",
            "currency": "EUR",
            "amount": Decimal("10.00"),
            "kind": "assets",
        },
        {
            "label": "manual investment assets",
            "source": "manual_portfolios",
            "currency": "USD",
            "amount": Decimal("1300.25"),
            "kind": "assets",
        },
        {
            "label": "paper account equity (cash plus paper positions)",
            "source": "paper_account",
            "currency": "USD",
            "amount": Decimal("120.00"),
            "kind": "simulated_assets",
        },
    ]
    assert snapshot["combined_net_worth"] is None
    assert snapshot["liabilities"]["complete"] is False
    assert snapshot["excluded_sources"][0]["source"] == "legacy_shared_simulation"


def test_runway_rejects_invalid_cash_and_lookback():
    with pytest.raises(ValueError, match="non-negative"):
        calculate_runway("-1", [], as_of=date(2026, 11, 28))
    with pytest.raises(ValueError, match="positive"):
        calculate_runway("1", [], as_of=date(2026, 11, 28), lookback_days=0)

