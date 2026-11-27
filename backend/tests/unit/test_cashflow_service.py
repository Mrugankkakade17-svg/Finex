"""Deterministic cash-flow aggregation and owner-scoped service tests."""

from datetime import date, datetime
from decimal import Decimal

import pytest

from app.schemas.sprint5_privacy_spending import SpendingTransaction
from app.services.cashflow_service import (
    CategoryRule,
    calculate_cash_flow,
)


def transaction(
    transaction_id: str,
    day: str = "2026-11-15",
    amount: str = "10.00",
    category: str = "Groceries",
    description: str = "MARKET PURCHASE",
) -> SpendingTransaction:
    return SpendingTransaction(
        transaction_id=transaction_id,
        date=day,
        amount=Decimal(amount),
        category=category,
        description_masked=description,
    )


def test_cash_flow_totals_reconcile_to_cents_after_per_transaction_rounding() -> None:
    summary = calculate_cash_flow(
        [
            transaction("expense-1", amount="10.005"),
            transaction("expense-2", amount="2.004", category="Dining"),
            transaction("credit-1", amount="-3.335", category="Refund"),
        ],
        "2026-11-01",
        "2026-11-30",
    )

    assert summary.income_total == Decimal("3.34")
    assert summary.expense_total == Decimal("12.01")
    assert summary.net_cash_flow == Decimal("-8.67")
    assert (
        sum(
            (item.amount for item in summary.categories if item.direction == "expense"),
            Decimal("0.00"),
        )
        == summary.expense_total
    )
    assert (
        sum(
            (item.amount for item in summary.categories if item.direction == "income"),
            Decimal("0.00"),
        )
        == summary.income_total
    )
    assert summary.transaction_count == 3


def test_category_rules_apply_in_declared_order_to_category_and_description() -> None:
    rules = (
        CategoryRule(("payroll",), "Employment income", "income"),
        CategoryRule(("refund",), "Refunds", "income"),
    )
    summary = calculate_cash_flow(
        [
            transaction("1", amount="1200", category="Other", description="ACME PAYROLL"),
            transaction("2", amount="25", category="Other", description="Card refund"),
            transaction("3", amount="4", category="Beverages", description="COFFEE SHOP"),
        ],
        date(2026, 11, 1),
        date(2026, 11, 30),
        rules=rules,
    )

    assert summary.income_total == Decimal("1225.00")
    assert summary.expense_total == Decimal("4.00")
    assert [(item.category, item.direction) for item in summary.categories] == [
        ("Employment income", "income"),
        ("Refunds", "income"),
        ("Beverages", "expense"),
    ]


def test_period_is_inclusive_empty_period_is_zero_and_output_is_sorted() -> None:
    summary = calculate_cash_flow(
        [
            transaction("before", day="2026-10-31", amount="50"),
            transaction("first", day="2026-11-01", amount="3", category="zeta"),
            transaction("last", day="2026-11-30", amount="2", category="Alpha"),
            transaction("after", day="2026-12-01", amount="100"),
        ],
        "2026-11-01",
        "2026-11-30",
        rules=(),
    )
    assert summary.expense_total == Decimal("5.00")
    assert [item.category for item in summary.categories] == ["Alpha", "zeta"]

    empty = calculate_cash_flow([], date(2026, 11, 1), date(2026, 11, 30))
    assert empty.income_total == empty.expense_total == empty.net_cash_flow == Decimal("0.00")
    assert empty.transaction_count == 0
    assert empty.categories == ()


@pytest.mark.parametrize(
    ("period_start", "period_end"),
    [
        (datetime(2026, 11, 1, 12), date(2026, 11, 30)),
        (date(2026, 12, 1), date(2026, 11, 30)),
        ("not-a-date", "2026-11-30"),
    ],
)
def test_invalid_period_is_rejected(period_start: date | datetime | str, period_end: date) -> None:
    with pytest.raises(ValueError):
        calculate_cash_flow([], period_start, period_end)


def test_datetime_transaction_date_and_non_finite_amount_are_rejected() -> None:
    with pytest.raises(ValueError, match="transaction date"):
        calculate_cash_flow(
            [transaction("1", day=datetime(2026, 11, 15, 8).isoformat())],
            "2026-11-01",
            "2026-11-30",
        )

    with pytest.raises(ValueError, match="finite"):
        calculate_cash_flow([transaction("2", amount="NaN")], "2026-11-01", "2026-11-30")


def test_category_rule_validates_configuration() -> None:
    with pytest.raises(ValueError, match="match term"):
        CategoryRule((" ",), "Income", "income")
    with pytest.raises(ValueError, match="category"):
        CategoryRule(("salary",), " ", "income")
