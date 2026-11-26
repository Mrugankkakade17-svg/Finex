import pytest

from app.services.portfolio_analytics_service import calculate_portfolio_analytics


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
