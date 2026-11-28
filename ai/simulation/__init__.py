"""FinEx AI Simulation Package.

This package contains analytical simulation and stress-testing engines,
including historical stress scenarios, drawdown analysis, and Monte Carlo models.
"""

from __future__ import annotations

from ai.simulation.stress import (
    HISTORICAL_SCENARIOS,
    DrawdownPoint,
    DuplicateObservationError,
    HistoricalStressEngine,
    InsufficientDataError,
    InvalidObservationError,
    PriceObservation,
    ScenarioWindow,
    ScenarioWindowError,
    StressEngineError,
    StressScenarioResult,
    calculate_drawdown_series,
    calculate_stress_metrics,
    evaluate_from_candles,
    evaluate_scenario_window,
    normalize_observations,
)

__all__ = [
    "HISTORICAL_SCENARIOS",
    "DrawdownPoint",
    "DuplicateObservationError",
    "HistoricalStressEngine",
    "InsufficientDataError",
    "InvalidObservationError",
    "PriceObservation",
    "ScenarioWindow",
    "ScenarioWindowError",
    "StressEngineError",
    "StressScenarioResult",
    "calculate_drawdown_series",
    "calculate_stress_metrics",
    "evaluate_from_candles",
    "evaluate_scenario_window",
    "normalize_observations",
]
