"""Dated foreign-exchange series and auditable currency valuation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable


def _currency(value: str) -> str:
    code = value.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError("Currency must be a three-letter ISO code.")
    return code


def _positive_rate(value: Decimal | str | int | float) -> Decimal:
    try:
        rate = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("FX rate must be a finite positive decimal.") from exc
    if not rate.is_finite() or rate <= 0:
        raise ValueError("FX rate must be a finite positive decimal.")
    return rate


@dataclass(frozen=True, slots=True)
class FxRate:
    """A labelled quote: one unit of base currency expressed in quote currency."""

    rate_id: str
    base_currency: str
    quote_currency: str
    rate: Decimal
    as_of: date
    source: str
    freshness: str = "END_OF_DAY"

    def __post_init__(self) -> None:
        if not self.rate_id.strip() or not self.source.strip():
            raise ValueError("FX rate requires a rate ID and source label.")
        base, quote = _currency(self.base_currency), _currency(self.quote_currency)
        if base == quote:
            raise ValueError("Base and quote currencies must differ.")
        if not isinstance(self.as_of, date) or isinstance(self.as_of, datetime):
            raise ValueError("FX as_of must be a date-only value.")
        if not self.freshness.strip():
            raise ValueError("FX freshness label cannot be empty.")
        object.__setattr__(self, "base_currency", base)
        object.__setattr__(self, "quote_currency", quote)
        object.__setattr__(self, "rate", _positive_rate(self.rate))
        object.__setattr__(self, "freshness", self.freshness.strip().upper())


@dataclass(frozen=True, slots=True)
class FxConversion:
    """Converted amount together with the exact rate lineage used."""

    amount: Decimal
    source_currency: str
    target_currency: str
    rate: Decimal
    rate_id: str
    source: str
    as_of: date
    freshness: str
    inverted: bool = False


class FxSeries:
    """An immutable-in-use collection of dated rates with no implicit live fetch."""

    def __init__(self, rates: Iterable[FxRate] = ()) -> None:
        self._rates: dict[tuple[str, str], list[FxRate]] = {}
        ids: set[str] = set()
        for item in rates:
            if not isinstance(item, FxRate):
                raise TypeError("FX series entries must be FxRate values.")
            if item.rate_id in ids:
                raise ValueError(f"Duplicate FX rate ID: {item.rate_id}")
            ids.add(item.rate_id)
            self._rates.setdefault((item.base_currency, item.quote_currency), []).append(item)
        for values in self._rates.values():
            values.sort(key=lambda item: (item.as_of, item.rate_id))

    def get_rate(self, base_currency: str, quote_currency: str, on: date) -> FxRate:
        """Return the latest direct rate on or before the requested valuation date."""
        base, quote = _currency(base_currency), _currency(quote_currency)
        if not isinstance(on, date) or isinstance(on, datetime):
            raise ValueError("Valuation date must be a date-only value.")
        if base == quote:
            raise ValueError("Identical currencies do not have a stored FX rate.")
        candidates = [r for r in self._rates.get((base, quote), ()) if r.as_of <= on]
        if not candidates:
            raise LookupError(f"No {base}/{quote} FX rate is available on or before {on}.")
        return candidates[-1]

    def rates(self, base_currency: str, quote_currency: str) -> tuple[FxRate, ...]:
        """Return the dated direct series in ascending date order."""
        return tuple(self._rates.get((_currency(base_currency), _currency(quote_currency)), ()))

    def convert(
        self,
        amount: Decimal | str | int | float,
        source_currency: str,
        target_currency: str,
        on: date,
    ) -> FxConversion:
        """Convert using direct rate, or its mathematical inverse, preserving labels."""
        source, target = _currency(source_currency), _currency(target_currency)
        if not isinstance(on, date) or isinstance(on, datetime):
            raise ValueError("Valuation date must be a date-only value.")
        try:
            value = amount if isinstance(amount, Decimal) else Decimal(str(amount))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Amount must be a finite decimal.") from exc
        if not value.is_finite():
            raise ValueError("Amount must be a finite decimal.")
        if source == target:
            return FxConversion(
                value, source, target, Decimal("1"), "identity", "identity", on, "IDENTITY"
            )
        inverted = False
        try:
            rate_record = self.get_rate(source, target, on)
            conversion_rate = rate_record.rate
        except LookupError:
            try:
                rate_record = self.get_rate(target, source, on)
            except LookupError as inverse_error:
                raise LookupError(
                    f"No {source}/{target} FX rate is available on or before {on}."
                ) from inverse_error
            conversion_rate = Decimal("1") / rate_record.rate
            inverted = True
        return FxConversion(
            amount=value * conversion_rate,
            source_currency=source,
            target_currency=target,
            rate=conversion_rate,
            rate_id=rate_record.rate_id,
            source=rate_record.source,
            as_of=rate_record.as_of,
            freshness=rate_record.freshness,
            inverted=inverted,
        )


class FxService:
    """Small facade for FX lookup and INR/USD valuation over an injected series."""

    def __init__(self, series: FxSeries) -> None:
        self.series = series

    def get_rate(self, base_currency: str, quote_currency: str, on: date) -> FxRate:
        return self.series.get_rate(base_currency, quote_currency, on)

    def convert(
        self,
        amount: Decimal | str | int | float,
        source_currency: str,
        target_currency: str,
        on: date,
    ) -> FxConversion:
        return self.series.convert(amount, source_currency, target_currency, on)

    def value_inr(
        self, amount: Decimal | str | int | float, currency: str, on: date
    ) -> FxConversion:
        return self.convert(amount, currency, "INR", on)

    def value_usd(
        self, amount: Decimal | str | int | float, currency: str, on: date
    ) -> FxConversion:
        return self.convert(amount, currency, "USD", on)
