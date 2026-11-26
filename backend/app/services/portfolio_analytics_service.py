"""Deterministic portfolio return and risk analytics.

Price histories are ordered oldest to newest and must share the same observation
calendar. This module is deliberately independent of a market-data vendor; until
the OHLCV history port is available, callers pass no history and performance
metrics are reported as INSUFFICIENT_DATA.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from app.config.database import execute_query

_PERIODS_PER_YEAR = 252
_MIN_RETURNS = 2
_Z_SCORES = {0.95: 1.6448536269514722, 0.99: 2.3263478740408408}


def fetch_close_price_history(
    symbols: Sequence[str],
    *,
    currency: str,
    start_date: date,
    end_date: date,
) -> dict[str, list[dict[str, object]]]:
    """Load daily closes through the canonical S2-PA03 market warehouse table."""
    normalized_currency = currency.strip().upper()
    if normalized_currency == "INR":
        exchanges = "('NSE', 'BSE')"
        preferred_exchange = "CASE upper(i.exchange) WHEN 'NSE' THEN 0 ELSE 1 END"
    elif normalized_currency == "USD":
        exchanges = "('NASDAQ', 'NYSE')"
        preferred_exchange = "CASE upper(i.exchange) WHEN 'NASDAQ' THEN 0 ELSE 1 END"
    else:
        return {}

    history: dict[str, list[dict[str, object]]] = {}
    for symbol in sorted({item.strip().upper() for item in symbols if item.strip()}):
        rows = execute_query(
            f"""WITH selected_instrument AS (
                    SELECT i.instrument_id
                    FROM finex_dev.market.instruments i
                    WHERE upper(i.symbol) = :symbol AND upper(i.exchange) IN {exchanges}
                    ORDER BY {preferred_exchange}
                    LIMIT 1
                )
                SELECT p.price_date AS timestamp, p.close_price AS close
                FROM finex_dev.market.prices p
                JOIN selected_instrument i ON i.instrument_id = p.instrument_id
                WHERE p.price_date >= :start_date AND p.price_date <= :end_date
                ORDER BY p.price_date ASC""",
            {"symbol": symbol, "start_date": start_date, "end_date": end_date},
        )
        history[symbol] = [
            {
                "timestamp": row["timestamp"],
                "close": _finite_number(row["close"], field="close", positive=True),
            }
            for row in rows
        ]
    return history


def align_close_price_history(
    history: Mapping[str, Sequence[Mapping[str, object]]],
    symbols: Sequence[str],
    benchmark_symbol: str,
) -> tuple[dict[str, list[float]], list[float] | None]:
    """Align position and benchmark closes on their common observation dates."""
    requested = [symbol.strip().upper() for symbol in symbols]
    series = {
        symbol: {
            str(row["timestamp"])[:10]: _finite_number(
                row["close"], field=f"{symbol} close", positive=True
            )
            for row in history.get(symbol, ())
        }
        for symbol in requested
    }
    if not requested or any(not series[symbol] for symbol in requested):
        return {}, None
    common_dates = set.intersection(*(set(series[symbol]) for symbol in requested))
    benchmark = benchmark_symbol.strip().upper()
    benchmark_series = {
        str(row["timestamp"])[:10]: _finite_number(
            row["close"], field=f"{benchmark} close", positive=True
        )
        for row in history.get(benchmark, ())
    }
    if benchmark_series:
        common_dates &= set(benchmark_series)
    ordered_dates = sorted(common_dates)
    if len(ordered_dates) < _MIN_RETURNS + 1:
        return {}, None
    aligned = {symbol: [series[symbol][day] for day in ordered_dates] for symbol in requested}
    benchmark_prices = (
        [benchmark_series[day] for day in ordered_dates] if benchmark_series else None
    )
    return aligned, benchmark_prices


def _finite_number(value: object, *, field: str, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} must be a finite number.") from exc
    if not math.isfinite(number) or (positive and number <= 0):
        raise ValueError(f"{field} must be a finite {'positive ' if positive else ''}number.")
    return number


def _rounded(value: float | None, places: int = 8) -> float | None:
    if value is None:
        return None
    result = round(value, places)
    return 0.0 if result == 0 else result


def calculate_portfolio_analytics(
    *,
    portfolio_id: str,
    holdings: Sequence[Mapping[str, Any]],
    price_history: Mapping[str, Sequence[float]] | None = None,
    benchmark_prices: Sequence[float] | None = None,
    benchmark_symbol: str = "SPY",
    risk_free_rate_annual: float = 0.0,
    risk_free_rate_source: str = "FinEx configured default",
    risk_free_rate_as_of: str = "2026-01-01",
    confidence_level: float = 0.95,
    top_n: int = 5,
) -> dict[str, Any]:
    """Calculate concentration and performance measures from an owned snapshot.

    Historical VaR is the empirical loss quantile (linear interpolation); the
    parametric VaR assumes normally distributed daily returns. Both are one-day
    portfolio-value losses at the requested confidence level.
    """
    if not portfolio_id:
        raise ValueError("portfolio_id is required.")
    if isinstance(top_n, bool) or not isinstance(top_n, int) or not 1 <= top_n <= 100:
        raise ValueError("top_n must be an integer from 1 to 100.")
    if confidence_level not in _Z_SCORES:
        raise ValueError("confidence_level must be 0.95 or 0.99.")
    risk_free_rate = _finite_number(risk_free_rate_annual, field="risk_free_rate_annual")
    if risk_free_rate <= -1:
        raise ValueError("risk_free_rate_annual must be greater than -1.")
    if not risk_free_rate_source.strip() or not risk_free_rate_as_of.strip():
        raise ValueError("Risk-free rate source and as-of date are required.")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    total_value = 0.0
    for holding in holdings:
        symbol = str(holding.get("symbol", "")).strip().upper()
        if not symbol or symbol in seen:
            raise ValueError("Holding symbols must be non-empty and unique.")
        seen.add(symbol)
        quantity = _finite_number(holding.get("quantity"), field=f"{symbol}.quantity")
        value = _finite_number(holding.get("current_value"), field=f"{symbol}.current_value")
        if quantity <= 0 or value < 0:
            raise ValueError("Holding quantity must be positive and current value non-negative.")
        total_value += value
        normalized.append({"symbol": symbol, "quantity": quantity, "current_value": value})

    hhi: float | None = None
    if total_value > 0:
        hhi = sum((row["current_value"] / total_value) ** 2 for row in normalized)
    ranked = sorted(normalized, key=lambda row: (-row["current_value"], row["symbol"]))
    top = [
        {
            "symbol": row["symbol"],
            "current_value": _rounded(row["current_value"], 2),
            "weight": _rounded(row["current_value"] / total_value if total_value else None),
        }
        for row in ranked[:top_n]
    ]

    portfolio_returns: list[float] = []
    benchmark_returns: list[float] = []
    history = {str(key).strip().upper(): value for key, value in (price_history or {}).items()}
    sufficient = bool(normalized) and all(row["symbol"] in history for row in normalized)
    if sufficient:
        series = {
            symbol: [_finite_number(p, field=f"{symbol} price", positive=True) for p in points]
            for symbol, points in history.items()
            if symbol in seen
        }
        lengths = {len(points) for points in series.values()}
        sufficient = len(lengths) == 1 and next(iter(lengths), 0) >= _MIN_RETURNS + 1
        if sufficient:
            values = [
                sum(row["quantity"] * series[row["symbol"]][idx] for row in normalized)
                for idx in range(next(iter(lengths)))
            ]
            sufficient = all(value > 0 for value in values)
            if sufficient:
                portfolio_returns = [b / a - 1 for a, b in zip(values, values[1:])]

    if benchmark_prices is not None:
        prices = [
            _finite_number(p, field=f"{benchmark_symbol} price", positive=True)
            for p in benchmark_prices
        ]
        if len(prices) == len(portfolio_returns) + 1 and len(prices) >= 2:
            benchmark_returns = [b / a - 1 for a, b in zip(prices, prices[1:])]

    status = (
        "COMPLETE" if sufficient and len(portfolio_returns) >= _MIN_RETURNS else "INSUFFICIENT_DATA"
    )
    mean_return = volatility = sharpe = beta = historical_var = parametric_var = None
    cumulative_return = annualized_return = None
    if status == "COMPLETE":
        count = len(portfolio_returns)
        mean_return = sum(portfolio_returns) / count
        variance = sum((r - mean_return) ** 2 for r in portfolio_returns) / (count - 1)
        volatility = math.sqrt(variance)
        daily_risk_free = (1 + risk_free_rate) ** (1 / _PERIODS_PER_YEAR) - 1
        sharpe = (
            (mean_return - daily_risk_free) / volatility * math.sqrt(_PERIODS_PER_YEAR)
            if volatility
            else None
        )
        cumulative_return = math.prod(1 + r for r in portfolio_returns) - 1
        annualized_return = (1 + cumulative_return) ** (_PERIODS_PER_YEAR / count) - 1
        if len(benchmark_returns) == count:
            benchmark_mean = sum(benchmark_returns) / count
            benchmark_variance = sum((r - benchmark_mean) ** 2 for r in benchmark_returns) / (
                count - 1
            )
            if benchmark_variance:
                covariance = sum(
                    (a - mean_return) * (b - benchmark_mean)
                    for a, b in zip(portfolio_returns, benchmark_returns)
                ) / (count - 1)
                beta = covariance / benchmark_variance
        losses = sorted(-r for r in portfolio_returns)
        location = confidence_level * (count - 1)
        lower = math.floor(location)
        fraction = location - lower
        historical_daily_loss = (
            losses[lower] * (1 - fraction) + losses[min(lower + 1, count - 1)] * fraction
        )
        historical_var = max(0.0, historical_daily_loss) * total_value
        parametric_var = (
            max(0.0, -mean_return + _Z_SCORES[confidence_level] * volatility) * total_value
        )

    return {
        "portfolio_id": portfolio_id,
        "status": status,
        "observation_count": len(portfolio_returns),
        "benchmark_symbol": benchmark_symbol.strip().upper(),
        "confidence_level": confidence_level,
        "risk_free_rate": {
            "annual_rate": _rounded(risk_free_rate),
            "source": risk_free_rate_source,
            "as_of": risk_free_rate_as_of,
        },
        "returns": {
            "cumulative": _rounded(cumulative_return),
            "annualized": _rounded(annualized_return),
            "daily_mean": _rounded(mean_return),
        },
        "annualized_volatility": _rounded(volatility * math.sqrt(_PERIODS_PER_YEAR))
        if volatility is not None
        else None,
        "sharpe_ratio": _rounded(sharpe),
        "beta": _rounded(beta),
        "value_at_risk": {
            "historical": _rounded(historical_var, 2),
            "parametric": _rounded(parametric_var, 2),
            "confidence_level": confidence_level,
            "horizon_days": 1,
        },
        "current_value": _rounded(total_value, 2),
        "hhi": _rounded(hhi, 6),
        "top_holdings": top,
        "limitations": [
            "Historical metrics are unavailable until aligned daily close-price "
            "history is supplied."
        ]
        if status == "INSUFFICIENT_DATA"
        else [],
    }
