"""FinEx AI Simulation Package.

This package contains analytical simulation and stress-testing engines,
including seeded Monte Carlo models.
"""

from __future__ import annotations

from ai.simulation.monte_carlo import (
    DISCLAIMER_TEXT,
    DOCUMENTED_ASSUMPTIONS,
    DOCUMENTED_LIMITATIONS,
    CompoundingConvention,
    InvalidSimulationInputError,
    MonteCarloConfig,
    MonteCarloEngine,
    MonteCarloError,
    MonteCarloResult,
    NumericalInstabilityError,
    run_monte_carlo,
    theoretical_gbm_expected,
    theoretical_gbm_terminal,
    theoretical_gbm_variance,
)

__all__ = [
    "DISCLAIMER_TEXT",
    "DOCUMENTED_ASSUMPTIONS",
    "DOCUMENTED_LIMITATIONS",
    "CompoundingConvention",
    "InvalidSimulationInputError",
    "MonteCarloConfig",
    "MonteCarloEngine",
    "MonteCarloError",
    "MonteCarloResult",
    "NumericalInstabilityError",
    "run_monte_carlo",
    "theoretical_gbm_expected",
    "theoretical_gbm_terminal",
    "theoretical_gbm_variance",
]
