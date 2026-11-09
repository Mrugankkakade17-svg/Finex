"""
Router for Sprint 4: Simulated Order Execution, Cash Ledger, and Positions.
Ensures deterministic execution, idempotency, no broker APIs, atomic ledger tracking.
"""

from decimal import Decimal
from typing import Dict, List
from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Depends
from app.core.responses import APIResponse
from app.schemas.sprint4_paper_goals import (
    PaperOrderRequest,
    PaperOrderResponse,
    PaperAccountSummary,
    PaperPosition,
    CashLedgerEntry,
)

router = APIRouter(prefix="/api/v1/paper-trading", tags=["Sprint 4 - Paper Trading"])

# In-memory store for paper trading demo/local mode
_processed_idempotency_keys: Dict[str, PaperOrderResponse] = {}
_cash_balance: Decimal = Decimal("50000.00")
_ledger: List[CashLedgerEntry] = [
    CashLedgerEntry(
        entry_id="ledger-init-001",
        timestamp=datetime.now(timezone.utc).isoformat(),
        entry_type="DEPOSIT",
        amount=Decimal("50000.00"),
        balance_after=Decimal("50000.00"),
        description="Initial virtual simulated cash deposit",
    )
]
_positions: Dict[str, PaperPosition] = {
    "AAPL": PaperPosition(
        instrument_id="AAPL",
        quantity=20,
        average_cost=Decimal("180.00"),
        current_price=Decimal("195.50"),
        market_value=Decimal("3910.00"),
        unrealized_pnl=Decimal("310.00"),
        unrealized_pnl_pct=Decimal("8.61"),
    )
}

# Fixed reference prices for simulation
MOCK_PRICES: Dict[str, Decimal] = {
    "AAPL": Decimal("195.50"),
    "MSFT": Decimal("420.00"),
    "GOOGL": Decimal("175.25"),
    "SPY": Decimal("545.00"),
    "QQQ": Decimal("480.00"),
}


@router.get("/account", summary="Get paper trading account summary and positions")
def get_paper_account(request: Request):
    global _cash_balance, _positions, _ledger
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    
    portfolio_val = sum((p.market_value for p in _positions.values()), Decimal("0.00"))
    summary = PaperAccountSummary(
        account_id="paper-acc-demo-user",
        cash_balance=_cash_balance,
        portfolio_value=portfolio_val,
        total_equity=_cash_balance + portfolio_val,
        positions=list(_positions.values()),
        recent_transactions=_ledger[-10:],
        currency="USD",
        is_simulated=True,
    )
    return APIResponse.success(
        message="Simulated account retrieved successfully",
        data=summary.model_dump(),
        correlation_id=correlation_id,
    )


@router.post("/orders", summary="Submit simulated buy or sell order idempotently")
def submit_paper_order(order: PaperOrderRequest, request: Request):
    global _cash_balance, _positions, _ledger
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))

    # Idempotency check: repeated keys return identical existing order
    if order.idempotency_key in _processed_idempotency_keys:
        return APIResponse.success(
            message="Order already processed (idempotent replay)",
            data=_processed_idempotency_keys[order.idempotency_key].model_dump(),
            correlation_id=correlation_id,
        )

    symbol = order.instrument_id.upper()
    price = MOCK_PRICES.get(symbol, Decimal("150.00"))
    total_cost = price * Decimal(order.quantity)

    if order.side == "BUY":
        if total_cost > _cash_balance:
            raise HTTPException(status_code=400, detail="Insufficient simulated cash balance.")
        
        # Execute BUY
        _cash_balance -= total_cost
        if symbol in _positions:
            old_pos = _positions[symbol]
            new_qty = old_pos.quantity + order.quantity
            total_invested = (old_pos.average_cost * old_pos.quantity) + total_cost
            avg_cost = total_invested / new_qty
            mkt_val = price * new_qty
            pnl = mkt_val - total_invested
            pnl_pct = (pnl / total_invested) * 100
            _positions[symbol] = PaperPosition(
                instrument_id=symbol,
                quantity=new_qty,
                average_cost=avg_cost.quantize(Decimal("0.01")),
                current_price=price,
                market_value=mkt_val.quantize(Decimal("0.01")),
                unrealized_pnl=pnl.quantize(Decimal("0.01")),
                unrealized_pnl_pct=pnl_pct.quantize(Decimal("0.01")),
            )
        else:
            _positions[symbol] = PaperPosition(
                instrument_id=symbol,
                quantity=order.quantity,
                average_cost=price,
                current_price=price,
                market_value=total_cost,
                unrealized_pnl=Decimal("0.00"),
                unrealized_pnl_pct=Decimal("0.00"),
            )

        ledger_entry = CashLedgerEntry(
            entry_id=f"ledger-{uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_type="BUY",
            amount=-total_cost,
            balance_after=_cash_balance,
            description=f"Simulated BUY {order.quantity} {symbol} @ ${price}",
        )
        _ledger.append(ledger_entry)

    elif order.side == "SELL":
        if symbol not in _positions or _positions[symbol].quantity < order.quantity:
            raise HTTPException(status_code=400, detail="Insufficient position quantity to sell.")

        old_pos = _positions[symbol]
        new_qty = old_pos.quantity - order.quantity
        proceeds = price * Decimal(order.quantity)
        _cash_balance += proceeds

        if new_qty == 0:
            del _positions[symbol]
        else:
            mkt_val = price * new_qty
            total_invested = old_pos.average_cost * new_qty
            pnl = mkt_val - total_invested
            pnl_pct = (pnl / total_invested) * 100
            _positions[symbol] = PaperPosition(
                instrument_id=symbol,
                quantity=new_qty,
                average_cost=old_pos.average_cost,
                current_price=price,
                market_value=mkt_val.quantize(Decimal("0.01")),
                unrealized_pnl=pnl.quantize(Decimal("0.01")),
                unrealized_pnl_pct=pnl_pct.quantize(Decimal("0.01")),
            )

        ledger_entry = CashLedgerEntry(
            entry_id=f"ledger-{uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_type="SELL",
            amount=proceeds,
            balance_after=_cash_balance,
            description=f"Simulated SELL {order.quantity} {symbol} @ ${price}",
        )
        _ledger.append(ledger_entry)

    res = PaperOrderResponse(
        order_id=f"ord-{uuid4().hex[:8]}",
        instrument_id=symbol,
        side=order.side,
        quantity=order.quantity,
        executed_price=price,
        total_amount=total_cost,
        status="FILLED",
        timestamp=datetime.now(timezone.utc).isoformat(),
        simulation_notice="SIMULATION ONLY: No real money or broker execution involved.",
    )
    _processed_idempotency_keys[order.idempotency_key] = res

    return APIResponse.success(
        message="Simulated order executed successfully",
        data=res.model_dump(),
        correlation_id=correlation_id,
    )


@router.post("/reset", summary="Reset simulated paper portfolio and ledger")
def reset_paper_account(request: Request):
    global _cash_balance, _positions, _ledger, _processed_idempotency_keys
    correlation_id = getattr(request.state, "correlation_id", str(uuid4()))
    
    _cash_balance = Decimal("50000.00")
    _positions.clear()
    _processed_idempotency_keys.clear()
    _ledger = [
        CashLedgerEntry(
            entry_id=f"ledger-{uuid4().hex[:8]}",
            timestamp=datetime.now(timezone.utc).isoformat(),
            entry_type="RESET",
            amount=Decimal("50000.00"),
            balance_after=Decimal("50000.00"),
            description="Simulated account reset to initial starting balance",
        )
    ]
    return APIResponse.success(
        message="Paper trading account reset successfully",
        data={"status": "RESET_COMPLETE", "balance": "50000.00"},
        correlation_id=correlation_id,
    )
