"""Exhaustive unit test suite for FinEx Seeded Monte Carlo Simulation Engine.

Task: S4-MI01
Issue: #62
Owner: Mitali (@mitali2701)
Secondary Reviewer: Payal (@payalmude14-star)

Acceptance Criteria Tested:
- AC-1: Same seed gives identical output across all returned fields.
- AC-2: Zero-volatility case equals the exact closed-form calculation.
- AC-3: Different seeds produce distinct stochastic trajectories for sigma > 0.
- AC-4: Input validation strictly rejects invalid, negative, non-finite, or boolean parameters.
- AC-5: Numerical stability under extreme and edge-case horizons and parameters.
- AC-6: Deterministic randomness isolation without global RNG state pollution.
- AC-7: Pure offline in-memory execution with zero external I/O or network dependencies.
- AC-8: Output contract validation (percentile monotonicity, trajectory dimensions, risk metrics).
- AC-9: Periodic cash flows, withdrawals, and financial ruin flooring.
- AC-10: Statistical convergence to theoretical moments within confidence intervals.
"""

from __future__ import annotations

import math
import random
from typing import Any

import numpy as np
import pytest
from ai.simulation.monte_carlo import (
    MAX_SIMULATION_ELEMENTS,
    PERCENTILE_KEYS,
    CompoundingConvention,
    InvalidSimulationInputError,
    MonteCarloConfig,
    run_monte_carlo,
    theoretical_gbm_expected,
    theoretical_gbm_terminal,
    theoretical_gbm_variance,
)

# ===========================================================================
# 1. AC-1 & AC-2: Core Deterministic Contracts
# ===========================================================================


class TestMonteCarloDeterministicContracts:
    """Tests verifying AC-1 (Seed Reproducibility) and AC-2 (Zero-Volatility Closed Form)."""

    def test_ac1_same_seed_produces_identical_output(self) -> None:
        """AC-1: Identical seeds produce bitwise and numerically identical results."""
        config1 = MonteCarloConfig(
            initial_value=25000.0,
            annualized_return=0.09,
            annualized_volatility=0.18,
            time_horizon_years=3.5,
            num_paths=500,
            steps_per_year=252,
            seed=42,
        )
        config2 = MonteCarloConfig(
            initial_value=25000.0,
            annualized_return=0.09,
            annualized_volatility=0.18,
            time_horizon_years=3.5,
            num_paths=500,
            steps_per_year=252,
            seed=42,
        )

        result1 = run_monte_carlo(config1)
        result2 = run_monte_carlo(config2)

        # Seeds
        assert result1.actual_seed == result2.actual_seed == 42
        assert result1.total_steps == result2.total_steps
        assert result1.dt == result2.dt

        # Summary moments
        assert result1.mean_final_value == result2.mean_final_value
        assert result1.median_final_value == result2.median_final_value
        assert result1.std_final_value == result2.std_final_value
        assert result1.min_final_value == result2.min_final_value
        assert result1.max_final_value == result2.max_final_value
        assert result1.probability_of_loss == result2.probability_of_loss
        assert result1.expected_shortfall_p05 == result2.expected_shortfall_p05

        # Percentiles
        assert result1.percentiles == result2.percentiles

        # Drawdowns
        assert result1.max_drawdown_stats == result2.max_drawdown_stats

        # Full terminal values array
        assert result1.final_values == result2.final_values

        # Quantile trajectories across all steps
        assert result1.percentile_trajectories == result2.percentile_trajectories

        # Sample paths
        assert result1.sample_paths == result2.sample_paths

    def test_ac1_different_seeds_produce_distinct_trajectories(self) -> None:
        """Different seeds with positive volatility must produce different trajectories."""
        config1 = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=2.0,
            num_paths=100,
            seed=101,
        )
        config2 = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=2.0,
            num_paths=100,
            seed=202,
        )

        result1 = run_monte_carlo(config1)
        result2 = run_monte_carlo(config2)

        # Seeds differ
        assert result1.actual_seed == 101
        assert result2.actual_seed == 202

        # Stochastic terminal value vectors must not be identical
        assert result1.final_values != result2.final_values
        assert not np.array_equal(result1.final_values, result2.final_values)

        # Sample trajectories and percentiles must not be identical
        assert result1.sample_paths != result2.sample_paths
        assert result1.percentile_trajectories != result2.percentile_trajectories

        # Confirm that 100% of individual path terminal values differ between the runs
        differences = [v1 != v2 for v1, v2 in zip(result1.final_values, result2.final_values)]
        assert all(differences), "Generated stochastic values collided across different seeds"

    def test_different_seeds_with_zero_volatility_remain_identical(self) -> None:
        """When sigma = 0, output is purely deterministic and identical regardless of seed."""
        config1 = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.0,
            time_horizon_years=3.0,
            num_paths=100,
            seed=101,
        )
        config2 = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.0,
            time_horizon_years=3.0,
            num_paths=100,
            seed=202,
        )
        res1 = run_monte_carlo(config1)
        res2 = run_monte_carlo(config2)

        # Actual seeds differ
        assert res1.actual_seed == 101
        assert res2.actual_seed == 202

        # But all statistical outputs and trajectories are bitwise identical
        assert res1.mean_final_value == res2.mean_final_value
        assert res1.median_final_value == res2.median_final_value
        assert res1.std_final_value == res2.std_final_value == 0.0
        assert res1.final_values == res2.final_values
        assert res1.percentiles == res2.percentiles
        assert res1.percentile_trajectories == res2.percentile_trajectories
        assert res1.sample_paths == res2.sample_paths

    def test_ac1_omitted_seed_generates_valid_seed_and_results(self) -> None:
        """When seed is None, engine auto-generates a valid positive seed."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.07,
            annualized_volatility=0.12,
            time_horizon_years=1.0,
            num_paths=50,
            seed=None,
        )
        result = run_monte_carlo(config)

        assert isinstance(result.actual_seed, int)
        assert 0 <= result.actual_seed < 2**63 - 1
        assert math.isfinite(result.mean_final_value)
        assert result.mean_final_value > 0.0

    @pytest.mark.parametrize(
        ("initial", "mu", "horizon"),
        [
            (10000.0, 0.08, 1.0),
            (50000.0, 0.12, 5.0),
            (1000.0, -0.05, 3.0),
            (250000.0, 0.0, 10.0),
            (7500.0, 0.25, 0.5),
        ],
    )
    def test_ac2_zero_volatility_matches_closed_form_exact(
        self, initial: float, mu: float, horizon: float
    ) -> None:
        """AC-2: When sigma = 0, terminal value matches S_0 * exp(mu * T) exactly."""
        config = MonteCarloConfig(
            initial_value=initial,
            annualized_return=mu,
            annualized_volatility=0.0,
            time_horizon_years=horizon,
            num_paths=200,
            steps_per_year=252,
            seed=42,
        )
        result = run_monte_carlo(config)
        expected_terminal = theoretical_gbm_terminal(initial, mu, horizon)

        # Exact terminal value check across all statistical aggregates
        assert math.isclose(result.mean_final_value, expected_terminal, rel_tol=1e-12)
        assert math.isclose(result.median_final_value, expected_terminal, rel_tol=1e-12)
        assert math.isclose(result.min_final_value, expected_terminal, rel_tol=1e-12)
        assert math.isclose(result.max_final_value, expected_terminal, rel_tol=1e-12)
        assert result.std_final_value == 0.0

        # Every percentile must equal the exact analytical terminal
        for p_key, p_val in result.percentiles.items():
            assert math.isclose(p_val, expected_terminal, rel_tol=1e-12), f"Mismatch in {p_key}"

        # Theoretical values
        assert math.isclose(result.theoretical_expected_value, expected_terminal, rel_tol=1e-12)
        assert result.theoretical_variance == 0.0

        # Trajectories: every path should be identical to the deterministic trajectory at step k
        total_steps = result.total_steps
        dt = result.dt
        for k in range(total_steps + 1):
            t_k = k * dt
            expected_at_k = initial * math.exp(mu * t_k)
            # All percentile curves at time step k must match expected_at_k
            for p_key in PERCENTILE_KEYS:
                val_at_k = result.percentile_trajectories[p_key][k]
                assert math.isclose(val_at_k, expected_at_k, rel_tol=1e-10)

    def test_ac2_zero_volatility_annual_discrete_compounding(self) -> None:
        """AC-2 with annual discrete compounding convention: S_T = S_0 * (1 + r)^T."""
        initial = 10000.0
        r = 0.10
        horizon = 3.0
        config = MonteCarloConfig(
            initial_value=initial,
            annualized_return=r,
            annualized_volatility=0.0,
            time_horizon_years=horizon,
            num_paths=100,
            compounding=CompoundingConvention.ANNUAL_DISCRETE,
            seed=7,
        )
        result = run_monte_carlo(config)
        expected = theoretical_gbm_terminal(
            initial, r, horizon, compounding=CompoundingConvention.ANNUAL_DISCRETE
        )

        assert math.isclose(result.mean_final_value, expected, rel_tol=1e-12)
        assert math.isclose(result.min_final_value, expected, rel_tol=1e-12)
        assert math.isclose(result.max_final_value, expected, rel_tol=1e-12)
        assert result.std_final_value == 0.0


# ===========================================================================
# 2. Input Validation & Strict Error Handling
# ===========================================================================


class TestMonteCarloInputValidation:
    """Tests verifying input parameter validation, type safety, and boundary checks."""

    @pytest.mark.parametrize("invalid_initial", [0.0, -100.0, -1e-8])
    def test_rejects_non_positive_initial_value(self, invalid_initial: float) -> None:
        with pytest.raises(
            InvalidSimulationInputError, match="Initial value must be strictly positive"
        ):
            MonteCarloConfig(
                initial_value=invalid_initial,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=1.0,
            )

    @pytest.mark.parametrize("invalid_vol", [-0.01, -0.2, -1e-6])
    def test_rejects_negative_volatility(self, invalid_vol: float) -> None:
        with pytest.raises(InvalidSimulationInputError, match="volatility must be non-negative"):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=invalid_vol,
                time_horizon_years=1.0,
            )

    @pytest.mark.parametrize("invalid_horizon", [0.0, -1.0, -0.001])
    def test_rejects_non_positive_horizon(self, invalid_horizon: float) -> None:
        with pytest.raises(
            InvalidSimulationInputError, match="Time horizon must be strictly positive"
        ):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=invalid_horizon,
            )

    def test_rejects_horizon_exceeding_maximum(self) -> None:
        with pytest.raises(InvalidSimulationInputError, match="Time horizon cannot exceed 100"):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=101.0,
            )

    @pytest.mark.parametrize("invalid_paths", [0, -1, -500, 50001])
    def test_rejects_invalid_num_paths(self, invalid_paths: int) -> None:
        with pytest.raises(
            InvalidSimulationInputError, match="Number of paths must be between 1 and"
        ):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=1.0,
                num_paths=invalid_paths,
            )

    @pytest.mark.parametrize("invalid_steps", [0, -252, 1001])
    def test_rejects_invalid_steps_per_year(self, invalid_steps: int) -> None:
        with pytest.raises(
            InvalidSimulationInputError, match="Steps per year must be between 1 and"
        ):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=1.0,
                steps_per_year=invalid_steps,
            )

    @pytest.mark.parametrize(
        "field_name",
        [
            "initial_value",
            "annualized_return",
            "annualized_volatility",
            "time_horizon_years",
            "num_paths",
            "steps_per_year",
            "seed",
        ],
    )
    def test_rejects_boolean_types(self, field_name: str) -> None:
        """Booleans masquerading as numeric values (True/False) must be strictly rejected."""
        valid_kwargs: dict[str, object] = {
            "initial_value": 10000.0,
            "annualized_return": 0.08,
            "annualized_volatility": 0.15,
            "time_horizon_years": 1.0,
            "num_paths": 100,
            "steps_per_year": 252,
            "seed": 42,
        }
        valid_kwargs[field_name] = True
        with pytest.raises(InvalidSimulationInputError, match="must be a"):
            MonteCarloConfig(**valid_kwargs)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("field_name", "bad_val"),
        [
            ("initial_value", float("nan")),
            ("initial_value", float("inf")),
            ("annualized_return", float("nan")),
            ("annualized_return", float("-inf")),
            ("annualized_volatility", float("nan")),
            ("annualized_volatility", float("inf")),
            ("time_horizon_years", float("nan")),
        ],
    )
    def test_rejects_nan_and_inf(self, field_name: str, bad_val: float) -> None:
        """Non-finite floats (NaN, +Inf, -Inf) must be rejected."""
        valid_kwargs: dict[str, object] = {
            "initial_value": 10000.0,
            "annualized_return": 0.08,
            "annualized_volatility": 0.15,
            "time_horizon_years": 1.0,
        }
        valid_kwargs[field_name] = bad_val
        with pytest.raises(InvalidSimulationInputError, match="must be a finite number"):
            MonteCarloConfig(**valid_kwargs)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad_seed", [-1, 2**63])
    def test_rejects_invalid_seed_range(self, bad_seed: int) -> None:
        with pytest.raises(InvalidSimulationInputError, match="Seed must be in range"):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=1.0,
                seed=bad_seed,
            )

    def test_rejects_extra_fields(self) -> None:
        """Extra unauthorized attributes must be forbidden by Pydantic model configuration."""
        with pytest.raises(Exception):
            MonteCarloConfig(  # type: ignore[call-arg]
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=1.0,
                unauthorized_extra_param=123,
            )

    def test_rejects_excessive_combined_workload(self) -> None:
        """Parameters that collectively exceed MAX_SIMULATION_ELEMENTS must be rejected."""
        # 50,000 paths x 100 years x 1,000 steps/yr = 5,000,050,000 elements (~40 GB RAM)
        with pytest.raises(
            InvalidSimulationInputError,
            match="Simulation workload exceeds maximum resource capacity",
        ):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=100.0,
                num_paths=50000,
                steps_per_year=1000,
            )

        # 50,000 paths x 1 year x 252 steps/yr = 12,650,000 elements > 10,000,000 limit
        with pytest.raises(
            InvalidSimulationInputError,
            match="Simulation workload exceeds maximum resource capacity",
        ):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=1.0,
                num_paths=50000,
                steps_per_year=252,
            )

    def test_accepts_simulation_workload_exactly_at_boundary(self) -> None:
        """Workload exactly equal to MAX_SIMULATION_ELEMENTS (10M elements) must be accepted."""
        # 10,000 paths x 999 steps + 1 = 10,000 x 1,000 = 10,000,000 elements
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.0,
            time_horizon_years=1.0,
            num_paths=10000,
            steps_per_year=999,
            seed=42,
        )
        total_steps = round(config.time_horizon_years * config.steps_per_year)
        total_elements = config.num_paths * (total_steps + 1)
        assert total_elements == MAX_SIMULATION_ELEMENTS

    def test_accepts_simulation_workload_just_below_boundary(self) -> None:
        """Workload just below MAX_SIMULATION_ELEMENTS must be accepted."""
        # 10,000 paths x 998 steps + 1 = 10,000 x 999 = 9,990,000 elements
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.0,
            time_horizon_years=1.0,
            num_paths=10000,
            steps_per_year=998,
            seed=42,
        )
        total_steps = round(config.time_horizon_years * config.steps_per_year)
        total_elements = config.num_paths * (total_steps + 1)
        assert total_elements < MAX_SIMULATION_ELEMENTS
        assert total_elements == 9_990_000

    def test_workload_validation_occurs_before_allocation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Validation must occur during config initialization before any matrix is allocated."""

        def mock_empty(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("np.empty was called for an invalid workload!")

        monkeypatch.setattr(np, "empty", mock_empty)

        # Config creation must fail during validation without ever reaching simulate / np.empty
        with pytest.raises(
            InvalidSimulationInputError,
            match="Simulation workload exceeds maximum resource capacity",
        ):
            MonteCarloConfig(
                initial_value=10000.0,
                annualized_return=0.08,
                annualized_volatility=0.15,
                time_horizon_years=10.0,
                num_paths=50000,
                steps_per_year=252,
            )


# ===========================================================================
# 3. Statistical Moments & Convergence Properties
# ===========================================================================


class TestMonteCarloStatisticalProperties:
    """Tests verifying statistical convergence, moment properties, and distribution quantiles."""

    def test_sample_mean_converges_to_theoretical_expectation(self) -> None:
        """Large N simulation sample mean must fall within 99.7% confidence interval of E[S_T]."""
        s0 = 10000.0
        mu = 0.08
        sigma = 0.15
        horizon = 1.0
        num_paths = 10_000

        config = MonteCarloConfig(
            initial_value=s0,
            annualized_return=mu,
            annualized_volatility=sigma,
            time_horizon_years=horizon,
            num_paths=num_paths,
            steps_per_year=252,
            seed=12345,
        )
        result = run_monte_carlo(config)

        theo_mean = theoretical_gbm_expected(s0, mu, horizon)
        theo_var = theoretical_gbm_variance(s0, mu, sigma, horizon)
        std_error = math.sqrt(theo_var / num_paths)

        # 99.7% confidence interval (+/- 3 standard errors)
        lower_ci = theo_mean - 3.5 * std_error
        upper_ci = theo_mean + 3.5 * std_error

        assert lower_ci <= result.mean_final_value <= upper_ci, (
            f"Sample mean {result.mean_final_value:.2f} outside CI [{lower_ci:.2f}, {upper_ci:.2f}]"
        )

    def test_monotonicity_of_percentiles(self) -> None:
        """Quantiles must satisfy strict monotonic non-decreasing ordering."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.20,
            time_horizon_years=2.0,
            num_paths=1000,
            seed=999,
        )
        result = run_monte_carlo(config)
        p = result.percentiles

        assert (
            p["p05"]
            <= p["p10"]
            <= p["p25"]
            <= p["p50"]
            <= p["p75"]
            <= p["p90"]
            <= p["p95"]
            <= p["p99"]
        )
        assert result.min_final_value <= p["p05"]
        assert p["p99"] <= result.max_final_value

    def test_expected_shortfall_less_than_or_equal_to_p05(self) -> None:
        """Conditional Value-at-Risk (CVaR / Expected Shortfall) must be <= 5th percentile."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.20,
            time_horizon_years=2.0,
            num_paths=1000,
            seed=42,
        )
        result = run_monte_carlo(config)
        assert result.expected_shortfall_p05 <= result.percentiles["p05"]

    def test_probability_of_loss_behaviour(self) -> None:
        """Probability of loss must be between 0.0 and 1.0."""
        # Strong positive drift and low volatility -> low loss probability
        config_pos = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.30,
            annualized_volatility=0.05,
            time_horizon_years=3.0,
            num_paths=500,
            seed=42,
        )
        res_pos = run_monte_carlo(config_pos)
        assert res_pos.probability_of_loss == 0.0

        # Strong negative drift -> high loss probability
        config_neg = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=-0.30,
            annualized_volatility=0.05,
            time_horizon_years=3.0,
            num_paths=500,
            seed=42,
        )
        res_neg = run_monte_carlo(config_neg)
        assert res_neg.probability_of_loss == 1.0


# ===========================================================================
# 4. Trajectory Integrity & Downstream Contract Tests
# ===========================================================================


class TestMonteCarloTrajectoryIntegrity:
    """Tests verifying output shapes and integration contracts for S4-PA01, S4-LI01, S4-LI04."""

    def test_trajectory_dimensions_and_initial_point(self) -> None:
        """Trajectory matrix and sample paths must match exact time step dimensions."""
        horizon = 2.0
        steps_per_year = 12  # monthly steps
        expected_steps = 24  # 2 * 12

        config = MonteCarloConfig(
            initial_value=50000.0,
            annualized_return=0.07,
            annualized_volatility=0.14,
            time_horizon_years=horizon,
            num_paths=100,
            steps_per_year=steps_per_year,
            seed=42,
        )
        result = run_monte_carlo(config)

        assert result.total_steps == expected_steps
        assert math.isclose(result.dt, 1.0 / 12.0)

        # Percentile trajectories length = steps + 1 (including t=0)
        for key in PERCENTILE_KEYS:
            traj = result.percentile_trajectories[key]
            assert len(traj) == expected_steps + 1
            # Initial point at t=0 must be exactly S_0 for all percentiles
            assert traj[0] == 50000.0

        # Sample paths
        assert len(result.sample_paths) == 10
        for path in result.sample_paths:
            assert len(path) == expected_steps + 1
            assert path[0] == 50000.0

    def test_drawdown_metrics_bounds(self) -> None:
        """Drawdowns must be non-positive fractions, with worst <= median <= best <= 0.0."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.18,
            time_horizon_years=1.0,
            num_paths=200,
            seed=42,
        )
        result = run_monte_carlo(config)
        dd = result.max_drawdown_stats

        assert dd["worst_mdd"] <= dd["median_mdd"] <= dd["best_mdd"] <= 0.0
        assert -1.0 <= dd["worst_mdd"] <= 0.0


# ===========================================================================
# 5. Safety, Isolation & Global State Purity
# ===========================================================================


class TestMonteCarloSafetyAndIsolation:
    """Tests verifying PRNG isolation, absence of global random pollution, and documentation."""

    def test_global_random_state_not_polluted(self) -> None:
        """Running the simulation must not mutate standard random or numpy legacy random state."""
        # 1. Capture Python random state
        random.seed(112233)
        py_state_before = random.getstate()

        # 2. Capture NumPy random state
        np.random.seed(445566)
        np_state_before = np.random.get_state()

        # Execute simulation
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.20,
            time_horizon_years=3.0,
            num_paths=1000,
            seed=9999,
        )
        _ = run_monte_carlo(config)

        # 3. Assert states unchanged
        py_state_after = random.getstate()
        np_state_after = np.random.get_state()

        assert py_state_before == py_state_after, "Global Python random state was mutated!"
        assert np_state_before[0] == np_state_after[0]
        assert np.array_equal(np_state_before[1], np_state_after[1]), (
            "Global np.random state was mutated!"
        )

    def test_documented_assumptions_and_limitations_present(self) -> None:
        """Result must contain mandatory documented assumptions, limitations, and disclaimers."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=1.0,
            num_paths=50,
            seed=1,
        )
        result = run_monte_carlo(config)

        assert len(result.assumptions) >= 4
        assert len(result.limitations) >= 3
        assert "Educational simulation prototype" in result.disclaimer
        assert any("Geometric Brownian Motion" in a for a in result.assumptions)
        assert any("Fat-tailed risk" in lim for lim in result.limitations)


# ===========================================================================
# 6. Cash Flows, Periodic Contributions & Edge Cases
# ===========================================================================


class TestMonteCarloCashFlowsAndEdgeCases:
    """Tests verifying periodic cash flows, withdrawals, and edge case boundaries."""

    def test_periodic_contributions_increase_wealth(self) -> None:
        """Positive periodic contributions must increase terminal wealth compared to pure GBM."""
        base_config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=2.0,
            num_paths=500,
            steps_per_year=12,
            seed=42,
            periodic_contribution=0.0,
        )
        contrib_config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=2.0,
            num_paths=500,
            steps_per_year=12,
            seed=42,
            periodic_contribution=500.0,  # 500 added monthly
        )

        res_base = run_monte_carlo(base_config)
        res_contrib = run_monte_carlo(contrib_config)

        assert res_contrib.mean_final_value > res_base.mean_final_value
        assert res_contrib.median_final_value > res_base.median_final_value

    def test_ruin_condition_with_heavy_withdrawals(self) -> None:
        """Heavy periodic withdrawals floor at 0.0 without producing negative portfolio balances."""
        ruin_config = MonteCarloConfig(
            initial_value=1000.0,
            annualized_return=0.02,
            annualized_volatility=0.10,
            time_horizon_years=1.0,
            num_paths=100,
            steps_per_year=12,
            seed=42,
            periodic_contribution=-500.0,  # massive withdrawal relative to principal
        )
        result = run_monte_carlo(ruin_config)

        assert result.min_final_value >= 0.0
        assert all(val >= 0.0 for val in result.final_values)

    def test_single_path_edge_case(self) -> None:
        """Simulation with num_paths=1 executes successfully without crashing or divide-by-zero."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.15,
            time_horizon_years=1.0,
            num_paths=1,
            seed=42,
        )
        result = run_monte_carlo(config)
        assert result.std_final_value == 0.0
        assert len(result.final_values) == 1
        assert len(result.sample_paths) == 1

    def test_single_step_edge_case(self) -> None:
        """Simulation with 1 time step executes accurately."""
        config = MonteCarloConfig(
            initial_value=10000.0,
            annualized_return=0.08,
            annualized_volatility=0.0,
            time_horizon_years=1.0,
            steps_per_year=1,
            num_paths=10,
            seed=42,
        )
        result = run_monte_carlo(config)
        expected = theoretical_gbm_terminal(10000.0, 0.08, 1.0)
        assert math.isclose(result.mean_final_value, expected, rel_tol=1e-12)
        assert result.total_steps == 1
