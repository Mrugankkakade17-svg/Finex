"""Deterministic paper order rules and eligible-quote enforcement."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, time, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.config.settings import Settings
from app.core.exceptions import FinExException
from app.repositories.paper_trading_repository import (
    PaperOrderRecord,
    PaperTradingConflict,
    PaperTradingStoreUnavailable,
    PostgresPaperTradingRepository,
)
from app.schemas.market import DataFreshness, MarketQuoteResponse
from app.schemas.paper import PaperOrderRequest

_CENT = Decimal("0.01")
_PRICE_UNIT = Decimal("0.000001")
_SESSION = {
    "NYSE": ("America/New_York", time(9, 30), time(16, 0)),
    "NASDAQ": ("America/New_York", time(9, 30), time(16, 0)),
}
ELIGIBLE_FRESHNESS = {DataFreshness.LIVE, DataFreshness.DELAYED, DataFreshness.CACHED}


class PaperQuoteProvider(Protocol):
    async def get_quote_with_freshness(self, symbol: str) -> MarketQuoteResponse: ...


class PaperTradingServiceError(FinExException):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message=message, error_code=code, status_code=status_code)


class PaperTradingService:
    def __init__(
        self,
        repository: PostgresPaperTradingRepository,
        quotes: PaperQuoteProvider,
        settings: Settings,
        *,
        clock=lambda: datetime.now(timezone.utc),
        market_open=None,
    ) -> None:
        self.repository = repository
        self.quotes = quotes
        self.settings = settings
        self.clock = clock
        self.market_open = market_open or is_market_open

    @staticmethod
    def fingerprint(order: PaperOrderRequest) -> str:
        canonical = json.dumps(
            {
                "instrument_id": order.instrument_id.strip().upper(),
                "exchange": order.exchange,
                "side": order.side,
                "quantity": order.quantity,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def submit_order(
        self, user_id: str, order: PaperOrderRequest
    ) -> tuple[PaperOrderRecord, bool]:
        fingerprint = self.fingerprint(order)
        existing = self.repository.find_order(user_id, order.idempotency_key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise PaperTradingServiceError(
                    "IDEMPOTENCY_KEY_REUSED",
                    "The idempotency key was already used for a different order.",
                    409,
                )
            return existing, False

        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise PaperTradingServiceError(
                "INVALID_CLOCK", "Paper order execution requires an aware clock.", 500
            )
        if not self.market_open(order.exchange, now):
            raise PaperTradingServiceError(
                "MARKET_CLOSED", "Paper orders are accepted only during regular market hours.", 409
            )

        symbol = order.instrument_id.strip().upper()
        try:
            quote = await self.quotes.get_quote_with_freshness(symbol)
        except Exception as exc:
            raise PaperTradingServiceError(
                "QUOTE_UNAVAILABLE", "An eligible market quote is unavailable.", 503
            ) from exc
        self._validate_quote(quote)
        if quote.currency.upper() != "USD":
            raise PaperTradingServiceError(
                "QUOTE_CURRENCY_UNSUPPORTED", "Paper accounts accept USD quotes only.", 422
            )

        assert quote.price is not None
        price = Decimal(str(quote.price)).quantize(_PRICE_UNIT, rounding=ROUND_HALF_UP)
        if price <= 0:
            raise PaperTradingServiceError(
                "QUOTE_INELIGIBLE", "The market quote is below the supported price precision.", 503
            )
        notional = (price * order.quantity).quantize(_CENT, rounding=ROUND_HALF_UP)
        notional_cents = int(notional * 100)
        fee_cents = int(
            (Decimal(notional_cents * self.settings.paper_trading_fee_bps) / 10_000).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        cash_delta = (
            -(notional_cents + fee_cents) if order.side == "BUY" else notional_cents - fee_cents
        )
        if cash_delta == 0:
            raise PaperTradingServiceError(
                "ORDER_VALUE_TOO_SMALL", "Order proceeds after fees must be at least one cent.", 422
            )

        record = PaperOrderRecord(
            order_id=f"paper-order-{uuid4().hex}",
            account_id=f"paper-{uuid4().hex}",
            user_id=user_id,
            idempotency_key=order.idempotency_key,
            request_fingerprint=fingerprint,
            instrument_id=symbol,
            exchange=order.exchange,
            side=order.side,
            quantity=order.quantity,
            executed_price=price,
            notional_cents=notional_cents,
            fee_cents=fee_cents,
            cash_delta_cents=cash_delta,
            balance_after_cents=0,
            quote_freshness=quote.freshness.value,
            quote_as_of=quote.as_of,
            created_at=now,
        )
        initial_cash_cents = int(self.settings.paper_trading_initial_cash.quantize(_CENT) * 100)
        try:
            return self.repository.execute_order(record, initial_cash_cents=initial_cash_cents)
        except PaperTradingConflict as exc:
            raise PaperTradingServiceError(exc.code, str(exc), 409) from exc
        except PaperTradingStoreUnavailable as exc:
            raise PaperTradingServiceError("PAPER_STORE_UNAVAILABLE", str(exc), 503) from exc

    def get_account(self, user_id: str) -> dict[str, object]:
        try:
            snapshot = self.repository.account_snapshot(
                user_id,
                initial_cash_cents=int(self.settings.paper_trading_initial_cash * 100),
            )
        except PaperTradingStoreUnavailable as exc:
            raise PaperTradingServiceError("PAPER_STORE_UNAVAILABLE", str(exc), 503) from exc
        cash = (Decimal(snapshot["cash_balance_cents"]) / 100).quantize(_CENT)
        positions: list[dict[str, object]] = []
        portfolio_value = Decimal("0.00")
        for raw in snapshot["positions"]:
            row = raw
            quantity = int(row["quantity"])
            average_cost = Decimal(row["average_cost"])
            last_price = Decimal(row["last_price"])
            market_value = (last_price * quantity).quantize(_CENT, rounding=ROUND_HALF_UP)
            portfolio_value += market_value
            positions.append(
                {
                    "instrument_id": str(row["instrument_id"]),
                    "exchange": str(row["exchange"]),
                    "quantity": quantity,
                    "average_cost": average_cost,
                    "last_price": last_price,
                    "market_value": market_value,
                    "unrealized_pnl": (market_value - average_cost * quantity).quantize(
                        _CENT, rounding=ROUND_HALF_UP
                    ),
                }
            )
        recent_orders = [self.order_dict(record) for record in snapshot["recent_orders"]]
        return {
            "account_id": str(snapshot["account_id"]),
            "cash_balance": cash,
            "portfolio_value": portfolio_value.quantize(_CENT),
            "total_equity": (cash + portfolio_value).quantize(_CENT),
            "positions": positions,
            "recent_orders": recent_orders,
        }

    def list_orders(self, user_id: str, *, limit: int) -> list[dict[str, object]]:
        try:
            rows = self.repository.list_orders(user_id, limit=limit)
        except PaperTradingStoreUnavailable as exc:
            raise PaperTradingServiceError("PAPER_STORE_UNAVAILABLE", str(exc), 503) from exc
        return [self.order_dict(row) for row in rows]

    @staticmethod
    def order_dict(record: PaperOrderRecord) -> dict[str, object]:
        return {
            "order_id": record.order_id,
            "instrument_id": record.instrument_id,
            "exchange": record.exchange,
            "side": record.side,
            "quantity": record.quantity,
            "executed_price": record.executed_price,
            "notional": (Decimal(record.notional_cents) / 100).quantize(_CENT),
            "fee": (Decimal(record.fee_cents) / 100).quantize(_CENT),
            "cash_delta": (Decimal(record.cash_delta_cents) / 100).quantize(_CENT),
            "status": "FILLED",
            "quote_freshness": record.quote_freshness,
            "quote_as_of": record.quote_as_of,
            "created_at": record.created_at.isoformat(),
        }

    @staticmethod
    def _validate_quote(quote: MarketQuoteResponse) -> None:
        if (
            quote.freshness not in ELIGIBLE_FRESHNESS
            or quote.is_stale
            or quote.price is None
            or not math.isfinite(quote.price)
            or quote.price <= 0
        ):
            raise PaperTradingServiceError(
                "QUOTE_INELIGIBLE",
                "The market quote is stale or unavailable; no fill was created.",
                503,
            )

    @staticmethod
    def market_is_open(exchange: str, now: datetime) -> bool:
        return is_market_open(exchange, now)


def is_market_open(exchange: str, now: datetime) -> bool:
    """Check regular weekday session hours; exchange holidays are not in this calendar."""
    schedule = _SESSION.get(exchange)
    if schedule is None or now.tzinfo is None or now.utcoffset() is None:
        return False
    zone_name, opening, closing = schedule
    local = now.astimezone(ZoneInfo(zone_name))
    return local.weekday() < 5 and opening <= local.time().replace(tzinfo=None) < closing
