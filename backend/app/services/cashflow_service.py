"""Deterministic, owner-scoped cash-flow aggregation and category rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal, Protocol

from app.repositories.spending_repository import spending_repository
from app.schemas.sprint5_privacy_spending import SpendingTransaction

FlowDirection = Literal["income", "expense"]
CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CategoryRule:
    """Map matching category or masked-description text to a category and flow type.

    Rules are evaluated in the order provided. Text matching is case-insensitive and
    matches whole terms, so short words cannot match inside unrelated categories.
    """

    match_any: tuple[str, ...]
    category: str
    direction: FlowDirection

    def __post_init__(self) -> None:
        if not self.match_any or any(not value.strip() for value in self.match_any):
            raise ValueError("category rules need at least one non-empty match term")
        if not self.category.strip():
            raise ValueError("category rules need a category")
        if self.direction not in ("income", "expense"):
            raise ValueError("category rule direction must be income or expense")


DEFAULT_CATEGORY_RULES: tuple[CategoryRule, ...] = (
    CategoryRule(
        match_any=("salary", "paycheck", "payroll", "wage", "income"),
        category="Income",
        direction="income",
    ),
    CategoryRule(
        match_any=("refund", "reimbursement", "cashback", "cash back"),
        category="Refunds",
        direction="income",
    ),
    CategoryRule(
        match_any=("dividend", "interest earned"),
        category="Investment income",
        direction="income",
    ),
)


@dataclass(frozen=True, slots=True)
class CategoryCashFlow:
    category: str
    direction: FlowDirection
    amount: Decimal
    transaction_count: int


@dataclass(frozen=True, slots=True)
class CashFlowSummary:
    period_start: date
    period_end: date
    income_total: Decimal
    expense_total: Decimal
    net_cash_flow: Decimal
    transaction_count: int
    categories: tuple[CategoryCashFlow, ...]


class SpendingTransactionSource(Protocol):
    """Minimal owner-scoped repository interface needed by the service."""

    def list_transactions(self, user_id: str) -> list[SpendingTransaction]: ...


def _date_only(value: date | str, field_name: str) -> date:
    if isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a date, not a datetime")
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an ISO date (YYYY-MM-DD)") from exc
        return parsed
    raise ValueError(f"{field_name} must be a date or ISO date string")


def _money(value: Decimal | int | float | str) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("transaction amounts must be valid decimals") from exc
    if not amount.is_finite():
        raise ValueError("transaction amounts must be finite")
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def _transaction_date(value: date | str) -> date:
    return _date_only(value, "transaction date")


def _rule_for(
    transaction: SpendingTransaction, rules: tuple[CategoryRule, ...]
) -> CategoryRule | None:
    searchable = f"{transaction.category} {transaction.description_masked}".casefold()
    return next(
        (
            rule
            for rule in rules
            if any(
                re.search(
                    rf"(?<![a-z0-9]){re.escape(term.casefold())}(?![a-z0-9])",
                    searchable,
                )
                for term in rule.match_any
            )
        ),
        None,
    )


def calculate_cash_flow(
    transactions: list[SpendingTransaction] | tuple[SpendingTransaction, ...],
    period_start: date | str,
    period_end: date | str,
    *,
    rules: tuple[CategoryRule, ...] = DEFAULT_CATEGORY_RULES,
) -> CashFlowSummary:
    """Aggregate an already owner-scoped transaction collection for an inclusive period.

    Positive transaction amounts follow FinEx's spending convention and represent
    expenses. Negative amounts represent credits and are reported as positive income.
    Category rules can explicitly classify and rename matching transactions.
    Every input is rounded to cents before it enters a bucket; all totals are then
    derived from those buckets so category totals reconcile exactly.
    """
    start = _date_only(period_start, "period_start")
    end = _date_only(period_end, "period_end")
    if start > end:
        raise ValueError("period_start must not be after period_end")

    amounts: dict[tuple[FlowDirection, str], Decimal] = {}
    counts: dict[tuple[FlowDirection, str], int] = {}
    for transaction in transactions:
        transaction_day = _transaction_date(transaction.date)
        if not start <= transaction_day <= end:
            continue

        amount = _money(transaction.amount)
        if amount == 0:
            continue
        matched_rule = _rule_for(transaction, rules)
        if matched_rule is not None:
            direction = matched_rule.direction
            category = matched_rule.category.strip()
        elif amount < 0:
            direction = "income"
            category = transaction.category.strip() or "Income"
        else:
            direction = "expense"
            category = transaction.category.strip() or "Uncategorized"

        key = (direction, category)
        amounts[key] = amounts.get(key, Decimal("0.00")) + abs(amount)
        counts[key] = counts.get(key, 0) + 1

    categories = tuple(
        CategoryCashFlow(
            category=category,
            direction=direction,
            amount=amounts[(direction, category)].quantize(CENT),
            transaction_count=counts[(direction, category)],
        )
        for direction, category in sorted(
            amounts, key=lambda key: (0 if key[0] == "income" else 1, key[1].casefold())
        )
    )
    income = sum(
        (item.amount for item in categories if item.direction == "income"), Decimal("0.00")
    ).quantize(CENT)
    expenses = sum(
        (item.amount for item in categories if item.direction == "expense"), Decimal("0.00")
    ).quantize(CENT)
    return CashFlowSummary(
        period_start=start,
        period_end=end,
        income_total=income,
        expense_total=expenses,
        net_cash_flow=(income - expenses).quantize(CENT),
        transaction_count=sum(item.transaction_count for item in categories),
        categories=categories,
    )


def get_cash_flow(
    user_id: str,
    period_start: date | str,
    period_end: date | str,
    *,
    repository: SpendingTransactionSource | None = None,
    rules: tuple[CategoryRule, ...] = DEFAULT_CATEGORY_RULES,
) -> CashFlowSummary:
    """Read one user's saved transactions and calculate their cash flow."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id is required")
    source = repository or spending_repository
    return calculate_cash_flow(
        source.list_transactions(user_id), period_start, period_end, rules=rules
    )


__all__ = [
    "DEFAULT_CATEGORY_RULES",
    "CategoryCashFlow",
    "CategoryRule",
    "CashFlowSummary",
    "calculate_cash_flow",
    "get_cash_flow",
]
