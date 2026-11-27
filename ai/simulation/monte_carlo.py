"""Seeded Monte Carlo simulation engine with documented assumptions for FinEx.

Task: S4-MI01
Sprint: Sprint 4 — Simulated Orders, Cash Ledger & Goals (Milestone #5)
Owner: Mitali (@mitali2701)
Secondary Reviewer: Payal (@payalmude14-star)
Prerequisites: S3-PA01 (#50)
Blocks / Downstream Consumers: S4-PA01 (#64), S4-LI01 (#65), S4-LI04 (#68)

Model Overview:
---------------
This module provides a pure, deterministic, vectorized simulation engine
based on Geometric Brownian Motion (GBM) for portfolio wealth projection,
goal planning, and retirement trajectory analysis.

Mathematical Formulation:
-------------------------
1. Stochastic Differential Equation (SDE):
   dS_t = μ * S_t * dt + σ * S_t * dW_t

   where:
   - S_t: Portfolio value at time t (S_0 > 0 is initial principal)
   - μ (mu): Annualized expected continuous drift rate
   - σ (sigma): Annualized volatility (σ >= 0)
   - W_t: Standard one-dimensional Brownian motion (Wiener process)

2. Exact Vectorized Solution via Itô's Lemma:
   Under Itô's Lemma, ln(S_t) follows an arithmetic Brownian motion:
   d(ln S_t) = (μ - 0.5 * σ^2) * dt + σ * dW_t

   Discretizing over time step Δt = T / M:
   S_{t+1} = S_t * exp( (μ - 0.5 * σ^2) * Δt + σ * sqrt(Δt) * Z_t )
   where Z_t ~ N(0, 1) are independent standard normal random variates.

   Cumulative trajectory equation:
   S_k = S_0 * exp( sum_{j=1}^k [ (μ - 0.5 * σ^2) * Δt + σ * sqrt(Δt) * Z_j ] )

3. Zero-Volatility Closed-Form Oracle (Acceptance Criterion AC-2):
   When σ = 0:
   S_t = S_0 * exp(μ * t)
   At terminal horizon T:
   S_T = S_0 * exp(μ * T)
   The simulation guarantees that when σ = 0, every generated path collapses
   exactly onto this deterministic exponential trajectory with zero variance
   (within strict floating-point numerical tolerance < 1e-12).

4. Periodic Contributions / Cash Injections:
   For scenarios with periodic cash flows C (contributions/withdrawals) per step:
   S_{k+1} = (S_k + C) * exp( (μ - 0.5 * σ^2) * Δt + σ * sqrt(Δt) * Z_k )
   When C = 0, this simplifies to pure compounding GBM.

5. Seeded Reproducibility (Acceptance Criterion AC-1):
   Deterministic randomness is strictly isolated using numpy's PCG64 /
   np.random.default_rng(seed). Global random states (random.seed or np.random.seed)
   are never touched or modified. Two runs with identical seeds produce bitwise
   identical trajectories, terminal values, and summary statistics.

6. Statistical Moments & Metrics:
   - Theoretical Expectation: E[S_T] = S_0 * exp(μ * T) (when C = 0)
   - Theoretical Variance: Var(S_T) = S_0^2 * exp(2*μ*T) * (exp(σ^2*T) - 1) (when C = 0)
   - Sample Statistics: Mean, Median, Standard Deviation, Min, Max of S_T
   - Percentiles: P5, P10, P25, P50 (median), P75, P90, P95, P99
   - Percentile Trajectories: Time series of quantile values across all time steps
   - Probability of Loss: P(S_T < S_0)
   - Max Drawdown (MDD) Distribution: Pathwise peak-to-trough drawdowns

Documented Assumptions & Disclaimers:
-------------------------------------
1. Lognormal Asset Distribution: Asset returns are assumed to be independent
   and identically distributed (i.i.d.) normal increments over continuous intervals.
2. Constant Drift and Volatility: The parameters μ and σ are held constant over
   the simulation horizon. Real markets exhibit time-varying volatility clustering,
   skewness, and regime shifts.
3. Continuous Liquidity & Frictionless Rebalancing: The simulation assumes
   frictionless trading without bid-ask spreads, transaction commissions, slippage,
   liquidity constraints, or tax drag.
4. Non-Negative Portfolio Value: Under pure GBM without withdrawals, S_t > 0 for all t.
   With large net withdrawals, portfolio value may reach zero (ruin condition).
5. Educational Prototype: All outputs are educational simulation projections
   and do not constitute financial advice, performance guarantees, or solicitations.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STEPS_PER_YEAR = 252  # Standard annual trading days
DEFAULT_NUM_PATHS = 1000
MAX_NUM_PATHS = 50_000
MAX_HORIZON_YEARS = 100.0
MAX_STEPS_PER_YEAR = 1000
MIN_INITIAL_VALUE = 0.01

PERCENTILE_LEVELS: tuple[float, ...] = (5.0, 10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 99.0)
PERCENTILE_KEYS: tuple[str, ...] = (
    "p05",
    "p10",
    "p25",
    "p50",
    "p75",
    "p90",
    "p95",
    "p99",
)

DOCUMENTED_ASSUMPTIONS: tuple[str, ...] = (
    "Geometric Brownian Motion (GBM) dynamics with log-normal asset price distributions.",
    "Constant annualized drift rate (mu) and constant annualized volatility (sigma).",
    "Independent and identically distributed (i.i.d.) normal return increments per time step.",
    "Frictionless market conditions: no transaction costs, slippage, exchange fees, or taxes.",
    "Continuous liquidity and instantaneous execution at continuous market prices.",
)

DOCUMENTED_LIMITATIONS: tuple[str, ...] = (
    "Fat-tailed risk (kurtosis) and extreme market tail events are underestimated by standard normal increments.",
    "Volatility clustering, leverage effects, and macroeconomic regime shifts are not modeled.",
    "Fixed parameters cannot predict forward-looking monetary policy, inflation spikes, or structural shifts.",
    "Historical or assumed parameters are not indicative of future investment returns.",
)

DISCLAIMER_TEXT: str = (
    "Educational simulation prototype only. Projections are hypothetical, mathematically modeled "
    "estimates and do not constitute financial advice, investment recommendations, or performance guarantees."
)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------


class MonteCarloError(Exception):
    """Base domain exception for Monte Carlo simulation engine."""


class InvalidSimulationInputError(MonteCarloError):
    """Raised when simulation parameters are invalid, non-finite, out of bounds, or booleans."""


class NumericalInstabilityError(MonteCarloError):
    """Raised when floating-point overflow or extreme numerical divergence occurs."""


# ---------------------------------------------------------------------------
# Enums and Configuration Models
# ---------------------------------------------------------------------------


class CompoundingConvention(str, Enum):
    """Compounding frequency convention for annualized parameters."""

    CONTINUOUS = "continuous"
    ANNUAL_DISCRETE = "annual_discrete"


class MonteCarloConfig(BaseModel):
    """Immutable, strictly validated configuration for Monte Carlo simulation.

    Attributes:
        initial_value: Initial investment principal S_0 (must be > 0).
        annualized_return: Expected annualized drift / return (mu, e.g. 0.08 for 8%).
        annualized_volatility: Annualized return volatility (sigma >= 0, e.g. 0.15 for 15%).
        time_horizon_years: Investment horizon in years (T > 0).
        num_paths: Number of simulated trajectories to generate (N >= 1).
        steps_per_year: Discretization intervals per year (e.g. 252 daily, 12 monthly).
        seed: Random seed for deterministic reproducibility. If None, a system seed is used.
        periodic_contribution: Fixed cash injection per time step (default 0.0).
        compounding: Compounding convention (continuous or annual discrete).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    initial_value: float = Field(
        ...,
        description="Initial investment portfolio principal value S_0 (must be positive).",
    )
    annualized_return: float = Field(
        ...,
        description="Expected annualized continuous drift rate mu (e.g. 0.08 for 8%).",
    )
    annualized_volatility: float = Field(
        ...,
        description="Annualized return standard deviation sigma (must be non-negative).",
    )
    time_horizon_years: float = Field(
        ...,
        description="Simulation time horizon in years T (must be positive).",
    )
    num_paths: int = Field(
        default=DEFAULT_NUM_PATHS,
        description="Number of stochastic simulation trajectories (1 <= N <= 50,000).",
    )
    steps_per_year: int = Field(
        default=DEFAULT_STEPS_PER_YEAR,
        description="Discretization steps per calendar year (1 <= steps <= 1000).",
    )
    seed: int | None = Field(
        default=None,
        description="Deterministic integer seed for PCG64 PRNG reproducibility.",
    )
    periodic_contribution: float = Field(
        default=0.0,
        description="Fixed cash contribution (+) or withdrawal (-) per time step.",
    )
    compounding: CompoundingConvention = Field(
        default=CompoundingConvention.CONTINUOUS,
        description="Compounding convention for drift interpretation.",
    )

    @field_validator(
        "initial_value",
        "annualized_return",
        "annualized_volatility",
        "time_horizon_years",
        "periodic_contribution",
        mode="before",
    )
    @classmethod
    def validate_finite_floats(cls, v: Any, info: Any) -> float:
        """Validate that numeric inputs are genuine finite floats and not booleans."""
        if isinstance(v, bool):
            raise InvalidSimulationInputError(
                f"Field '{info.field_name}' must be a float, got boolean {v!r}"
            )
        try:
            val = float(v)
        except (TypeError, ValueError) as exc:
            raise InvalidSimulationInputError(
                f"Field '{info.field_name}' must be a numeric value, got {v!r}"
            ) from exc

        if not math.isfinite(val):
            raise InvalidSimulationInputError(
                f"Field '{info.field_name}' must be a finite number, got {val!r}"
            )
        return val

    @field_validator("num_paths", "steps_per_year", mode="before")
    @classmethod
    def validate_positive_integers(cls, v: Any, info: Any) -> int:
        """Validate that integer count fields are genuine positive ints and not booleans."""
        if isinstance(v, bool):
            raise InvalidSimulationInputError(
                f"Field '{info.field_name}' must be an integer, got boolean {v!r}"
            )
        try:
            val = int(v)
        except (TypeError, ValueError) as exc:
            raise InvalidSimulationInputError(
                f"Field '{info.field_name}' must be an integer, got {v!r}"
            ) from exc

        if val != float(v):
            raise InvalidSimulationInputError(
                f"Field '{info.field_name}' must be a whole integer, got {v!r}"
            )
        return val

    @field_validator("seed", mode="before")
    @classmethod
    def validate_seed(cls, v: Any) -> int | None:
        """Validate optional PRNG seed."""
        if v is None:
            return None
        if isinstance(v, bool):
            raise InvalidSimulationInputError(
                f"Seed must be an integer or None, got boolean {v!r}"
            )
        try:
            seed_val = int(v)
        except (TypeError, ValueError) as exc:
            raise InvalidSimulationInputError(
                f"Seed must be an integer or None, got {v!r}"
            ) from exc

        if seed_val < 0 or seed_val >= 2**63 - 1:
            raise InvalidSimulationInputError(
                f"Seed must be in range [0, 2^63 - 2], got {seed_val}"
            )
        return seed_val

    @model_validator(mode="after")
    def validate_simulation_bounds(self) -> MonteCarloConfig:
        """Validate cross-field mathematical constraints and boundary limits."""
        if self.initial_value <= 0.0:
            raise InvalidSimulationInputError(
                f"Initial value must be strictly positive (> 0), got {self.initial_value}"
            )
        if self.annualized_volatility < 0.0:
            raise InvalidSimulationInputError(
                f"Annualized volatility must be non-negative (>= 0), got {self.annualized_volatility}"
            )
        if self.time_horizon_years <= 0.0:
            raise InvalidSimulationInputError(
                f"Time horizon must be strictly positive (> 0), got {self.time_horizon_years}"
            )
        if self.time_horizon_years > MAX_HORIZON_YEARS:
            raise InvalidSimulationInputError(
                f"Time horizon cannot exceed {MAX_HORIZON_YEARS} years, got {self.time_horizon_years}"
            )
        if self.num_paths < 1 or self.num_paths > MAX_NUM_PATHS:
            raise InvalidSimulationInputError(
                f"Number of paths must be between 1 and {MAX_NUM_PATHS}, got {self.num_paths}"
            )
        if self.steps_per_year < 1 or self.steps_per_year > MAX_STEPS_PER_YEAR:
            raise InvalidSimulationInputError(
                f"Steps per year must be between 1 and {MAX_STEPS_PER_YEAR}, got {self.steps_per_year}"
            )
        if abs(self.annualized_return) > 20.0:
            raise InvalidSimulationInputError(
                f"Annualized return parameter exceeds sensible numerical bounds (|mu| <= 20.0), got {self.annualized_return}"
            )
        if self.annualized_volatility > 20.0:
            raise InvalidSimulationInputError(
                f"Annualized volatility parameter exceeds sensible numerical bounds (sigma <= 20.0), got {self.annualized_volatility}"
            )
        return self


# ---------------------------------------------------------------------------
# Output / Result Schema
# ---------------------------------------------------------------------------


class MonteCarloResult(BaseModel):
    """Comprehensive, immutable output model representing a complete simulation run.

    Provides summary moments, quantile trajectories for plotting, path statistics,
    risk metrics, and explicit assumptions and limitations.
    """

    model_config = ConfigDict(frozen=True)

    config: MonteCarloConfig = Field(
        ..., description="The configuration used for this simulation."
    )
    actual_seed: int = Field(
        ..., description="The concrete PRNG seed used for the run."
    )
    total_steps: int = Field(
        ..., description="Total discrete time steps M = round(T * steps_per_year)."
    )
    dt: float = Field(..., description="Discretization step size Δt = T / M in years.")

    mean_final_value: float = Field(
        ..., description="Sample mean terminal wealth across all simulated paths."
    )
    median_final_value: float = Field(
        ..., description="Sample median (50th percentile) terminal wealth."
    )
    std_final_value: float = Field(
        ..., description="Sample standard deviation of terminal wealth."
    )
    min_final_value: float = Field(
        ..., description="Minimum terminal wealth observed across all paths."
    )
    max_final_value: float = Field(
        ..., description="Maximum terminal wealth observed across all paths."
    )

    theoretical_expected_value: float = Field(
        ...,
        description="Analytical expected value S_0 * exp(mu * T) (closed-form continuous benchmark).",
    )
    theoretical_variance: float | None = Field(
        default=None,
        description="Analytical variance Var(S_T) under pure GBM, or None if periodic flows present.",
    )

    percentiles: dict[str, float] = Field(
        ...,
        description="Terminal wealth percentiles (p05, p10, p25, p50, p75, p90, p95, p99).",
    )
    probability_of_loss: float = Field(
        ...,
        description="Fraction of paths whose terminal wealth is less than initial principal S_0.",
    )
    expected_shortfall_p05: float = Field(
        ...,
        description="Conditional Value-at-Risk / CVaR: mean terminal wealth among paths <= 5th percentile.",
    )

    max_drawdown_stats: dict[str, float] = Field(
        ...,
        description="Summary statistics of pathwise maximum drawdowns (mean, median, worst).",
    )

    percentile_trajectories: dict[str, list[float]] = Field(
        ...,
        description="Time series of quantile values at each discrete step (t_0 through t_M).",
    )
    sample_paths: list[list[float]] = Field(
        ...,
        description="Representative sample trajectories for visual chart inspection (up to 10 paths).",
    )
    final_values: list[float] = Field(
        ...,
        description="List of terminal wealth values S_T for all N paths (for histograms / distributions).",
    )

    assumptions: list[str] = Field(
        default_factory=lambda: list(DOCUMENTED_ASSUMPTIONS),
        description="List of core financial and mathematical assumptions underlying the model.",
    )
    limitations: list[str] = Field(
        default_factory=lambda: list(DOCUMENTED_LIMITATIONS),
        description="Known limitations and risks of the simulation approach.",
    )
    disclaimer: str = Field(
        default=DISCLAIMER_TEXT,
        description="Mandatory educational prototype and financial safety disclaimer.",
    )


# ---------------------------------------------------------------------------
# Closed-Form Analytical Oracles
# ---------------------------------------------------------------------------


def theoretical_gbm_terminal(
    initial_value: float,
    annualized_return: float,
    time_horizon_years: float,
    compounding: CompoundingConvention = CompoundingConvention.CONTINUOUS,
) -> float:
    """Calculate the exact theoretical terminal value in the absence of volatility.

    When sigma = 0:
    - Continuous: S_T = S_0 * exp(mu * T)
    - Annual Discrete: S_T = S_0 * (1 + r)^T

    Args:
        initial_value: Initial portfolio principal S_0 > 0.
        annualized_return: Expected annualized drift rate mu.
        time_horizon_years: Horizon T in years.
        compounding: Continuous or annual discrete compounding convention.

    Returns:
        Exact analytical terminal portfolio value.
    """
    if initial_value <= 0.0:
        raise InvalidSimulationInputError(
            f"Initial value must be > 0, got {initial_value}"
        )
    if time_horizon_years < 0.0:
        raise InvalidSimulationInputError(
            f"Time horizon cannot be negative, got {time_horizon_years}"
        )

    if time_horizon_years == 0.0:
        return float(initial_value)

    if compounding == CompoundingConvention.CONTINUOUS:
        exponent = annualized_return * time_horizon_years
        if exponent > 700.0:
            raise NumericalInstabilityError(
                f"Exponential overflow in theoretical terminal calculation: exp({exponent})"
            )
        return float(initial_value * math.exp(exponent))
    else:
        base = 1.0 + annualized_return
        if base < 0.0:
            raise InvalidSimulationInputError(
                f"Annual discrete compounding requires (1 + return) >= 0, got base {base}"
            )
        return float(initial_value * (base**time_horizon_years))


def theoretical_gbm_expected(
    initial_value: float,
    annualized_return: float,
    time_horizon_years: float,
) -> float:
    """Calculate theoretical expected wealth E[S_T] for a GBM process.

    Under continuous GBM dS = mu * S * dt + sigma * S * dW:
    E[S_T] = S_0 * exp(mu * T)
    (Note that the expected value is independent of volatility sigma).
    """
    return theoretical_gbm_terminal(
        initial_value=initial_value,
        annualized_return=annualized_return,
        time_horizon_years=time_horizon_years,
        compounding=CompoundingConvention.CONTINUOUS,
    )


def theoretical_gbm_variance(
    initial_value: float,
    annualized_return: float,
    annualized_volatility: float,
    time_horizon_years: float,
) -> float:
    """Calculate theoretical variance Var(S_T) for a pure GBM process.

    Var(S_T) = S_0^2 * exp(2 * mu * T) * (exp(sigma^2 * T) - 1)
    When sigma = 0, Var(S_T) = 0 exactly.
    """
    if annualized_volatility < 0.0:
        raise InvalidSimulationInputError("Volatility cannot be negative.")
    if annualized_volatility == 0.0 or time_horizon_years == 0.0:
        return 0.0

    exp_term = 2.0 * annualized_return * time_horizon_years
    vol_term = (annualized_volatility**2) * time_horizon_years

    if exp_term + vol_term > 700.0:
        raise NumericalInstabilityError(
            "Numerical overflow in theoretical variance calculation."
        )

    expected_sq = (initial_value**2) * math.exp(exp_term)
    var_mult = math.expm1(vol_term)  # exp(x) - 1 with high precision near zero
    return float(expected_sq * var_mult)


# ---------------------------------------------------------------------------
# Core Simulation Engine
# ---------------------------------------------------------------------------


class MonteCarloEngine:
    """Pure, deterministic, non-networked Monte Carlo simulation engine."""

    def __init__(self, config: MonteCarloConfig) -> None:
        """Initialize engine with a verified configuration.

        Args:
            config: A validated MonteCarloConfig instance.
        """
        self.config = config

    def simulate(self) -> MonteCarloResult:
        """Execute the vectorized Monte Carlo simulation.

        Returns:
            A populated, immutable MonteCarloResult object containing trajectories,
            statistics, percentiles, drawdown distribution, and documented assumptions.
        """
        cfg = self.config
        total_steps = max(1, round(cfg.time_horizon_years * cfg.steps_per_year))
        dt = cfg.time_horizon_years / float(total_steps)

        # Determine effective drift per step based on compounding convention
        if cfg.compounding == CompoundingConvention.CONTINUOUS:
            mu_continuous = cfg.annualized_return
        else:
            # Convert discrete annual return r to continuous log-drift: mu = ln(1 + r)
            if cfg.annualized_return <= -1.0:
                raise InvalidSimulationInputError(
                    f"Discrete annual return must be > -1.0, got {cfg.annualized_return}"
                )
            mu_continuous = math.log(1.0 + cfg.annualized_return)

        # Handle Seed Isolation (AC-1)
        # We explicitly resolve or generate the seed, using an isolated PRNG generator.
        if cfg.seed is not None:
            actual_seed = cfg.seed
        else:
            # Derive deterministic-looking system seed from OS entropy without touching global RNG
            seed_gen = np.random.default_rng()
            actual_seed = int(seed_gen.integers(0, 2**63 - 1))

        rng = np.random.default_rng(actual_seed)

        # Allocate trajectory matrix: shape (num_paths, total_steps + 1)
        # trajectories[:, 0] = S_0
        trajectories = np.empty((cfg.num_paths, total_steps + 1), dtype=np.float64)
        trajectories[:, 0] = cfg.initial_value

        sigma = cfg.annualized_volatility
        c = cfg.periodic_contribution

        # -------------------------------------------------------------------
        # Zero-Volatility Analytical Path (Acceptance Criterion AC-2)
        # -------------------------------------------------------------------
        if sigma == 0.0:
            if c == 0.0:
                # Pure exponential closed form: S(t_k) = S_0 * exp(mu * t_k)
                time_points = np.linspace(0.0, cfg.time_horizon_years, total_steps + 1)
                time_points[0] = 0.0
                time_points[-1] = cfg.time_horizon_years
                deterministic_path = cfg.initial_value * np.exp(
                    mu_continuous * time_points
                )
                deterministic_path[-1] = cfg.initial_value * math.exp(
                    mu_continuous * cfg.time_horizon_years
                )
                # Broadcast across all paths
                trajectories[:, :] = deterministic_path
            else:
                # Step-by-step exact compounding with periodic cash flow
                growth_factor = math.exp(mu_continuous * dt)
                current_values = np.full(
                    cfg.num_paths, cfg.initial_value, dtype=np.float64
                )
                for step in range(1, total_steps + 1):
                    current_values = (current_values + c) * growth_factor
                    # Floor at 0.0 to represent financial ruin under withdrawals
                    np.maximum(current_values, 0.0, out=current_values)
                    trajectories[:, step] = current_values
        else:
            # ---------------------------------------------------------------
            # Stochastic GBM Vectorized Path Generation
            # ---------------------------------------------------------------
            drift_step = (mu_continuous - 0.5 * (sigma**2)) * dt
            diffusion_step = sigma * math.sqrt(dt)

            if c == 0.0:
                # Fully vectorized across all paths and steps simultaneously
                # Standard normal shocks: Z ~ N(0, 1), shape (num_paths, total_steps)
                z_shocks = rng.standard_normal(
                    size=(cfg.num_paths, total_steps), dtype=np.float64
                )
                log_returns = drift_step + diffusion_step * z_shocks

                # Cumulative log returns
                np.cumsum(log_returns, axis=1, out=log_returns)

                # Check for numerical overflow before exp
                max_log = np.max(log_returns)
                if max_log > 700.0:
                    raise NumericalInstabilityError(
                        f"Numerical overflow encountered: max cumulative log return {max_log:.2f} > 700"
                    )

                trajectories[:, 1:] = cfg.initial_value * np.exp(log_returns)
            else:
                # Step-by-step iteration for paths with periodic cash injections / withdrawals
                current_values = np.full(
                    cfg.num_paths, cfg.initial_value, dtype=np.float64
                )
                for step in range(1, total_steps + 1):
                    z_shocks_step = rng.standard_normal(
                        size=cfg.num_paths, dtype=np.float64
                    )
                    step_factor = np.exp(drift_step + diffusion_step * z_shocks_step)
                    current_values = (current_values + c) * step_factor
                    # Floor at 0.0 if ruined
                    np.maximum(current_values, 0.0, out=current_values)
                    trajectories[:, step] = current_values

        # -------------------------------------------------------------------
        # Summary Moments & Distribution Metrics
        # -------------------------------------------------------------------
        final_values_arr = trajectories[:, -1]

        # Check for non-finite values in output
        if not np.all(np.isfinite(final_values_arr)):
            raise NumericalInstabilityError(
                "Non-finite values encountered in simulated terminal wealth array."
            )

        min_final = float(np.min(final_values_arr))
        max_final = float(np.max(final_values_arr))
        if min_final == max_final or sigma == 0.0:
            mean_final = min_final
            median_final = min_final
            std_final = 0.0
        else:
            mean_final = float(np.mean(final_values_arr))
            median_final = float(np.median(final_values_arr))
            std_final = (
                float(np.std(final_values_arr, ddof=1)) if cfg.num_paths > 1 else 0.0
            )

        # Closed form reference
        if c == 0.0:
            theo_expected = theoretical_gbm_expected(
                initial_value=cfg.initial_value,
                annualized_return=mu_continuous,
                time_horizon_years=cfg.time_horizon_years,
            )
            theo_variance = theoretical_gbm_variance(
                initial_value=cfg.initial_value,
                annualized_return=mu_continuous,
                annualized_volatility=sigma,
                time_horizon_years=cfg.time_horizon_years,
            )
        else:
            theo_expected = mean_final
            theo_variance = None

        # Terminal wealth percentiles
        percentile_values = np.percentile(final_values_arr, PERCENTILE_LEVELS)
        percentiles_dict: dict[str, float] = {
            k: float(v) for k, v in zip(PERCENTILE_KEYS, percentile_values)
        }

        # Probability of capital loss: P(S_T < S_0)
        num_loss = int(np.sum(final_values_arr < cfg.initial_value))
        prob_loss = float(num_loss / cfg.num_paths)

        # Expected Shortfall (CVaR) at 5th percentile
        p05_threshold = percentiles_dict["p05"]
        tail_losses = final_values_arr[final_values_arr <= p05_threshold]
        expected_shortfall = (
            float(np.mean(tail_losses)) if len(tail_losses) > 0 else p05_threshold
        )

        # -------------------------------------------------------------------
        # Pathwise Maximum Drawdown (MDD) Distribution
        # -------------------------------------------------------------------
        # Running peaks across time steps: shape (num_paths, total_steps + 1)
        running_peaks = np.maximum.accumulate(trajectories, axis=1)
        # Avoid division by zero if running peak is zero
        safe_peaks = np.where(running_peaks == 0.0, 1.0, running_peaks)
        drawdowns = (trajectories - running_peaks) / safe_peaks  # <= 0
        path_mdds = np.min(drawdowns, axis=1)  # minimum drawdown per path (negative)

        max_drawdown_stats: dict[str, float] = {
            "mean_mdd": float(np.mean(path_mdds)),
            "median_mdd": float(np.median(path_mdds)),
            "worst_mdd": float(np.min(path_mdds)),
            "best_mdd": float(np.max(path_mdds)),
        }

        # -------------------------------------------------------------------
        # Quantile Trajectories Across All Time Steps
        # -------------------------------------------------------------------
        # Compute percentiles across paths at each step k
        percentile_trajectories: dict[str, list[float]] = {}
        trajectory_percentiles = np.percentile(trajectories, PERCENTILE_LEVELS, axis=0)
        for idx, k in enumerate(PERCENTILE_KEYS):
            percentile_trajectories[k] = [
                float(val) for val in trajectory_percentiles[idx]
            ]

        # Up to 10 sample paths for plotting spaghetti curves
        sample_path_count = min(10, cfg.num_paths)
        sample_paths = [
            [float(val) for val in trajectories[i]] for i in range(sample_path_count)
        ]

        final_values_list = [float(val) for val in final_values_arr]

        return MonteCarloResult(
            config=cfg,
            actual_seed=actual_seed,
            total_steps=total_steps,
            dt=dt,
            mean_final_value=mean_final,
            median_final_value=median_final,
            std_final_value=std_final,
            min_final_value=min_final,
            max_final_value=max_final,
            theoretical_expected_value=theo_expected,
            theoretical_variance=theo_variance,
            percentiles=percentiles_dict,
            probability_of_loss=prob_loss,
            expected_shortfall_p05=expected_shortfall,
            max_drawdown_stats=max_drawdown_stats,
            percentile_trajectories=percentile_trajectories,
            sample_paths=sample_paths,
            final_values=final_values_list,
        )


def run_monte_carlo(config: MonteCarloConfig) -> MonteCarloResult:
    """Convenience helper to initialize engine and execute simulation.

    Args:
        config: Validated MonteCarloConfig instance.

    Returns:
        MonteCarloResult containing complete simulation output.
    """
    engine = MonteCarloEngine(config)
    return engine.simulate()
