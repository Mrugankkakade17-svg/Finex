"""Unit, contract, and golden scenario tests for the FinEx S4-MI02 historical stress engine.

Task ID: S4-MI02
File under test: ai/simulation/stress.py
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from ai.simulation.stress import (
    HISTORICAL_SCENARIOS,
    DuplicateObservationError,
    HistoricalStressEngine,
    InsufficientDataError,
    InvalidObservationError,
    PriceObservation,
    ScenarioWindow,
    ScenarioWindowError,
    calculate_drawdown_series,
    calculate_stress_metrics,
    evaluate_from_candles,
    evaluate_scenario_window,
    normalize_observations,
)


def _load_golden_scenarios() -> list[dict]:
    # Look in root ai/simulation or backend/ai/simulation
    root = Path(__file__).resolve().parents[3]
    golden_path = root / "ai" / "simulation" / "golden_scenarios_v1.json"
    if not golden_path.exists():
        fallback = Path(__file__).resolve().parents[2] / "ai" / "simulation"
        golden_path = fallback / "golden_scenarios_v1.json"
    with open(golden_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["scenarios"]


# ==============================================================================
# A. Golden Scenario Tests
# ==============================================================================


@pytest.mark.parametrize("scenario", _load_golden_scenarios(), ids=lambda s: s["scenario_id"])
def test_all_official_golden_scenarios_pass(scenario: dict) -> None:
    """Verify that every defined golden scenario passes with exact hand-calculated metrics."""
    observations = [
        PriceObservation(
            date=date.fromisoformat(row["date"]),
            price=Decimal(str(row["price"])),
        )
        for row in scenario["observations"]
    ]

    result = HistoricalStressEngine.calculate(
        observations=observations,
        scenario_name=scenario["title"],
    )

    exp = scenario["expected"]
    assert result.trading_days == exp["trading_days"]
    assert result.calendar_days == exp["calendar_days"]
    assert float(result.start_price) == pytest.approx(exp["start_price"], abs=1e-6)
    assert float(result.end_price) == pytest.approx(exp["end_price"], abs=1e-6)
    assert float(result.cumulative_return) == pytest.approx(exp["cumulative_return"], abs=1e-6)
    assert float(result.cumulative_return_pct) == pytest.approx(
        exp["cumulative_return_pct"], abs=1e-4
    )
    assert float(result.max_drawdown) == pytest.approx(exp["max_drawdown"], abs=1e-6)
    assert float(result.max_drawdown_pct) == pytest.approx(exp["max_drawdown_pct"], abs=1e-4)
    assert result.peak_date.isoformat() == exp["peak_date"]
    assert float(result.peak_price) == pytest.approx(exp["peak_price"], abs=1e-6)
    assert result.trough_date.isoformat() == exp["trough_date"]
    assert float(result.trough_price) == pytest.approx(exp["trough_price"], abs=1e-6)
    assert result.recovered is exp["recovered"]
    if exp["recovery_date"] is not None:
        assert result.recovery_date is not None
        assert result.recovery_date.isoformat() == exp["recovery_date"]
    else:
        assert result.recovery_date is None
    assert result.peak_to_trough_days == exp["peak_to_trough_days"]
    assert result.recovery_days == exp["recovery_days"]
    assert result.peak_to_recovery_days == exp["peak_to_recovery_days"]


# ==============================================================================
# B. Mathematical Correctness Tests
# ==============================================================================


def test_monotonic_increasing_series_has_zero_drawdown() -> None:
    """Monotonically increasing prices must have exactly 0.0 drawdown and 100% recovery."""
    data = [
        (date(2026, 1, 1), 100.0),
        (date(2026, 1, 2), 110.0),
        (date(2026, 1, 3), 125.0),
        (date(2026, 1, 4), 140.0),
    ]
    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs, scenario_name="Monotonic Up")

    assert result.max_drawdown == Decimal("0.0")
    assert result.max_drawdown_pct == Decimal("0.0")
    assert result.cumulative_return == Decimal("0.40")  # (140 - 100) / 100
    assert result.recovered is True
    assert result.peak_to_trough_days == 0
    assert result.recovery_days == 0


def test_monotonic_decreasing_series_has_no_recovery() -> None:
    """Monotonically decreasing prices must have peak at start, trough at end, and no recovery."""
    data = [
        (date(2026, 2, 1), 100.0),
        (date(2026, 2, 2), 90.0),
        (date(2026, 2, 3), 75.0),
        (date(2026, 2, 4), 50.0),
    ]
    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs, scenario_name="Monotonic Down")

    assert result.max_drawdown == Decimal("-0.50")  # (50 - 100) / 100
    assert result.max_drawdown_pct == Decimal("-50.0")
    assert result.cumulative_return == Decimal("-0.50")
    assert result.peak_date == date(2026, 2, 1)
    assert result.trough_date == date(2026, 2, 4)
    assert result.recovered is False
    assert result.recovery_date is None
    assert result.peak_to_trough_days == 3


def test_constant_flat_prices() -> None:
    """Constant flat prices must have zero return and zero drawdown."""
    data = [(date(2026, 3, i), 100.0) for i in range(1, 6)]
    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs, scenario_name="Flat Series")

    assert result.cumulative_return == Decimal("0.0")
    assert result.max_drawdown == Decimal("0.0")
    assert result.recovered is True
    assert result.peak_price == Decimal("100.0")
    assert result.trough_price == Decimal("100.0")


def test_v_shape_crash_and_recovery_metrics() -> None:
    """A single sharp drop followed by full recovery identifies exact peak, trough, and recovery."""
    data = [
        (date(2026, 4, 1), 100),
        (date(2026, 4, 2), 200),
        (date(2026, 4, 3), 100),
        (date(2026, 4, 4), 150),
        (date(2026, 4, 5), 200),
        (date(2026, 4, 6), 220),
    ]
    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs, scenario_name="V-Shape")

    assert result.peak_date == date(2026, 4, 2)
    assert result.peak_price == Decimal("200")
    assert result.trough_date == date(2026, 4, 3)
    assert result.trough_price == Decimal("100")
    assert result.max_drawdown == Decimal("-0.5")
    assert result.max_drawdown_pct == Decimal("-50.0")
    assert result.recovered is True
    assert result.recovery_date == date(2026, 4, 5)
    assert result.peak_to_trough_days == 1
    assert result.recovery_days == 2  # April 3 to April 5
    assert result.peak_to_recovery_days == 3  # April 2 to April 5


def test_multiple_drawdowns_selects_global_maximum() -> None:
    """Verify that the engine selects the true global maximum drawdown among multiple waves."""
    data = [
        (date(2026, 5, 1), 100),
        (date(2026, 5, 2), 80),
        (date(2026, 5, 3), 150),
        (date(2026, 5, 4), 60),
        (date(2026, 5, 5), 160),
        (date(2026, 5, 6), 120),
    ]
    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs)

    assert result.max_drawdown == Decimal("-0.6")
    assert result.peak_date == date(2026, 5, 3)
    assert result.peak_price == Decimal("150")
    assert result.trough_date == date(2026, 5, 4)
    assert result.trough_price == Decimal("60")
    assert result.recovered is True
    assert result.recovery_date == date(2026, 5, 5)


def test_step_by_step_drawdown_series() -> None:
    """Verify that calculate_drawdown_series correctly tracks periodic returns and running peaks."""
    data = [
        (date(2026, 6, 1), 100.0),
        (date(2026, 6, 2), 120.0),
        (date(2026, 6, 3), 90.0),
    ]
    obs = normalize_observations(data)
    points = calculate_drawdown_series(obs)

    assert len(points) == 3
    # Point 0
    assert points[0].running_peak == Decimal("100.0")
    assert points[0].drawdown == Decimal("0.0")
    assert points[0].period_return is None

    # Point 1: 120 -> new peak
    assert points[1].running_peak == Decimal("120.0")
    assert points[1].drawdown == Decimal("0.0")
    assert points[1].period_return == Decimal("0.2")

    # Point 2: 90 -> drop from 120
    assert points[2].running_peak == Decimal("120.0")
    assert points[2].drawdown == Decimal("-0.25")  # (90 - 120) / 120 = -30 / 120
    assert points[2].period_return == Decimal("-0.25")  # (90 - 120) / 120


# ==============================================================================
# C. Input Validation and Exception Tests
# ==============================================================================


def test_empty_observations_raises_insufficient_data_error() -> None:
    with pytest.raises(InsufficientDataError, match="empty"):
        normalize_observations([])


def test_single_observation_raises_insufficient_data_error() -> None:
    obs = [PriceObservation(date=date(2026, 1, 1), price=Decimal("100"))]
    with pytest.raises(InsufficientDataError, match="At least 2 historical observations"):
        calculate_stress_metrics(obs)


@pytest.mark.parametrize("invalid_price", [0, -10, -0.01])
def test_zero_or_negative_price_raises_invalid_observation_error(invalid_price: float) -> None:
    with pytest.raises(InvalidObservationError, match="strictly positive"):
        normalize_observations([(date(2026, 1, 1), invalid_price)])


@pytest.mark.parametrize("non_finite", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_price_raises_invalid_observation_error(non_finite: float) -> None:
    with pytest.raises(InvalidObservationError, match="finite"):
        normalize_observations([(date(2026, 1, 1), non_finite)])


def test_duplicate_differing_price_on_same_date_raises_duplicate_error() -> None:
    data = [
        {"date": "2026-01-01", "close": 100},
        {"date": "2026-01-01", "close": 105},
    ]
    with pytest.raises(DuplicateObservationError, match="Conflicting duplicate observation"):
        normalize_observations(data)


def test_identical_duplicate_on_same_date_deduplicates_deterministically() -> None:
    data = [
        {"date": "2026-01-01", "close": 100},
        {"date": "2026-01-01", "close": 100},
        {"date": "2026-01-02", "close": 110},
    ]
    obs = normalize_observations(data)
    assert len(obs) == 2
    assert obs[0].date == date(2026, 1, 1)
    assert obs[1].date == date(2026, 1, 2)


def test_out_of_order_dates_are_sorted_chronologically() -> None:
    data = [
        (date(2026, 1, 5), 150),
        (date(2026, 1, 1), 100),
        (date(2026, 1, 3), 120),
    ]
    obs = normalize_observations(data, sort_chronological=True)
    assert [o.date for o in obs] == [date(2026, 1, 1), date(2026, 1, 3), date(2026, 1, 5)]
    assert [o.price for o in obs] == [Decimal("100"), Decimal("120"), Decimal("150")]


def test_missing_required_fields_in_dict_raises_invalid_observation_error() -> None:
    with pytest.raises(InvalidObservationError, match="missing date/timestamp"):
        normalize_observations([{"close": 100}])

    with pytest.raises(InvalidObservationError, match="missing price/close"):
        normalize_observations([{"timestamp": "2026-01-01"}])


def test_invalid_date_type_raises_invalid_observation_error() -> None:
    with pytest.raises(InvalidObservationError, match="Cannot parse date"):
        normalize_observations([(12345678, 100)])


def test_scenario_window_end_before_start_raises_error() -> None:
    with pytest.raises(ScenarioWindowError, match="cannot precede"):
        ScenarioWindow(
            name="Inverted Window",
            start_date=date(2026, 5, 10),
            end_date=date(2026, 5, 5),
        )


def test_unknown_scenario_name_raises_scenario_window_error() -> None:
    with pytest.raises(ScenarioWindowError, match="Unknown scenario key"):
        evaluate_scenario_window(
            [(date(2026, 1, 1), 100), (date(2026, 1, 2), 110)], "NON_EXISTENT_CRISIS"
        )


# ==============================================================================
# D. Edge Cases & Market Calendar Gaps
# ==============================================================================


def test_weekend_and_holiday_gaps_handled_without_data_fabrication() -> None:
    """Verify returns across weekend/holiday gaps are calculated between real sessions."""
    data = [
        (date(2026, 1, 2), 100.0),  # Friday
        (date(2026, 1, 6), 110.0),  # Tuesday
    ]
    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs)

    assert result.trading_days == 2
    assert result.calendar_days == 4
    assert result.cumulative_return == Decimal("0.10")


def test_large_multi_year_series_performance_and_accuracy() -> None:
    """Verify that a synthetic 1,000-day series executes deterministically and accurately."""
    start = date(2020, 1, 1)
    data = []
    for i in range(1000):
        d = date.fromordinal(start.toordinal() + i)
        if i < 500:
            p = 100 + (i * 0.2)  # up to 200 at i=500
        elif i == 500:
            p = 100  # -50% crash
        else:
            p = 100 + ((i - 500) * 0.1)  # gradual recovery
        data.append((d, p))

    obs = normalize_observations(data)
    result = calculate_stress_metrics(obs, include_series=True)

    assert result.trading_days == 1000
    assert result.max_drawdown < Decimal("-0.49")
    assert result.drawdown_series is not None
    assert len(result.drawdown_series) == 1000


# ==============================================================================
# E. Determinism Tests
# ==============================================================================


def test_determinism_repeated_execution_yields_identical_output() -> None:
    """Running calculation 50 times on identical inputs produces identical results."""
    data = [
        (date(2026, 7, 1), 100),
        (date(2026, 7, 2), 150),
        (date(2026, 7, 3), 75),
        (date(2026, 7, 4), 120),
        (date(2026, 7, 5), 160),
    ]
    obs = normalize_observations(data)

    base = calculate_stress_metrics(obs)
    for _ in range(50):
        run = calculate_stress_metrics(obs)
        assert run.cumulative_return == base.cumulative_return
        assert run.max_drawdown == base.max_drawdown
        assert run.peak_date == base.peak_date
        assert run.trough_date == base.trough_date
        assert run.recovery_date == base.recovery_date
        assert run.to_summary_dict() == base.to_summary_dict()


# ==============================================================================
# F. Integration & S2-PA03 Contract Compatibility Tests
# ==============================================================================


def test_s2_pa03_candle_dict_compatibility() -> None:
    """Verify direct evaluation from S2-PA03 GET /api/v1/market/instruments/{symbol}/ohlcv items."""
    s2_candles = [
        {
            "timestamp": "2026-11-01T00:00:00",
            "open": "100.00",
            "high": "110.00",
            "low": "95.00",
            "close": "105.00",
            "volume": 50000,
        },
        {
            "timestamp": "2026-11-02T00:00:00",
            "open": "105.00",
            "high": "115.00",
            "low": "102.00",
            "close": "112.00",
            "volume": 62000,
        },
        {
            "timestamp": "2026-11-03T00:00:00",
            "open": "112.00",
            "high": "112.00",
            "low": "80.00",
            "close": "84.00",
            "volume": 98000,
        },
        {
            "timestamp": "2026-11-04T00:00:00",
            "open": "84.00",
            "high": "120.00",
            "low": "82.00",
            "close": "115.00",
            "volume": 75000,
        },
    ]

    result = evaluate_from_candles(
        candles=s2_candles,
        scenario_name="S2-PA03 Integration Test",
        symbol="AAPL",
        exchange="NASDAQ",
    )

    assert result.symbol == "AAPL"
    assert result.exchange == "NASDAQ"
    assert result.trading_days == 4
    assert result.start_price == Decimal("105.00")
    assert result.end_price == Decimal("115.00")
    assert result.max_drawdown == Decimal("-0.25")
    assert result.max_drawdown_pct == Decimal("-25.0")
    assert result.peak_date == date(2026, 11, 2)
    assert result.trough_date == date(2026, 11, 3)
    assert result.recovered is True
    assert result.recovery_date == date(2026, 11, 4)


def test_evaluate_scenario_window_filtering() -> None:
    """Verify that evaluate_scenario_window correctly filters a multi-month series into window."""
    window = ScenarioWindow(
        name="Target Month",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    data = [
        (date(2026, 1, 15), 50.0),
        (date(2026, 3, 2), 100.0),
        (date(2026, 3, 15), 70.0),
        (date(2026, 3, 30), 110.0),
        (date(2026, 4, 15), 150.0),
    ]

    result = evaluate_scenario_window(
        data,
        scenario=window,
        allow_partial_window=True,
    )

    assert result.trading_days == 3
    assert result.start_date == date(2026, 3, 2)
    assert result.end_date == date(2026, 3, 30)
    assert result.max_drawdown == Decimal("-0.30")


def test_reference_scenarios_definitions_are_valid() -> None:
    """Verify that canonical reference scenario definitions have valid dates."""
    assert len(HISTORICAL_SCENARIOS) >= 4
    for _, scn in HISTORICAL_SCENARIOS.items():
        assert scn.end_date > scn.start_date
        assert len(scn.name) > 0
        assert scn.description is not None


# ==============================================================================
# G. Security, User Isolation and Facade Tests
# ==============================================================================


def test_stateless_facade_and_user_isolation() -> None:
    """Verify that HistoricalStressEngine provides state-free execution with zero shared state."""
    engine = HistoricalStressEngine()

    data_user_a = [(date(2026, 1, 1), 100), (date(2026, 1, 2), 200)]
    data_user_b = [(date(2026, 1, 1), 500), (date(2026, 1, 2), 250)]

    res_a = engine.calculate(engine.normalize(data_user_a), symbol="USER_A")
    res_b = engine.calculate(engine.normalize(data_user_b), symbol="USER_B")

    assert res_a.symbol == "USER_A"
    assert res_a.cumulative_return == Decimal("1.0")
    assert res_b.symbol == "USER_B"
    assert res_b.cumulative_return == Decimal("-0.5")


def test_to_summary_dict_is_fully_json_serializable() -> None:
    """Verify that summary dicts contain standard primitive types that serialize to JSON cleanly."""
    data = [(date(2026, 1, 1), 100), (date(2026, 1, 2), 80)]
    result = calculate_stress_metrics(
        normalize_observations(data), symbol="AAPL", exchange="NASDAQ"
    )
    summary = result.to_summary_dict()

    dumped = json.dumps(summary)
    loaded = json.loads(dumped)

    assert loaded["symbol"] == "AAPL"
    assert loaded["max_drawdown"] == -0.2
    assert loaded["peak_date"] == "2026-01-01"
    assert loaded["trough_date"] == "2026-01-02"


# ==============================================================================
# H. Additional Comprehensive Edge Cases & Boundary Tests
# ==============================================================================


def test_two_observations_minimal_valid_series() -> None:
    """Minimal valid series of length 2 correctly handles gain, loss, and flat price pairs."""
    # 1. Gain pair
    gain_data = [(date(2026, 1, 1), 100), (date(2026, 1, 2), 120)]
    gain_res = calculate_stress_metrics(normalize_observations(gain_data))
    assert gain_res.trading_days == 2
    assert gain_res.cumulative_return == Decimal("0.20")
    assert gain_res.max_drawdown == Decimal("0.0")
    assert gain_res.recovered is True
    assert gain_res.peak_date == date(2026, 1, 2)
    assert gain_res.trough_date == date(2026, 1, 2)
    assert gain_res.peak_to_trough_days == 0
    assert gain_res.recovery_days == 0

    # 2. Loss pair
    loss_data = [(date(2026, 1, 1), 100), (date(2026, 1, 2), 85)]
    loss_res = calculate_stress_metrics(normalize_observations(loss_data))
    assert loss_res.trading_days == 2
    assert loss_res.cumulative_return == Decimal("-0.15")
    assert loss_res.max_drawdown == Decimal("-0.15")
    assert loss_res.recovered is False
    assert loss_res.recovery_date is None
    assert loss_res.peak_date == date(2026, 1, 1)
    assert loss_res.trough_date == date(2026, 1, 2)
    assert loss_res.peak_to_trough_days == 1

    # 3. Flat pair
    flat_data = [(date(2026, 1, 1), 100), (date(2026, 1, 2), 100)]
    flat_res = calculate_stress_metrics(normalize_observations(flat_data))
    assert flat_res.trading_days == 2
    assert flat_res.cumulative_return == Decimal("0.0")
    assert flat_res.max_drawdown == Decimal("0.0")
    assert flat_res.recovered is True
    assert flat_res.peak_date == date(2026, 1, 1)
    assert flat_res.trough_date == date(2026, 1, 1)
    assert flat_res.peak_to_trough_days == 0


def test_immediate_drawdown_after_peak() -> None:
    """Peak established on day 2 immediately followed by drop on day 3."""
    data = [
        (date(2026, 2, 1), 100),
        (date(2026, 2, 2), 120),
        (date(2026, 2, 3), 84),
        (date(2026, 2, 4), 90),
    ]
    res = calculate_stress_metrics(normalize_observations(data))
    assert res.peak_date == date(2026, 2, 2)
    assert res.peak_price == Decimal("120")
    assert res.trough_date == date(2026, 2, 3)
    assert res.trough_price == Decimal("84")
    assert res.max_drawdown == Decimal("-0.30")
    assert res.max_drawdown_pct == Decimal("-30.0")
    assert res.peak_to_trough_days == 1
    assert res.recovered is False


def test_multiple_equal_peaks_deterministic_earliest_tie_break() -> None:
    """Equal peaks at 100 on Day 1 and Day 3, then drop on Day 4 selects Day 1 as peak."""
    data = [
        (date(2026, 3, 1), 100),
        (date(2026, 3, 2), 90),
        (date(2026, 3, 3), 100),
        (date(2026, 3, 4), 50),
    ]
    res = calculate_stress_metrics(normalize_observations(data))
    assert res.peak_date == date(2026, 3, 1)
    assert res.peak_price == Decimal("100")
    assert res.trough_date == date(2026, 3, 4)
    assert res.trough_price == Decimal("50")
    assert res.max_drawdown == Decimal("-0.50")
    assert res.peak_to_trough_days == 3


def test_multiple_equal_troughs_deterministic_earliest_tie_break() -> None:
    """Equal troughs on Day 2 and Day 4 select Day 2, and recovery evaluates after Day 2."""
    data = [
        (date(2026, 4, 1), 100),
        (date(2026, 4, 2), 50),
        (date(2026, 4, 3), 70),
        (date(2026, 4, 4), 50),
        (date(2026, 4, 5), 110),
    ]
    res = calculate_stress_metrics(normalize_observations(data))
    assert res.peak_date == date(2026, 4, 1)
    assert res.trough_date == date(2026, 4, 2)
    assert res.trough_price == Decimal("50")
    assert res.max_drawdown == Decimal("-0.50")
    assert res.recovered is True
    assert res.recovery_date == date(2026, 4, 5)
    assert res.peak_to_trough_days == 1
    assert res.recovery_days == 3  # April 2 to April 5


def test_recovery_exactly_to_previous_peak() -> None:
    """Recovery where terminal price reaches exactly the previous peak price."""
    data = [
        (date(2026, 5, 1), 100),
        (date(2026, 5, 2), 60),
        (date(2026, 5, 3), 80),
        (date(2026, 5, 4), 100.0),
    ]
    res = calculate_stress_metrics(normalize_observations(data))
    assert res.recovered is True
    assert res.recovery_date == date(2026, 5, 4)
    assert res.peak_price == Decimal("100")
    assert res.recovery_days == 2


def test_recovery_above_previous_peak() -> None:
    """Recovery where terminal price jumps strictly above previous peak price."""
    data = [
        (date(2026, 6, 1), 100),
        (date(2026, 6, 2), 60),
        (date(2026, 6, 3), 125.0),
    ]
    res = calculate_stress_metrics(normalize_observations(data))
    assert res.recovered is True
    assert res.recovery_date == date(2026, 6, 3)
    assert res.peak_price == Decimal("100")
    assert res.recovery_days == 1


def test_benchmark_window_missing_dates_rejection() -> None:
    """allow_partial_window=False rejects > 7-day gaps at start or end boundaries."""
    window = ScenarioWindow(
        name="Strict Window",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
    )

    # 1. Starts too late (> 7 days after window start)
    gapped_start = [(date(2026, 7, 15), 100), (date(2026, 7, 30), 110)]
    with pytest.raises(InsufficientDataError, match="starts on"):
        evaluate_scenario_window(gapped_start, scenario=window, allow_partial_window=False)

    # 2. Ends too early (> 7 days before window end)
    gapped_end = [(date(2026, 7, 2), 100), (date(2026, 7, 10), 110)]
    with pytest.raises(InsufficientDataError, match="ends on"):
        evaluate_scenario_window(gapped_end, scenario=window, allow_partial_window=False)


def test_benchmark_window_with_mismatched_dates() -> None:
    """Observations that do not overlap with the requested window raise InsufficientDataError."""
    data = [(date(2025, 1, 1), 100), (date(2025, 1, 2), 110)]
    window = ScenarioWindow(
        name="Disjoint Window",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    with pytest.raises(InsufficientDataError, match="contains only 0 observation"):
        evaluate_scenario_window(data, scenario=window)


def test_benchmark_window_with_empty_data() -> None:
    """Empty observations passed to evaluate_scenario_window raise InsufficientDataError."""
    with pytest.raises(InsufficientDataError, match="empty"):
        evaluate_scenario_window([], scenario="COVID_CRASH_2020")


def test_caller_input_data_immutability() -> None:
    """Verify that caller's input sequence and inner dictionaries are never mutated."""
    raw_input = [
        {"date": "2026-08-05", "close": 150.0, "volume": 1000},
        {"date": "2026-08-01", "close": 100.0, "volume": 2000},
    ]
    raw_copy = [
        {"date": "2026-08-05", "close": 150.0, "volume": 1000},
        {"date": "2026-08-01", "close": 100.0, "volume": 2000},
    ]

    obs = normalize_observations(raw_input, sort_chronological=True)
    calculate_stress_metrics(obs)

    assert raw_input == raw_copy
    assert raw_input[0]["date"] == "2026-08-05"


@pytest.mark.parametrize("scenario_key", list(HISTORICAL_SCENARIOS.keys()))
def test_all_canonical_benchmark_windows_evaluate_with_synthetic_daily_series(
    scenario_key: str,
) -> None:
    """Verify all defined benchmark crisis windows execute accurately with synthetic data."""
    scn_window = HISTORICAL_SCENARIOS[scenario_key]
    total_days = (scn_window.end_date - scn_window.start_date).days

    # Generate synthetic daily data for the scenario window
    daily_data = [
        (
            date.fromordinal(scn_window.start_date.toordinal() + i),
            100.0 + (i % 10) * 2.0 - (5.0 if i > (total_days // 2) else 0.0),
        )
        for i in range(total_days + 1)
    ]

    result = evaluate_scenario_window(daily_data, scenario=scenario_key)

    assert result.trading_days == total_days + 1
    assert result.calendar_days == total_days
    assert result.scenario_name == scn_window.name
    assert result.start_date == scn_window.start_date
    assert result.end_date == scn_window.end_date
    assert result.max_drawdown <= Decimal("0.0")
    summary = result.to_summary_dict()
    assert summary["scenario_name"] == scn_window.name
    assert "max_drawdown" in summary
