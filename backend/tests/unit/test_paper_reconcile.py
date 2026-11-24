from random import Random

import pytest

from app.services.paper_reconcile import reconcile_paper_account


def test_reconciles_empty_account_at_initial_cash() -> None:
    result = reconcile_paper_account([], {}, 1_000_000, initial_cash_cents=1_000_000)
    assert result.is_reconciled
    assert result.expected_positions == result.actual_positions == {}


def test_reconciles_buy_and_sell_using_fee_adjusted_order_cash_deltas() -> None:
    orders = [
        {
            "side": "BUY",
            "instrument_id": "SYN:AAPL",
            "quantity": 10,
            "cash_delta_cents": -200_100,
        },
        {
            "side": "SELL",
            "instrument_id": "SYN:AAPL",
            "quantity": 3,
            "cash_delta_cents": 59_950,
        },
    ]
    result = reconcile_paper_account(orders, {"SYN:AAPL": 7}, 859_850, initial_cash_cents=1_000_000)
    assert result.is_reconciled
    assert result.expected_cash_cents == 859_850
    assert result.expected_positions == {"SYN:AAPL": 7}


def test_deterministic_random_order_sequence_reconciles() -> None:
    rng = Random(4105)
    orders: list[dict[str, object]] = []
    quantities: dict[str, int] = {}
    cash = 5_000_000
    symbols = ("SYN:AAPL", "SYN:MSFT", "SYN:BND")
    for _ in range(250):
        symbol = rng.choice(symbols)
        if quantities.get(symbol, 0) == 0 or rng.random() < 0.6:
            quantity = rng.randint(1, 5)
            cash_delta = -quantity * rng.randint(100, 20_000)
            quantities[symbol] = quantities.get(symbol, 0) + quantity
            side = "BUY"
        else:
            quantity = rng.randint(1, quantities[symbol])
            cash_delta = quantity * rng.randint(100, 20_000)
            quantities[symbol] -= quantity
            side = "SELL"
        cash += cash_delta
        orders.append(
            {
                "side": side,
                "instrument_id": symbol,
                "quantity": quantity,
                "cash_delta_cents": cash_delta,
            }
        )
    positions = {symbol: qty for symbol, qty in quantities.items() if qty}
    result = reconcile_paper_account(orders, positions, cash, initial_cash_cents=5_000_000)
    assert result.is_reconciled


def test_reports_cash_and_each_position_mismatch() -> None:
    result = reconcile_paper_account(
        [{"side": "BUY", "instrument_id": "SYN:AAPL", "quantity": 2, "cash_delta_cents": -2000}],
        {"SYN:AAPL": 1, "SYN:MSFT": 4},
        97_999,
        initial_cash_cents=100_000,
    )
    assert not result.is_reconciled
    assert result.cash_difference_cents == 1
    assert result.position_differences == {"SYN:AAPL": 1, "SYN:MSFT": -4}


def test_buy_then_sell_to_zero_has_no_expected_position() -> None:
    result = reconcile_paper_account(
        [
            {"side": "BUY", "instrument_id": "SYN:AAPL", "quantity": 1, "cash_delta_cents": -100},
            {"side": "SELL", "instrument_id": "SYN:AAPL", "quantity": 1, "cash_delta_cents": 100},
        ],
        {},
        10_000,
        initial_cash_cents=10_000,
    )
    assert result.is_reconciled
    assert result.expected_positions == {}


@pytest.mark.parametrize(
    ("order", "positions", "balance"),
    [
        ({"side": "BUY", "instrument_id": "X", "quantity": 0, "cash_delta_cents": -1}, {}, 0),
        ({"side": "BUY", "instrument_id": "X", "quantity": 1, "cash_delta_cents": -1.0}, {}, 0),
        ({"side": "BUY", "instrument_id": "X", "quantity": 1, "cash_delta_cents": -1}, {"X": 0}, 0),
        ({"side": "BUY", "instrument_id": " X", "quantity": 1, "cash_delta_cents": -1}, {}, 0),
        ({"side": "HOLD", "instrument_id": "X", "quantity": 1, "cash_delta_cents": 0}, {}, 0),
    ],
)
def test_rejects_invalid_or_ambiguous_inputs(order, positions, balance) -> None:
    with pytest.raises(ValueError):
        reconcile_paper_account([order], positions, balance, initial_cash_cents=0)


def test_rejects_duplicate_position_rows_and_missing_order_fields() -> None:
    with pytest.raises(ValueError, match="duplicate position"):
        reconcile_paper_account(
            [], [{"instrument_id": "X", "quantity": 1}] * 2, 0, initial_cash_cents=0
        )
    with pytest.raises(ValueError, match="side"):
        reconcile_paper_account([{"quantity": 1}], {}, 0, initial_cash_cents=0)


def test_rejects_non_integer_balances() -> None:
    with pytest.raises(ValueError, match="initial_cash_cents"):
        reconcile_paper_account([], {}, 0, initial_cash_cents=100.0)
    with pytest.raises(ValueError, match="cash_balance_cents"):
        reconcile_paper_account([], {}, True, initial_cash_cents=0)
