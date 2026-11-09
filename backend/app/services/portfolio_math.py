from datetime import datetime
from typing import Any, Dict, List, Tuple

from app.schemas.portfolio import AllocationItem, HoldingResponse


def calculate_holding_metrics(
    holding_raw: Dict[str, Any],
    current_price: float,
    portfolio_total_value: float = 0.0,
) -> HoldingResponse:
    """
    Computes holding cost, current market value, gain/loss ($ and %), and portfolio weight %.
    """
    quantity = float(holding_raw["quantity"])
    avg_buy_price = float(holding_raw["avg_buy_price"])

    total_cost = round(quantity * avg_buy_price, 2)
    current_value = round(quantity * current_price, 2)
    unrealized_gain_loss = round(current_value - total_cost, 2)

    if total_cost > 0:
        unrealized_gain_loss_pct = round((unrealized_gain_loss / total_cost) * 100, 2)
    else:
        unrealized_gain_loss_pct = 0.0

    if portfolio_total_value > 0:
        weight_pct = round((current_value / portfolio_total_value) * 100, 2)
    else:
        weight_pct = 0.0

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
        quantity=quantity,
        avg_buy_price=avg_buy_price,
        current_price=round(current_price, 2),
        current_value=current_value,
        total_cost=total_cost,
        unrealized_gain_loss=unrealized_gain_loss,
        unrealized_gain_loss_pct=unrealized_gain_loss_pct,
        weight_pct=weight_pct,
        created_at=created_at,
        updated_at=updated_at,
    )


def compute_portfolio_valuations(
    raw_holdings: List[Dict[str, Any]],
    quotes_map: Dict[str, float],
) -> Tuple[float, float, float, float, List[HoldingResponse]]:
    """
    Calculates overall portfolio total value, total cost, total gain/loss ($ and %),
    and returns fully evaluated holding responses with accurate portfolio weight percentages.
    """
    if not raw_holdings:
        return 0.0, 0.0, 0.0, 0.0, []

    total_value = 0.0
    total_cost = 0.0

    # First pass: calculate total portfolio value and cost
    for h in raw_holdings:
        sym = str(h["symbol"]).strip().upper()
        price = quotes_map.get(sym, float(h["avg_buy_price"]))
        qty = float(h["quantity"])
        avg_price = float(h["avg_buy_price"])

        total_value += qty * price
        total_cost += qty * avg_price

    total_value = round(total_value, 2)
    total_cost = round(total_cost, 2)
    total_gain_loss = round(total_value - total_cost, 2)

    if total_cost > 0:
        total_gain_loss_pct = round((total_gain_loss / total_cost) * 100, 2)
    else:
        total_gain_loss_pct = 0.0

    # Second pass: calculate per-holding metrics with weight percentages
    evaluated_holdings: List[HoldingResponse] = []
    for h in raw_holdings:
        sym = str(h["symbol"]).strip().upper()
        price = quotes_map.get(sym, float(h["avg_buy_price"]))
        metric = calculate_holding_metrics(
            h,
            current_price=price,
            portfolio_total_value=total_value,
        )
        evaluated_holdings.append(metric)

    return (
        total_value,
        total_cost,
        total_gain_loss,
        total_gain_loss_pct,
        evaluated_holdings,
    )


def calculate_allocations(
    holdings: List[HoldingResponse],
    group_by: str,
    total_value: float,
) -> List[AllocationItem]:
    """
    Groups holding values by asset_class or sector and computes percentage breakdown.
    Ensures rounded percentages sum to 100.0% if total value > 0.
    """
    if not holdings or total_value <= 0:
        return []

    groups: Dict[str, float] = {}
    for h in holdings:
        if group_by == "asset_class":
            key = h.asset_class.value if hasattr(h.asset_class, "value") else str(h.asset_class)
        else:
            key = str(h.sector or "General")

        groups[key] = groups.get(key, 0.0) + h.current_value

    allocations: List[AllocationItem] = []
    for cat, val in groups.items():
        val_rounded = round(val, 2)
        pct = round((val / total_value) * 100, 2)
        allocations.append(AllocationItem(category=cat, value=val_rounded, percentage=pct))

    # Sort descending by value
    allocations.sort(key=lambda x: x.value, reverse=True)
    return allocations
