from datetime import date

import pytest

from app.services import portfolio_analytics_service
from app.services.portfolio_analytics_service import (
    align_close_price_history,
    calculate_portfolio_analytics,
)


def test_insufficient_history_keeps_current_hhi_and_top_n_available():
    result = calculate_portfolio_analytics(
        portfolio_id="portfolio-1",
        holdings=[
            {"symbol": "AAPL", "quantity": 1, "current_value": 200},
            {"symbol": "BND", "quantity": 2, "current_value": 100},
            {"symbol": "MSFT", "quantity": 1, "current_value": 300},
        ],
    )

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["returns"] == {"cumulative": None, "annualized": None, "daily_mean": None}
    assert result["sharpe_ratio"] is None
    assert result["beta"] is None
    assert result["value_at_risk"]["historical"] is None
    assert result["hhi"] == 0.388889
    assert [row["symbol"] for row in result["top_holdings"]] == ["MSFT", "AAPL", "BND"]


def test_hand_computed_returns_beta_and_var_are_deterministic():
    result = calculate_portfolio_analytics(
        portfolio_id="portfolio-1",
        holdings=[{"symbol": "AAA", "quantity": 1, "current_value": 100}],
        price_history={"AAA": [100, 110, 100]},
        benchmark_prices=[100, 105, 100],
        risk_free_rate_annual=0.0,
        risk_free_rate_source="fixture treasury curve",
        risk_free_rate_as_of="2026-01-02",
    )

    assert result["status"] == "COMPLETE"
    assert result["observation_count"] == 2
    assert result["returns"]["cumulative"] == 0.0
    assert result["beta"] == pytest.approx(1.9556541)
    assert result["annualized_volatility"] > 0
    assert result["value_at_risk"]["historical"] == pytest.approx(8.14)
    assert result["risk_free_rate"] == {
        "annual_rate": 0.0,
        "source": "fixture treasury curve",
        "as_of": "2026-01-02",
    }


@pytest.mark.parametrize(
    "kwargs",
    [
        {"top_n": 0},
        {"top_n": 101},
        {"confidence_level": 0.975},
        {"risk_free_rate_annual": -1.0},
        {"risk_free_rate_source": ""},
    ],
)
def test_invalid_analytics_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        calculate_portfolio_analytics(
            portfolio_id="portfolio-1",
            holdings=[],
            **kwargs,
        )


def test_misaligned_history_does_not_publish_performance_metrics():
    result = calculate_portfolio_analytics(
        portfolio_id="portfolio-1",
        holdings=[
            {"symbol": "AAA", "quantity": 1, "current_value": 50},
            {"symbol": "BBB", "quantity": 1, "current_value": 50},
        ],
        price_history={"AAA": [10, 11, 12], "BBB": [20, 21]},
    )

    assert result["status"] == "INSUFFICIENT_DATA"
    assert result["returns"]["cumulative"] is None
    assert result["sharpe_ratio"] is None


def test_close_history_alignment_uses_only_shared_dates():
    history = {
        "AAA": [
            {"timestamp": "2026-01-01", "close": 10},
            {"timestamp": "2026-01-02", "close": 11},
            {"timestamp": "2026-01-03", "close": 12},
            {"timestamp": "2026-01-04", "close": 13},
        ],
        "BBB": [
            {"timestamp": "2026-01-02", "close": 20},
            {"timestamp": "2026-01-03", "close": 21},
            {"timestamp": "2026-01-04", "close": 22},
        ],
        "SPY": [
            {"timestamp": "2026-01-01", "close": 100},
            {"timestamp": "2026-01-02", "close": 105},
            {"timestamp": "2026-01-03", "close": 110},
            {"timestamp": "2026-01-04", "close": 115},
        ],
    }

    positions, benchmark = align_close_price_history(history, ["AAA", "BBB"], "SPY")

    assert positions == {"AAA": [11.0, 12.0, 13.0], "BBB": [20.0, 21.0, 22.0]}
    assert benchmark == [105.0, 110.0, 115.0]


def test_market_history_fetch_selects_currency_exchange_and_binds_symbols(monkeypatch):
    calls = []

    def execute_query(query, params):
        calls.append((query, params))
        return [{"timestamp": date(2026, 1, 2), "close": "105.25"}]

    monkeypatch.setattr(portfolio_analytics_service, "execute_query", execute_query)

    result = portfolio_analytics_service.fetch_close_price_history(
        ["aapl", "AAPL"],
        currency="USD",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )

    assert result == {"AAPL": [{"timestamp": date(2026, 1, 2), "close": 105.25}]}
    assert len(calls) == 1
    assert "('NASDAQ', 'NYSE')" in calls[0][0]
    assert calls[0][1]["symbol"] == "AAPL"


def test_market_history_rejects_unsupported_currency_without_query(monkeypatch):
    monkeypatch.setattr(
        portfolio_analytics_service,
        "execute_query",
        lambda *args, **kwargs: pytest.fail("Unsupported currency must not query market history"),
    )
    assert portfolio_analytics_service.fetch_close_price_history(
        ["AAPL"],
        currency="EUR",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    ) == {}
