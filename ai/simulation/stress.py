"""Historical stress and drawdown scenario engine for FinEx.

Task: S4-MI02
Sprint: Sprint 4 — Simulated Orders, Cash Ledger & Goals
Prerequisite: S2-PA03 (Historical OHLCV and market calendar)

This module provides a pure, deterministic, non-networked analytical engine
for calculating cumulative returns, peak-to-trough drawdowns, maximum drawdown
(MDD), recovery trajectories, and historical stress scenario impacts from
stored historical market price observations (e.g., S2-PA03 daily OHLCV candles).

Financial & Mathematical Conventions:
-------------------------------------
1. Chronological Ordering:
   Observations are sorted strictly by date ascending: t_0 < t_1 < ... < t_n.
2. Period Return:
   r_t = (P_t - P_{t-1}) / P_{t-1}
3. Cumulative Return:
   R_cum = (P_{end} - P_{start}) / P_{start}
   R_cum_pct = R_cum * 100
4. Running Peak:
   M_t = max_{0 <= s <= t} (P_s)
5. Drawdown at Observation t:
   DD_t = (P_t - M_t) / M_t  (where DD_t <= 0)
   DD_pct_t = DD_t * 100
6. Maximum Drawdown (MDD):
   MDD = min_{0 <= t <= T} (DD_t)  (expressed as negative fraction, e.g. -0.35)
   MDD_pct = MDD * 100             (expressed as negative percentage, e.g. -35.0%)
7. Peak Date:
   The date on or before the MDD trough where the running peak was established:
   t_peak = max { s <= t_trough | P_s = M_{t_trough} }
8. Trough Date:
   The date at which the maximum drawdown occurs:
   t_trough = argmin_{0 <= t <= T} (DD_t)
9. Recovery Date:
   The earliest date strictly following t_trough where price reaches or exceeds P_peak:
   t_recovery = min { s > t_trough | P_s >= P_peak }
   If P_s < P_peak for all s > t_trough, recovered = False and t_recovery = None.
10. Durations:
    - peak_to_trough_days: Calendar days between peak_date and trough_date.
    - recovery_days: Calendar days between trough_date and recovery_date (None if unrecovered).
    - peak_to_recovery_days: Calendar days between peak and recovery (None if unrecovered).
    - calendar_days: Calendar days between start_date and end_date.
    - trading_days: Count of valid trading observation points in the window.

Operational Boundaries:
-----------------------
- No network requests, API calls, or database operations.
- Pure calculation layer consuming verified historical observations.
- Decimal precision used internally to avoid floating-point representation drift.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ZERO = Decimal("0.0")
_HUNDRED = Decimal("100.0")


class StressEngineError(Exception):
    """Base domain exception for stress engine operations."""


class InsufficientDataError(StressEngineError):
    """Raised when historical observations are empty or insufficient."""


class InvalidObservationError(StressEngineError):
    """Raised when an observation has invalid, negative, zero, or non-finite values."""


class DuplicateObservationError(StressEngineError):
    """Raised when duplicate conflicting observations are encountered for the same date."""


class ScenarioWindowError(StressEngineError):
    """Raised when a scenario window is invalid or outside the observation boundaries."""


@dataclass(frozen=True)
class PriceObservation:
    """A validated historical price observation point."""

    date: date
    price: Decimal
    volume: int | None = None
    symbol: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.date, date):
            raise InvalidObservationError(
                f"Observation date must be a datetime.date, got {type(self.date)}"
            )
        if not isinstance(self.price, Decimal):
            object.__setattr__(self, "price", Decimal(str(self.price)))
        if self.price <= 0:
            raise InvalidObservationError(
                f"Observation price must be strictly positive, got {self.price}"
            )
        if self.price.is_nan() or self.price.is_infinite():
            raise InvalidObservationError("Observation price must be finite")


class DrawdownPoint(BaseModel):
    """An individual time-step within a drawdown series."""

    model_config = ConfigDict(extra="forbid")

    date: date
    price: Decimal
    running_peak: Decimal
    drawdown: Decimal = Field(description="Drawdown fraction relative to peak, <= 0.0")
    drawdown_pct: Decimal = Field(description="Drawdown percentage relative to peak, <= 0.0%")
    period_return: Decimal | None = Field(
        default=None, description="Periodic return from prior bar"
    )
    period_return_pct: Decimal | None = Field(
        default=None, description="Periodic return percentage"
    )


class ScenarioWindow(BaseModel):
    """Definition of a historical stress scenario window."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date
    description: str | None = None

    @model_validator(mode="after")
    def validate_window_order(self) -> ScenarioWindow:
        if self.end_date < self.start_date:
            raise ScenarioWindowError(
                f"Scenario end_date ({self.end_date}) cannot precede start_date ({self.start_date})"
            )
        return self


class StressScenarioResult(BaseModel):
    """Authoritative result envelope for a historical stress and drawdown evaluation."""

    model_config = ConfigDict(extra="forbid")

    scenario_name: str
    symbol: str | None = None
    exchange: str | None = None
    start_date: date
    end_date: date
    trading_days: int = Field(ge=1, description="Number of historical trading day observations")
    calendar_days: int = Field(ge=0, description="Total calendar days in the scenario window")
    start_price: Decimal
    end_price: Decimal
    cumulative_return: Decimal = Field(
        description="Fractional return across window: (P_end - P_start) / P_start"
    )
    cumulative_return_pct: Decimal = Field(description="Percentage return across window")
    max_drawdown: Decimal = Field(
        le=0, description="Maximum peak-to-trough decline as negative fraction"
    )
    max_drawdown_pct: Decimal = Field(
        le=0, description="Maximum peak-to-trough decline as negative percentage"
    )
    peak_date: date = Field(description="Date on which the preceding high peak occurred")
    peak_price: Decimal = Field(gt=0, description="Price at the preceding high peak")
    trough_date: date = Field(description="Date on which the maximum drawdown trough occurred")
    trough_price: Decimal = Field(gt=0, description="Price at the maximum drawdown trough")
    recovery_date: date | None = Field(
        default=None, description="First date price recovered to prior peak"
    )
    recovered: bool = Field(description="Whether price recovered to prior peak within the window")
    peak_to_trough_days: int = Field(ge=0, description="Calendar days from peak to trough")
    recovery_days: int | None = Field(
        default=None, ge=0, description="Calendar days from trough to recovery"
    )
    peak_to_recovery_days: int | None = Field(
        default=None, ge=0, description="Calendar days from peak to recovery"
    )
    drawdown_series: list[DrawdownPoint] | None = Field(
        default=None, description="Optional full time-series of running drawdowns"
    )

    def to_summary_dict(self) -> dict[str, Any]:
        """Return a float-serialized summary dict suitable for JSON APIs."""
        return {
            "scenario_name": self.scenario_name,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "trading_days": self.trading_days,
            "calendar_days": self.calendar_days,
            "start_price": float(self.start_price),
            "end_price": float(self.end_price),
            "cumulative_return": float(self.cumulative_return),
            "cumulative_return_pct": float(self.cumulative_return_pct),
            "max_drawdown": float(self.max_drawdown),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "peak_date": self.peak_date.isoformat(),
            "peak_price": float(self.peak_price),
            "trough_date": self.trough_date.isoformat(),
            "trough_price": float(self.trough_price),
            "recovery_date": self.recovery_date.isoformat() if self.recovery_date else None,
            "recovered": self.recovered,
            "peak_to_trough_days": self.peak_to_trough_days,
            "recovery_days": self.recovery_days,
            "peak_to_recovery_days": self.peak_to_recovery_days,
        }


# Canonical Reference Historical Stress Windows (Documented Benchmark Scenarios)
# Note: These represent standard financial industry benchmark crisis windows.
# Official project-specific golden scenario sets require product-owner confirmation.
HISTORICAL_SCENARIOS: dict[str, ScenarioWindow] = {
    "GFC_2008": ScenarioWindow(
        name="Global Financial Crisis (2007-2009)",
        start_date=date(2007, 10, 9),
        end_date=date(2009, 3, 9),
        description=(
            "Peak-to-trough collapse during the 2007-2009 global banking and subprime crisis."
        ),
    ),
    "COVID_CRASH_2020": ScenarioWindow(
        name="COVID-19 Market Shock (Feb-Mar 2020)",
        start_date=date(2020, 2, 19),
        end_date=date(2020, 3, 23),
        description=("Rapid global market liquidation triggered by the emergence of COVID-19."),
    ),
    "TECH_BUBBLE_2000": ScenarioWindow(
        name="Dot-Com Technology Crash (2000-2002)",
        start_date=date(2000, 3, 24),
        end_date=date(2002, 10, 9),
        description=(
            "Multi-year deflation of technology equities following the 1990s tech bubble."
        ),
    ),
    "RATE_SHOCK_2022": ScenarioWindow(
        name="2022 Global Rate Hike & Inflation Shock",
        start_date=date(2022, 1, 3),
        end_date=date(2022, 10, 12),
        description=(
            "Global equity and bond drawdown driven by aggressive interest rate tightening."
        ),
    ),
    "DEMONETIZATION_2016": ScenarioWindow(
        name="Indian Market Demonetization Shock (2016)",
        start_date=date(2016, 11, 8),
        end_date=date(2016, 12, 26),
        description=(
            "Short-term liquidity and currency demonetization shock in Indian markets (NSE/BSE)."
        ),
    ),
    "ILFS_CRISIS_2018": ScenarioWindow(
        name="Indian NBFC Liquidity Stress (IL&FS 2018)",
        start_date=date(2018, 8, 28),
        end_date=date(2018, 10, 26),
        description=(
            "Credit and liquidity shock following defaults in the Indian shadow banking sector."
        ),
    ),
}


def _parse_date(value: Any) -> date:
    """Parse a date, datetime, or ISO string to a datetime.date."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        cleaned = value.strip().replace("Z", "")
        # Handle full ISO timestamps e.g. '2026-11-02T09:15:00'
        if "T" in cleaned:
            cleaned = cleaned.split("T")[0]
        elif " " in cleaned:
            cleaned = cleaned.split(" ")[0]
        try:
            return date.fromisoformat(cleaned)
        except (ValueError, TypeError) as exc:
            raise InvalidObservationError(
                f"Cannot parse date from string {value!r}: {exc}"
            ) from exc
    raise InvalidObservationError(f"Cannot parse date from value {value!r} of type {type(value)}")


def _parse_decimal(value: Any) -> Decimal:
    """Parse a number or string into a Decimal with validation."""
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, float, str)):
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                raise InvalidObservationError("Float value is NaN or Infinite")
        try:
            dec = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise InvalidObservationError(f"Cannot parse Decimal from {value!r}") from exc
    else:
        raise InvalidObservationError(f"Unsupported price type: {type(value)}")

    if dec.is_nan() or dec.is_infinite():
        raise InvalidObservationError("Price value is NaN or Infinite")
    if dec <= _ZERO:
        raise InvalidObservationError(f"Price must be strictly positive (> 0), got {dec}")
    return dec


def normalize_observations(
    raw_data: Sequence[Any],
    price_field: str = "close",
    date_field: str = "timestamp",
    sort_chronological: bool = True,
) -> list[PriceObservation]:
    """Convert and validate raw records into a chronological sequence of PriceObservation.

    Compatible with:
    - S2-PA03 Candle models / dicts (`timestamp`, `close`)
    - Tuples of `(date, price)`
    - Direct `PriceObservation` instances
    """
    if not raw_data:
        raise InsufficientDataError("Historical observations series is empty")

    observations: list[PriceObservation] = []
    seen_dates: dict[date, Decimal] = {}

    for idx, item in enumerate(raw_data):
        obs_date: date
        obs_price: Decimal
        obs_volume: int | None = None
        obs_symbol: str | None = None

        if isinstance(item, PriceObservation):
            obs_date = item.date
            obs_price = item.price
            obs_volume = item.volume
            obs_symbol = item.symbol
        elif isinstance(item, tuple) and len(item) >= 2:
            obs_date = _parse_date(item[0])
            obs_price = _parse_decimal(item[1])
            if len(item) >= 3 and item[2] is not None:
                obs_volume = int(item[2])
        elif isinstance(item, dict):
            # Check for date in date_field, 'timestamp', 'price_date', or 'date'
            raw_date = (
                item.get(date_field)
                or item.get("timestamp")
                or item.get("price_date")
                or item.get("date")
            )
            if raw_date is None:
                raise InvalidObservationError(f"Record at index {idx} missing date/timestamp field")
            obs_date = _parse_date(raw_date)

            # Check for price in price_field, 'close', 'close_price', or 'price'
            raw_price = (
                item.get(price_field)
                or item.get("close")
                or item.get("close_price")
                or item.get("price")
            )
            if raw_price is None:
                raise InvalidObservationError(f"Record at index {idx} missing price/close field")
            obs_price = _parse_decimal(raw_price)

            raw_vol = item.get("volume")
            if raw_vol is not None:
                obs_volume = int(raw_vol)
            obs_symbol = item.get("symbol")
        elif hasattr(item, "timestamp") and hasattr(item, "close"):
            # S2-PA03 Candle Pydantic model
            obs_date = _parse_date(getattr(item, "timestamp"))
            obs_price = _parse_decimal(getattr(item, "close"))
            raw_vol = getattr(item, "volume", None)
            if raw_vol is not None:
                obs_volume = int(raw_vol)
        else:
            raise InvalidObservationError(
                f"Unsupported observation format at index {idx}: {type(item)}"
            )

        # Handle duplicate dates
        if obs_date in seen_dates:
            prior_price = seen_dates[obs_date]
            if prior_price != obs_price:
                raise DuplicateObservationError(
                    f"Conflicting duplicate observation for date {obs_date}: "
                    f"prior price {prior_price} != new price {obs_price}"
                )
            # If prices match exactly on duplicate date, skip duplicate to preserve determinism
            continue

        seen_dates[obs_date] = obs_price
        observations.append(
            PriceObservation(
                date=obs_date,
                price=obs_price,
                volume=obs_volume,
                symbol=obs_symbol,
            )
        )

    if len(observations) < 1:
        raise InsufficientDataError("No valid observations extracted from input series")

    if sort_chronological:
        observations.sort(key=lambda obs: obs.date)

    return observations


def calculate_drawdown_series(
    observations: Sequence[PriceObservation],
) -> list[DrawdownPoint]:
    """Calculate the running peak and drawdown point at each historical observation step."""
    if not observations:
        raise InsufficientDataError("Observations series is empty")

    running_peak = observations[0].price
    series: list[DrawdownPoint] = []
    prior_price: Decimal | None = None

    for obs in observations:
        price = obs.price
        if price > running_peak:
            running_peak = price

        drawdown = (price - running_peak) / running_peak
        drawdown_pct = drawdown * _HUNDRED

        period_return: Decimal | None = None
        period_return_pct: Decimal | None = None
        if prior_price is not None:
            period_return = (price - prior_price) / prior_price
            period_return_pct = period_return * _HUNDRED

        series.append(
            DrawdownPoint(
                date=obs.date,
                price=price,
                running_peak=running_peak,
                drawdown=drawdown,
                drawdown_pct=drawdown_pct,
                period_return=period_return,
                period_return_pct=period_return_pct,
            )
        )
        prior_price = price

    return series


def calculate_stress_metrics(
    observations: Sequence[PriceObservation],
    scenario_name: str = "custom",
    symbol: str | None = None,
    exchange: str | None = None,
    include_series: bool = False,
) -> StressScenarioResult:
    """Calculate comprehensive historical stress and drawdown metrics."""
    if not observations:
        raise InsufficientDataError("Cannot calculate stress metrics on empty observations")
    if len(observations) < 2:
        raise InsufficientDataError(
            f"At least 2 historical observations are required to calculate returns and "
            f"drawdown, got {len(observations)}"
        )

    start_obs = observations[0]
    end_obs = observations[-1]
    start_price = start_obs.price
    end_price = end_obs.price
    start_date = start_obs.date
    end_date = end_obs.date

    if end_date < start_date:
        raise ScenarioWindowError(
            f"Observations out of order: end date {end_date} precedes start date {start_date}"
        )

    # 1. Cumulative return across the window
    cumulative_return = (end_price - start_price) / start_price
    cumulative_return_pct = cumulative_return * _HUNDRED

    # 2. Step-by-step running peak and drawdown tracking
    running_peak = start_price
    running_peak_date = start_date

    max_drawdown = _ZERO
    peak_date = start_date
    peak_price = start_price
    trough_date = start_date
    trough_price = start_price
    trough_idx = 0

    series: list[DrawdownPoint] = []
    prior_price: Decimal | None = None

    for idx, obs in enumerate(observations):
        price = obs.price

        if price > running_peak:
            running_peak = price
            running_peak_date = obs.date

        drawdown = (price - running_peak) / running_peak
        drawdown_pct = drawdown * _HUNDRED

        period_return: Decimal | None = None
        period_return_pct: Decimal | None = None
        if prior_price is not None:
            period_return = (price - prior_price) / prior_price
            period_return_pct = period_return * _HUNDRED

        if include_series:
            series.append(
                DrawdownPoint(
                    date=obs.date,
                    price=price,
                    running_peak=running_peak,
                    drawdown=drawdown,
                    drawdown_pct=drawdown_pct,
                    period_return=period_return,
                    period_return_pct=period_return_pct,
                )
            )

        # Check for new maximum drawdown (most negative drawdown)
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            peak_date = running_peak_date
            peak_price = running_peak
            trough_date = obs.date
            trough_price = price
            trough_idx = idx

        prior_price = price

    max_drawdown_pct = max_drawdown * _HUNDRED

    # 3. Handle zero drawdown edge case (monotonic gain or flat)
    if max_drawdown == _ZERO:
        # No drop occurred. Peak is the final highest observation; trough equals peak.
        peak_date = running_peak_date
        peak_price = running_peak
        trough_date = peak_date
        trough_price = peak_price
        recovered = True
        recovery_date: date | None = peak_date
        peak_to_trough_days = 0
        recovery_days: int | None = 0
        peak_to_recovery_days: int | None = 0
    else:
        # 4. Search for recovery strictly after trough_idx
        recovered = False
        recovery_date = None
        for obs in observations[trough_idx + 1 :]:
            if obs.price >= peak_price:
                recovered = True
                recovery_date = obs.date
                break

        peak_to_trough_days = (trough_date - peak_date).days
        recovery_days = (recovery_date - trough_date).days if recovery_date else None
        peak_to_recovery_days = (recovery_date - peak_date).days if recovery_date else None

    calendar_days = (end_date - start_date).days

    return StressScenarioResult(
        scenario_name=scenario_name,
        symbol=symbol or start_obs.symbol,
        exchange=exchange,
        start_date=start_date,
        end_date=end_date,
        trading_days=len(observations),
        calendar_days=calendar_days,
        start_price=start_price,
        end_price=end_price,
        cumulative_return=cumulative_return,
        cumulative_return_pct=cumulative_return_pct,
        max_drawdown=max_drawdown,
        max_drawdown_pct=max_drawdown_pct,
        peak_date=peak_date,
        peak_price=peak_price,
        trough_date=trough_date,
        trough_price=trough_price,
        recovery_date=recovery_date,
        recovered=recovered,
        peak_to_trough_days=peak_to_trough_days,
        recovery_days=recovery_days,
        peak_to_recovery_days=peak_to_recovery_days,
        drawdown_series=series if include_series else None,
    )


def evaluate_scenario_window(
    raw_data: Sequence[Any],
    scenario: ScenarioWindow | str,
    symbol: str | None = None,
    exchange: str | None = None,
    allow_partial_window: bool = False,
    include_series: bool = False,
    min_observations: int = 2,
) -> StressScenarioResult:
    """Evaluate stress and drawdown for a specific date window against stored history."""
    if isinstance(scenario, str):
        if scenario not in HISTORICAL_SCENARIOS:
            known = list(HISTORICAL_SCENARIOS.keys())
            raise ScenarioWindowError(
                f"Unknown scenario key '{scenario}'. Known scenarios: {known}"
            )
        window = HISTORICAL_SCENARIOS[scenario]
    elif isinstance(scenario, ScenarioWindow):
        window = scenario
    else:
        raise ScenarioWindowError(
            f"Expected ScenarioWindow or scenario key string, got {type(scenario)}"
        )

    all_obs = normalize_observations(raw_data)

    # Slice observations falling within [window.start_date, window.end_date]
    windowed = [obs for obs in all_obs if window.start_date <= obs.date <= window.end_date]

    if len(windowed) < min_observations:
        raise InsufficientDataError(
            f"Scenario '{window.name}' [{window.start_date} to {window.end_date}] contains only "
            f"{len(windowed)} observation(s); minimum required is {min_observations}"
        )

    if not allow_partial_window:
        earliest_date = windowed[0].date
        latest_date = windowed[-1].date
        # Check if the available history reasonably spans the requested scenario
        if earliest_date > window.start_date and (earliest_date - window.start_date).days > 7:
            raise InsufficientDataError(
                f"History for scenario '{window.name}' starts on {earliest_date}, "
                f"which is after requested start date {window.start_date}"
            )
        if latest_date < window.end_date and (window.end_date - latest_date).days > 7:
            raise InsufficientDataError(
                f"History for scenario '{window.name}' ends on {latest_date}, "
                f"which is before requested end date {window.end_date}"
            )

    return calculate_stress_metrics(
        observations=windowed,
        scenario_name=window.name,
        symbol=symbol,
        exchange=exchange,
        include_series=include_series,
    )


def evaluate_from_candles(
    candles: Sequence[dict[str, Any] | Any],
    scenario_name: str = "custom",
    start_date: date | None = None,
    end_date: date | None = None,
    symbol: str | None = None,
    exchange: str | None = None,
    include_series: bool = False,
) -> StressScenarioResult:
    """Convenience adapter to evaluate stress metrics directly from S2-PA03 candle responses.

    Directly consumes the items list from S2-PA03 GET /api/v1/market/instruments/{symbol}/ohlcv.
    """
    obs = normalize_observations(candles, price_field="close", date_field="timestamp")

    if start_date or end_date:
        filtered = [
            o
            for o in obs
            if (start_date is None or o.date >= start_date)
            and (end_date is None or o.date <= end_date)
        ]
        if len(filtered) < 2:
            raise InsufficientDataError(
                f"Filtered candle range [{start_date} to {end_date}] contains "
                f"insufficient observations ({len(filtered)})"
            )
        obs = filtered

    return calculate_stress_metrics(
        observations=obs,
        scenario_name=scenario_name,
        symbol=symbol,
        exchange=exchange,
        include_series=include_series,
    )


class HistoricalStressEngine:
    """State-free, object-oriented facade for the FinEx historical stress simulation engine."""

    @staticmethod
    def normalize(
        raw_data: Sequence[Any],
        price_field: str = "close",
        date_field: str = "timestamp",
    ) -> list[PriceObservation]:
        """Normalize raw price observations."""
        return normalize_observations(raw_data, price_field=price_field, date_field=date_field)

    @staticmethod
    def calculate_drawdown_series(
        observations: Sequence[PriceObservation],
    ) -> list[DrawdownPoint]:
        """Calculate step-by-step drawdown points."""
        return calculate_drawdown_series(observations)

    @staticmethod
    def calculate(
        observations: Sequence[PriceObservation],
        scenario_name: str = "custom",
        symbol: str | None = None,
        exchange: str | None = None,
        include_series: bool = False,
    ) -> StressScenarioResult:
        """Calculate complete stress and drawdown metrics."""
        return calculate_stress_metrics(
            observations=observations,
            scenario_name=scenario_name,
            symbol=symbol,
            exchange=exchange,
            include_series=include_series,
        )

    @staticmethod
    def evaluate_scenario(
        raw_data: Sequence[Any],
        scenario: ScenarioWindow | str,
        symbol: str | None = None,
        exchange: str | None = None,
        allow_partial_window: bool = False,
        include_series: bool = False,
    ) -> StressScenarioResult:
        """Evaluate a named or defined scenario window against historical observations."""
        return evaluate_scenario_window(
            raw_data=raw_data,
            scenario=scenario,
            symbol=symbol,
            exchange=exchange,
            allow_partial_window=allow_partial_window,
            include_series=include_series,
        )

    @staticmethod
    def from_s2_candles(
        candles: Sequence[dict[str, Any] | Any],
        scenario_name: str = "custom",
        start_date: date | None = None,
        end_date: date | None = None,
        symbol: str | None = None,
        exchange: str | None = None,
        include_series: bool = False,
    ) -> StressScenarioResult:
        """Evaluate stress metrics from S2-PA03 OHLCV candle responses."""
        return evaluate_from_candles(
            candles=candles,
            scenario_name=scenario_name,
            start_date=start_date,
            end_date=end_date,
            symbol=symbol,
            exchange=exchange,
            include_series=include_series,
        )
