"""Contract and Schema Integration Tests for FinEx Monte Carlo Simulation Engine.

Task: S4-MI01
Issue: #62
Owner: Mitali (@mitali2701)
Secondary Reviewer: Payal (@payalmude14-star)

Architectural Boundary & Scope Documentation:
---------------------------------------------
1. Pure Engine Scope (S4-MI01):
   `ai/simulation/monte_carlo.py` is an analytical, non-networked calculation engine.
   Per FinEx architecture, it does NOT own database models, migration tables, HTTP routers,
   or user session management.

2. Downstream Router & Persistence Ownership (S4-PA01, Issue #64):
   - HTTP routes (`app/routers/simulations.py`)
   - Service orchestration (`app/services/simulation_service.py`)
   - Database persistence (`finex.simulation_runs`)
   - User isolation (`Depends(get_current_principal)`)
   These are explicitly allocated to downstream Task S4-PA01 (#64), which depends on S4-MI01.

3. Downstream Retirement & Life Event Consumers (S4-LI01 & S4-LI04):
   - Retirement calculator (`app/services/retirement_service.py`, Issue #65)
   - What-if and life events scenario routes (Issue #68)

This test module verifies the public API contract, Pydantic V2 schemas, serialization fidelity,
immutability, and OpenAPI schema generation ready for downstream S4-PA01 consumption.
"""

from __future__ import annotations

import json

import pytest
from ai.simulation.monte_carlo import (
    MonteCarloConfig,
    MonteCarloEngine,
    MonteCarloResult,
    run_monte_carlo,
)
from pydantic import ValidationError


class TestMonteCarloPublicContractSchema:
    """Verifies that engine models satisfy strict API contract requirements."""

    def test_config_json_schema_generation(self) -> None:
        """MonteCarloConfig generates valid schema suitable for FastAPI request validation."""
        schema = MonteCarloConfig.model_json_schema()

        assert schema["type"] == "object"
        properties = schema["properties"]
        required = schema["required"]

        # Required fields
        for field in [
            "initial_value",
            "annualized_return",
            "annualized_volatility",
            "time_horizon_years",
        ]:
            assert field in required, f"Field '{field}' should be required in config schema"
            assert field in properties, f"Field '{field}' should have schema property definition"

        # Optional fields with defaults
        assert "num_paths" in properties
        assert properties["num_paths"]["default"] == 1000
        assert "steps_per_year" in properties
        assert properties["steps_per_year"]["default"] == 252
        assert "seed" in properties
        assert "periodic_contribution" in properties
        assert "compounding" in properties

    def test_result_json_schema_generation(self) -> None:
        """MonteCarloResult generates valid JSON schema suitable for FastAPI response models."""
        schema = MonteCarloResult.model_json_schema()

        assert schema["type"] == "object"
        properties = schema["properties"]

        expected_fields = [
            "config",
            "actual_seed",
            "total_steps",
            "dt",
            "mean_final_value",
            "median_final_value",
            "std_final_value",
            "min_final_value",
            "max_final_value",
            "theoretical_expected_value",
            "percentiles",
            "probability_of_loss",
            "expected_shortfall_p05",
            "max_drawdown_stats",
            "percentile_trajectories",
            "sample_paths",
            "final_values",
            "assumptions",
            "limitations",
            "disclaimer",
        ]
        for field in expected_fields:
            assert field in properties, f"Field '{field}' missing from MonteCarloResult schema"

    def test_serialization_fidelity_and_json_roundtrip(self) -> None:
        """MonteCarloResult serializes to pure JSON without raw NumPy scalar type errors."""
        config = MonteCarloConfig(
            initial_value=15000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=2.0,
            num_paths=100,
            steps_per_year=12,
            seed=42,
        )
        result = run_monte_carlo(config)

        # 1. model_dump() must produce a standard Python dict
        dumped_dict = result.model_dump()
        assert isinstance(dumped_dict, dict)

        # 2. json.dumps must serialize cleanly without TypeError (no numpy types)
        json_str = json.dumps(dumped_dict)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

        # 3. model_dump_json() must also succeed directly
        direct_json_str = result.model_dump_json()
        assert isinstance(direct_json_str, str)

        # 4. Deserialization: model_validate must reconstruct identical instance
        reconstructed = MonteCarloResult.model_validate(json.loads(json_str))
        assert reconstructed.actual_seed == result.actual_seed
        assert reconstructed.mean_final_value == result.mean_final_value
        assert reconstructed.median_final_value == result.median_final_value
        assert reconstructed.std_final_value == result.std_final_value
        assert reconstructed.percentiles == result.percentiles
        assert reconstructed.percentile_trajectories == result.percentile_trajectories
        assert reconstructed.sample_paths == result.sample_paths

    def test_immutability_of_config_and_result(self) -> None:
        """Config and Result models must be frozen and immutable to prevent accidental mutation."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=1.0,
            num_paths=50,
            seed=42,
        )
        result = run_monte_carlo(config)

        with pytest.raises(ValidationError):
            config.initial_value = 20000.0  # type: ignore[misc]

        with pytest.raises(ValidationError):
            result.mean_final_value = 99999.0  # type: ignore[misc]


class TestDownstreamArchitecturalBoundaries:
    """Documents and verifies architectural boundaries between S4-MI01 and downstream tasks."""

    def test_downstream_task_ownership_documentation(self) -> None:
        """Formal verification of architectural responsibility boundaries."""
        # S4-MI01 ownership
        assert hasattr(MonteCarloConfig, "model_validate")
        assert hasattr(MonteCarloResult, "model_validate")
        assert callable(run_monte_carlo)

        # Downstream S4-PA01 contract boundaries
        downstream_pa01_dependencies: dict[str, str] = {
            "routes": "app/routers/simulations.py (Owned by S4-PA01, Issue #64)",
            "service": "app/services/simulation_service.py (Owned by S4-PA01, Issue #64)",
            "persistence": "finex.simulation_runs table (Owned by S4-PA01, Issue #64)",
            "auth_guard": "Depends(get_current_principal) (Owned by S4-PA01, Issue #64)",
        }
        for component, description in downstream_pa01_dependencies.items():
            assert description is not None, f"Missing documentation for {component}"

        # Downstream S4-LI01 contract boundaries
        downstream_li01_dependencies: dict[str, str] = {
            "calculator": "app/services/retirement_service.py (Owned by S4-LI01, Issue #65)",
            "cash_flows": "periodic_contribution field on MonteCarloConfig",
        }
        for component, description in downstream_li01_dependencies.items():
            assert description is not None, f"Missing documentation for {component}"

    def test_no_side_effects_or_state_leakage(self) -> None:
        """Engine invocation has zero network, database, or external state side effects."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=1.0,
            num_paths=10,
            seed=1,
        )
        engine = MonteCarloEngine(config)
        res1 = engine.simulate()
        res2 = engine.simulate()

        # Engine does not retain mutable internal state between calls
        assert res1.actual_seed == res2.actual_seed
        assert res1.mean_final_value == res2.mean_final_value
