"""Deterministic in-memory repository and quote source for paper API tests."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from decimal import Decimal
from threading import Lock

from app.repositories.paper_trading_repository import (
    PaperOrderRecord,
    PaperTradingConflict,
)
from app.schemas.market import DataFreshness, MarketQuoteResponse


class MemoryPaperTradingRepository:
    def __init__(self) -> None:
        self.orders: dict[tuple[str, str], PaperOrderRecord] = {}
        self.cash: dict[str, int] = {}
        self.positions: dict[tuple[str, str, str], dict[str, object]] = {}
        self._lock = Lock()

    def find_order(self, user_id: str, idempotency_key: str) -> PaperOrderRecord | None:
        return self.orders.get((user_id, idempotency_key))

    def execute_order(self, order: PaperOrderRecord, *, initial_cash_cents: int):
        with self._lock:
            key = (order.user_id, order.idempotency_key)
            existing = self.orders.get(key)
            if existing is not None:
                if existing.request_fingerprint != order.request_fingerprint:
                    raise PaperTradingConflict("IDEMPOTENCY_KEY_REUSED", "key reused")
                return existing, False

            balance = self.cash.setdefault(order.user_id, initial_cash_cents)
            after = balance + order.cash_delta_cents
            if after < 0:
                raise PaperTradingConflict("INSUFFICIENT_CASH", "insufficient cash")
            pos_key = (order.user_id, order.instrument_id, order.exchange)
            position = self.positions.get(pos_key)
            old_quantity = int(position["quantity"]) if position else 0
            if order.side == "SELL" and old_quantity < order.quantity:
                raise PaperTradingConflict("INSUFFICIENT_POSITION", "insufficient shares")

            if order.side == "BUY":
                quantity = old_quantity + order.quantity
                old_cost = Decimal(position["average_cost"]) if position else Decimal(0)
                average_cost = (
                    old_cost * old_quantity + Decimal(order.notional_cents + order.fee_cents) / 100
                ) / quantity
                self.positions[pos_key] = {
                    "quantity": quantity,
                    "average_cost": average_cost,
                    "last_price": order.executed_price,
                }
            else:
                remaining = old_quantity - order.quantity
                if remaining:
                    assert position is not None
                    position["quantity"] = remaining
                    position["last_price"] = order.executed_price
                else:
                    self.positions.pop(pos_key)

            self.cash[order.user_id] = after
            saved = replace(order, balance_after_cents=after)
            self.orders[key] = saved
            return saved, True

    def account_snapshot(self, user_id: str, *, initial_cash_cents: int):
        balance = self.cash.setdefault(user_id, initial_cash_cents)
        return {
            "account_id": f"paper-{user_id}",
            "cash_balance_cents": balance,
            "positions": [
                {
                    "instrument_id": instrument,
                    "exchange": exchange,
                    **position,
                }
                for (owner, instrument, exchange), position in self.positions.items()
                if owner == user_id
            ],
            "recent_orders": sorted(
                [order for (owner, _), order in self.orders.items() if owner == user_id],
                key=lambda order: order.created_at,
                reverse=True,
            )[:10],
        }

    def list_orders(self, user_id: str, *, limit: int):
        return sorted(
            [order for (owner, _), order in self.orders.items() if owner == user_id],
            key=lambda order: order.created_at,
            reverse=True,
        )[:limit]


class FixedPaperQuotes:
    def __init__(
        self,
        *,
        price: float | None = 100.0,
        freshness: DataFreshness = DataFreshness.DELAYED,
        stale: bool = False,
    ) -> None:
        self.price = price
        self.freshness = freshness
        self.stale = stale
        self.calls: list[str] = []

    async def get_quote_with_freshness(self, symbol: str) -> MarketQuoteResponse:
        await asyncio.sleep(0)
        self.calls.append(symbol)
        return MarketQuoteResponse(
            symbol=symbol,
            price=self.price,
            currency="USD",
            source="fixture-test",
            as_of="2026-11-23T15:00:00Z",
            fetched_at="2026-11-23T15:00:00Z",
            freshness=self.freshness,
            is_stale=self.stale,
        )
