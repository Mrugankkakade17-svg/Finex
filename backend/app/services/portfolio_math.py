from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Tuple

from app.schemas.portfolio import AllocationItem, HoldingResponse

_CENT = Decimal("0.01")
_ZERO = Decimal("0.00")
_HUNDRED = Decimal("100")


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _cent(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def calculate_holding_metrics(
    holding_raw: Dict[str, Any],
    current_price: float,
    portfolio_total_value: float = 0.0,
) -> HoldingResponse:
    quantity = _decimal(holding_raw["quantity"])
    average_cost = _decimal(holding_raw["avg_buy_price"])
    price = _cent(_decimal(current_price))

    total_cost = _cent(quantity * average_cost)
    current_value = _cent(quantity * price)
    gain_loss = current_value - total_cost
    gain_loss_pct = _cent(_HUNDRED * gain_loss / total_cost) if total_cost > 0 else _ZERO
    weight_pct = (
        _cent(_HUNDRED * current_value / _decimal(portfolio_total_value))
        if portfolio_total_value > 0
        else _ZERO
    )

    created_at = holding_raw.get("created_at")
    if not isinstance(created_at, datetime):
        created_at = None
    updated_at = holding_raw.get("updated_at")
    if not isinstance(updated_at, datetime):
        updated_at = None

    return HoldingResponse(
        holding_id=str(holding_raw["holding_id"]),
        portfolio_id=str(holding_raw["portfolio_id"]),
        user_id=str(holding_raw["user_id"]),
        symbol=str(holding_raw["symbol"]).strip().upper(),
        asset_class=holding_raw.get("asset_class", "EQUITY"),
        sector=holding_raw.get("sector") or "General",
        quantity=float(quantity),
        avg_buy_price=float(average_cost),
        current_price=float(price),
        current_value=float(current_value),
        total_cost=float(total_cost),
        unrealized_gain_loss=float(gain_loss),
        unrealized_gain_loss_pct=float(gain_loss_pct),
        weight_pct=float(weight_pct),
        created_at=created_at,
        updated_at=updated_at,
    )


def compute_portfolio_valuations(
    raw_holdings: List[Dict[str, Any]],
    quotes_map: Dict[str, float],
) -> Tuple[float, float, float, float, List[HoldingResponse]]:
    if not raw_holdings:
        return 0.0, 0.0, 0.0, 0.0, []

    total_value = _ZERO
    total_cost = _ZERO
    for holding in raw_holdings:
        symbol = str(holding["symbol"]).strip().upper()
        price = _decimal(quotes_map.get(symbol, float(holding["avg_buy_price"])))
        quantity = _decimal(holding["quantity"])
        average_cost = _decimal(holding["avg_buy_price"])
        total_value += _cent(quantity * price)
        total_cost += _cent(quantity * average_cost)

    gain_loss = total_value - total_cost
    gain_loss_pct = _cent(_HUNDRED * gain_loss / total_cost) if total_cost > 0 else _ZERO

    evaluated_holdings = [
        calculate_holding_metrics(
            holding,
            current_price=quotes_map.get(
                str(holding["symbol"]).strip().upper(),
                float(holding["avg_buy_price"]),
            ),
            portfolio_total_value=float(total_value),
        )
        for holding in raw_holdings
    ]

    return (
        float(total_value),
        float(total_cost),
        float(gain_loss),
        float(gain_loss_pct),
        evaluated_holdings,
    )


def calculate_allocations(
    holdings: List[HoldingResponse],
    group_by: str,
    total_value: float,
) -> List[AllocationItem]:
    if not holdings or total_value <= 0:
        return []

    groups: Dict[str, Decimal] = {}
    total = _decimal(total_value)
    for holding in holdings:
        if group_by == "asset_class":
            key = (
                holding.asset_class.value
                if hasattr(holding.asset_class, "value")
                else str(holding.asset_class)
            )
        else:
            key = str(holding.sector or "General")
        groups[key] = groups.get(key, _ZERO) + _decimal(holding.current_value)

    allocations = [
        AllocationItem(
            category=category,
            value=float(_cent(value)),
            percentage=float(_cent(_HUNDRED * value / total)),
        )
        for category, value in groups.items()
    ]
    allocations.sort(key=lambda item: item.value, reverse=True)
    return allocations
