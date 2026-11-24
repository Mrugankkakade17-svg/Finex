"""Reconcile PA04 paper orders, materialized positions, and cash in exact units."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping


@dataclass(frozen=True)
class ReconciliationResult:
    """Computed order-ledger state compared with a paper account snapshot."""

    is_reconciled: bool
    expected_cash_cents: int
    actual_cash_cents: int
    expected_positions: dict[str, int]
    actual_positions: dict[str, int]
    cash_difference_cents: int
    position_differences: dict[str, int]


def _integer(value: object, field: str, *, positive: bool = False) -> int:
    if type(value) is not int or (positive and value <= 0):
        requirement = "a positive integer" if positive else "an integer"
        raise ValueError(f"{field} must be {requirement}")
    return value


def _field(row: object, name: str) -> object:
    if isinstance(row, Mapping):
        try:
            return row[name]
        except KeyError:
            raise ValueError(f"row is missing {name}") from None
    try:
        return getattr(row, name)
    except AttributeError:
        raise ValueError(f"row is missing {name}") from None


def reconcile_paper_account(
    orders: Iterable[object],
    positions: Mapping[str, object] | Iterable[object],
    cash_balance_cents: object,
    *,
    initial_cash_cents: object,
) -> ReconciliationResult:
    """Check whether filled PA04 orders explain current positions and cash.

    Order rows provide ``side``, ``quantity``, ``instrument_id``, and signed
    ``cash_delta_cents``. The cash delta already includes the configured fee, so
    reconciliation never recomputes notional or fees. Positions may be a
    mapping from instrument ID to quantity or rows with ``instrument_id`` and
    ``quantity`` fields. All money and quantities are exact integers.
    """

    expected_cash = _integer(initial_cash_cents, "initial_cash_cents")
    if expected_cash < 0:
        raise ValueError("initial_cash_cents must be non-negative")
    expected: defaultdict[str, int] = defaultdict(int)
    for order in orders:
        side = _field(order, "side")
        if not isinstance(side, str) or side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        instrument = _field(order, "instrument_id")
        if not isinstance(instrument, str) or not instrument or instrument != instrument.strip():
            raise ValueError("instrument_id must be a non-empty canonical string")
        quantity = _integer(_field(order, "quantity"), "quantity", positive=True)
        cash_delta = _integer(_field(order, "cash_delta_cents"), "cash_delta_cents")
        if (side == "BUY" and cash_delta >= 0) or (side == "SELL" and cash_delta <= 0):
            raise ValueError("cash_delta_cents sign must match the order side")
        expected_cash += cash_delta
        expected[instrument] += quantity if side == "BUY" else -quantity

    actual: dict[str, int] = {}
    rows = (
        positions.items()
        if isinstance(positions, Mapping)
        else (
            (_field(position, "instrument_id"), _field(position, "quantity"))
            for position in positions
        )
    )
    for instrument, quantity_value in rows:
        if not isinstance(instrument, str) or not instrument or instrument != instrument.strip():
            raise ValueError("instrument_id must be a non-empty canonical string")
        if instrument in actual:
            raise ValueError(f"duplicate position for {instrument}")
        actual[instrument] = _integer(quantity_value, "position quantity", positive=True)

    expected_positions = {key: value for key, value in sorted(expected.items()) if value != 0}
    actual_positions = dict(sorted(actual.items()))
    keys = expected_positions.keys() | actual_positions.keys()
    differences = {
        key: expected_positions.get(key, 0) - actual_positions.get(key, 0)
        for key in sorted(keys)
        if expected_positions.get(key, 0) != actual_positions.get(key, 0)
    }
    actual_cash = _integer(cash_balance_cents, "cash_balance_cents")
    if actual_cash < 0:
        raise ValueError("cash_balance_cents must be non-negative")
    cash_difference = expected_cash - actual_cash
    return ReconciliationResult(
        is_reconciled=cash_difference == 0 and not differences,
        expected_cash_cents=expected_cash,
        actual_cash_cents=actual_cash,
        expected_positions=expected_positions,
        actual_positions=actual_positions,
        cash_difference_cents=cash_difference,
        position_differences=differences,
    )
