"""Lazy bounded public synthetic-quote cache, never owned persistence or a feed."""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from threading import Lock
from typing import Literal

from app.domain.local_application import Clock
from app.domain.local_portfolio import LocalPortfolioQuoteRecord, LocalQuoteUnavailable
from app.ports.adapters.synthetic_local_portfolio import validate_quote_snapshot
from app.ports.local_portfolio_quotes import LocalPortfolioQuotePort
from app.schemas.local_foundation import SCOPE, MarketQuoteData
from app.services.local_authorization import utc_now


@dataclass(frozen=True)
class QuoteEntry:
    quote: LocalPortfolioQuoteRecord
    fetched_at: datetime
    expires_at: datetime


class LocalFoundationQuotes:
    def __init__(self, provider: LocalPortfolioQuotePort, clock: Clock) -> None:
        self._provider = provider
        self._clock = clock
        self._entries: OrderedDict[str, QuoteEntry] = OrderedDict()
        self._lock = Lock()
        self._last_clock: datetime | None = None

    def quote(self, instrument_id: str) -> MarketQuoteData:
        with self._lock:
            try:
                now = utc_now(self._clock)
                expires = now + timedelta(seconds=60)
                if self._last_clock is not None and now < self._last_clock:
                    raise ValueError("Invalid synthetic cache time")
            except (ValueError, OverflowError):
                raise LocalQuoteUnavailable() from None
            # Clock observation does not renew a successful retrieval. Invalid
            # timing above changes neither this observation nor any entry.
            self._last_clock = now
            previous = self._entries.get(instrument_id)
            if previous is not None:
                self._entries.move_to_end(instrument_id)
                if now < previous.expires_at:
                    return self._response(instrument_id, previous, now, failed=False)
            try:
                snapshot = validate_quote_snapshot(
                    self._provider.snapshot((instrument_id,)), (instrument_id,)
                )
                entry = QuoteEntry(snapshot.quotes[0], now, expires)
            except Exception:
                return self._response(instrument_id, previous, now, failed=True)
            self._entries[instrument_id] = entry
            self._entries.move_to_end(instrument_id)
            while len(self._entries) > 4:
                self._entries.popitem(last=False)
            return self._response(instrument_id, entry, now, failed=False)

    @staticmethod
    def _response(
        instrument_id: str, entry: QuoteEntry | None, now: datetime, *, failed: bool
    ) -> MarketQuoteData:
        status: Literal["CACHED", "STALE", "UNAVAILABLE"] = "UNAVAILABLE"
        reason: (
            Literal[
                "SYNTHETIC_PROVIDER_STALE",
                "SYNTHETIC_QUOTE_UNAVAILABLE",
                "SYNTHETIC_PROVIDER_UNAVAILABLE",
            ]
            | None
        ) = "SYNTHETIC_PROVIDER_UNAVAILABLE"
        price: str | None = None
        as_of: Literal["2026-01-01T00:00:00Z"] | None = None
        if entry is not None and not failed:
            if entry.quote.data_status == "CACHED":
                status, reason, price, as_of = (
                    "CACHED",
                    None,
                    entry.quote.unit_price,
                    "2026-01-01T00:00:00Z",
                )
            else:
                reason = "SYNTHETIC_QUOTE_UNAVAILABLE"
        elif (
            entry is not None
            and entry.quote.unit_price is not None
            and now - entry.fetched_at < timedelta(seconds=300)
        ):
            status, reason, price, as_of = (
                "STALE",
                "SYNTHETIC_PROVIDER_STALE",
                entry.quote.unit_price,
                "2026-01-01T00:00:00Z",
            )
        return MarketQuoteData(
            **SCOPE,
            catalog_version="synthetic_catalog.v1",
            quote_snapshot_version="synthetic_quotes.v1",
            source="finex.synthetic.portfolio",
            source_type="SYNTHETIC",
            fixture_as_of="2026-01-01T00:00:00Z",
            instrument_id=instrument_id,
            currency="USD",
            status=status,
            unit_price=price,
            quote_as_of=as_of,
            fetched_at=entry.fetched_at.isoformat() if entry is not None else None,
            cache_expires_at=entry.expires_at.isoformat() if entry is not None else None,
            reason=reason,
        )
