"""Comprehensive unit, invariant, and persona tests for SuitabilityService (S3-LI01)."""

from decimal import Decimal

import pytest
from ai.risk.schemas import QuestionAnswer

from app.schemas.suitability import (
    CurrentAllocationItem,
    RiskCategoryEnum,
    SuitabilityRebalanceRequest,
)
from app.services.suitability_service import (
    ALLOCATION_TARGETS,
    SuitabilityException,
    SuitabilityService,
    suitability_service,
)

# ==============================================================================
# A. Risk Scoring Integration Tests
# ==============================================================================


def test_resolve_risk_category_from_direct_string() -> None:
    service = SuitabilityService()
    assert (
        service.resolve_risk_category(risk_category="CONSERVATIVE")[0]
        == RiskCategoryEnum.CONSERVATIVE
    )
    assert service.resolve_risk_category(risk_category="moderate")[0] == RiskCategoryEnum.MODERATE
    assert (
        service.resolve_risk_category(risk_category="Aggressive_V1")[0]
        == RiskCategoryEnum.AGGRESSIVE
    )


def test_resolve_risk_category_unsupported_string_raises() -> None:
    service = SuitabilityService()
    with pytest.raises(SuitabilityException, match="Unsupported risk category"):
        service.resolve_risk_category(risk_category="SPECULATIVE")


def test_resolve_risk_category_missing_inputs_raises() -> None:
    service = SuitabilityService()
    with pytest.raises(
        SuitabilityException, match="Either 'risk_category' or 'questionnaire_answers'"
    ):
        service.resolve_risk_category()


def test_resolve_risk_category_from_questionnaire_answers() -> None:
    service = SuitabilityService()
    # Canonical Conservative answers: lowest risk options across W1-W5, C1-C5
    conservative_answers = [
        QuestionAnswer(question_id=f"W{i}", answer_code=f"W{i}_A") for i in range(1, 6)
    ] + [QuestionAnswer(question_id=f"C{i}", answer_code=f"C{i}_A") for i in range(1, 6)]

    cat, summary = service.resolve_risk_category(questionnaire_answers=conservative_answers)
    assert cat == RiskCategoryEnum.CONSERVATIVE
    assert summary is not None
    assert summary["category"] == "Conservative"
    assert "composite_score" in summary
    assert "dimension_scores" in summary


# ==============================================================================
# B. Allocation Correctness & Invariant Tests
# ==============================================================================


@pytest.mark.parametrize(
    "category",
    [RiskCategoryEnum.CONSERVATIVE, RiskCategoryEnum.MODERATE, RiskCategoryEnum.AGGRESSIVE],
)
def test_target_allocation_invariants_per_category(category: RiskCategoryEnum) -> None:
    service = SuitabilityService()
    resp = service.get_target_allocation(category)

    assert resp.risk_category == category.value
    assert resp.invariants_satisfied is True
    assert len(resp.allocations) == 3

    weights_sum = Decimal("0.0")
    asset_classes = set()
    for item in resp.allocations:
        assert item.target_weight >= Decimal("0.0")
        assert item.target_weight <= Decimal("1.0")
        assert not item.target_weight.is_nan()
        assert not item.target_weight.is_infinite()
        assert item.target_pct == item.target_weight * Decimal("100.0")
        assert item.benchmark_symbol in ("SPY", "AGG", "CSHX")
        weights_sum += item.target_weight
        asset_classes.add(item.asset_class)

    assert asset_classes == {"EQUITY", "FIXED_INCOME", "CASH"}
    assert weights_sum == Decimal("1.000000")


def test_equity_monotonicity_across_categories() -> None:
    service = SuitabilityService()
    resp_cons = service.get_target_allocation(RiskCategoryEnum.CONSERVATIVE)
    resp_mod = service.get_target_allocation(RiskCategoryEnum.MODERATE)
    resp_agg = service.get_target_allocation(RiskCategoryEnum.AGGRESSIVE)

    eq_cons = next(a.target_weight for a in resp_cons.allocations if a.asset_class == "EQUITY")
    eq_mod = next(a.target_weight for a in resp_mod.allocations if a.asset_class == "EQUITY")
    eq_agg = next(a.target_weight for a in resp_agg.allocations if a.asset_class == "EQUITY")

    assert eq_cons == Decimal("0.200000")
    assert eq_mod == Decimal("0.500000")
    assert eq_agg == Decimal("0.800000")
    assert eq_cons < eq_mod < eq_agg


def test_invariants_validation_rejects_negative_and_unreconciled_weights() -> None:
    service = SuitabilityService()
    with pytest.raises(SuitabilityException, match="must be non-negative"):
        service.validate_allocation_invariants({"EQUITY": Decimal("-0.1"), "CASH": Decimal("1.1")})

    with pytest.raises(SuitabilityException, match="must sum to 1.0"):
        service.validate_allocation_invariants({"EQUITY": Decimal("0.5"), "CASH": Decimal("0.4")})


# ==============================================================================
# C. Property-Based Invariant Tests
# ==============================================================================


def test_property_all_models_sum_to_one() -> None:
    for model_code, targets in ALLOCATION_TARGETS.items():
        total = sum(targets.values())
        assert total == Decimal("1.000000"), f"Model {model_code} does not sum to 1.0"
        for ac, w in targets.items():
            assert w >= Decimal("0.0"), f"{ac} in {model_code} is negative"


def test_property_drift_sum_equals_zero_for_normalized_portfolios() -> None:
    service = SuitabilityService()
    target_map = ALLOCATION_TARGETS["MODERATE_V1"]

    # Test arbitrary valid portfolio distributions
    test_distributions = [
        {"EQUITY": Decimal("0.3"), "FIXED_INCOME": Decimal("0.5"), "CASH": Decimal("0.2")},
        {"EQUITY": Decimal("0.7"), "FIXED_INCOME": Decimal("0.2"), "CASH": Decimal("0.1")},
        {"EQUITY": Decimal("0.5"), "FIXED_INCOME": Decimal("0.4"), "CASH": Decimal("0.1")},
        {"EQUITY": Decimal("0.0"), "FIXED_INCOME": Decimal("0.0"), "CASH": Decimal("1.0")},
    ]

    for curr in test_distributions:
        drift_items, _, _ = service.calculate_drift(curr, target_map)
        drift_sum = sum((item.drift for item in drift_items), Decimal("0"))
        assert abs(drift_sum) < Decimal("0.000001"), f"Drift sum {drift_sum} != 0 for {curr}"

        plan = service.generate_rebalance_plan(drift_items, portfolio_value=Decimal("100000.00"))
        amount_sum = sum(
            (item.indicative_amount for item in plan if item.indicative_amount is not None),
            Decimal("0"),
        )
        assert abs(amount_sum) <= Decimal("0.02"), f"Rebalance monetary sum {amount_sum} != 0"


# ==============================================================================
# D. Drift Calculation Tests
# ==============================================================================


def test_drift_on_target_is_balanced_and_hold() -> None:
    service = SuitabilityService()
    target = {"EQUITY": Decimal("0.5"), "FIXED_INCOME": Decimal("0.4"), "CASH": Decimal("0.1")}
    current = {"EQUITY": Decimal("0.5"), "FIXED_INCOME": Decimal("0.4"), "CASH": Decimal("0.1")}

    drift_items, max_drift, rebal_req = service.calculate_drift(current, target)
    assert max_drift == Decimal("0.0")
    assert rebal_req is False
    assert all(item.status == "BALANCED" for item in drift_items)
    assert all(item.action == "HOLD" for item in drift_items)


def test_drift_overweight_and_underweight_identification() -> None:
    service = SuitabilityService()
    target = {"EQUITY": Decimal("0.2"), "FIXED_INCOME": Decimal("0.7"), "CASH": Decimal("0.1")}
    current = {"EQUITY": Decimal("0.5"), "FIXED_INCOME": Decimal("0.4"), "CASH": Decimal("0.1")}

    drift_items, max_drift, rebal_req = service.calculate_drift(current, target)
    assert rebal_req is True
    assert max_drift == Decimal("0.3")

    drift_by_ac = {item.asset_class: item for item in drift_items}
    assert drift_by_ac["EQUITY"].drift == Decimal("0.3")
    assert drift_by_ac["EQUITY"].status == "OVERWEIGHT"
    assert drift_by_ac["EQUITY"].action == "REDUCE"

    assert drift_by_ac["FIXED_INCOME"].drift == Decimal("-0.3")
    assert drift_by_ac["FIXED_INCOME"].status == "UNDERWEIGHT"
    assert drift_by_ac["FIXED_INCOME"].action == "INCREASE"

    assert drift_by_ac["CASH"].drift == Decimal("0.0")
    assert drift_by_ac["CASH"].status == "BALANCED"
    assert drift_by_ac["CASH"].action == "HOLD"


def test_drift_with_untracked_asset_class_retained() -> None:
    service = SuitabilityService()
    target = {"EQUITY": Decimal("0.5"), "FIXED_INCOME": Decimal("0.4"), "CASH": Decimal("0.1")}
    # Portfolio contains CRYPTO not in target
    current = {
        "EQUITY": Decimal("0.4"),
        "FIXED_INCOME": Decimal("0.4"),
        "CASH": Decimal("0.1"),
        "CRYPTO": Decimal("0.1"),
    }

    drift_items, max_drift, rebal_req = service.calculate_drift(current, target)
    drift_by_ac = {item.asset_class: item for item in drift_items}

    assert "CRYPTO" in drift_by_ac
    assert drift_by_ac["CRYPTO"].target_weight == Decimal("0.0")
    assert drift_by_ac["CRYPTO"].drift == Decimal("0.1")
    assert drift_by_ac["CRYPTO"].status == "OVERWEIGHT"
    assert drift_by_ac["CRYPTO"].action == "REDUCE"


# ==============================================================================
# E. Persona Golden Cases
# ==============================================================================


def test_persona_1_retired_capital_preservation_conservative() -> None:
    """Persona 1: Aarav (Retired / Conservative)

    Target: Conservative (20% Equity, 70% Fixed Income, 10% Cash)
    Current: $100k (50% Equity, 30% Fixed Income, 20% Cash)
    Expected:
      - Equity: 30% overweight -> REDUCE by $30,000
      - Fixed Income: 40% underweight -> INCREASE by $40,000 via AGG
      - Cash: 10% overweight -> REDUCE by $10,000
    """
    req = SuitabilityRebalanceRequest(
        risk_category="CONSERVATIVE",
        current_allocation=[
            CurrentAllocationItem(
                asset_class="EQUITY", weight=Decimal("0.50"), value=Decimal("50000.00")
            ),
            CurrentAllocationItem(
                asset_class="FIXED_INCOME", weight=Decimal("0.30"), value=Decimal("30000.00")
            ),
            CurrentAllocationItem(
                asset_class="CASH", weight=Decimal("0.20"), value=Decimal("20000.00")
            ),
        ],
        portfolio_value=Decimal("100000.00"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    assert res.risk_category == "CONSERVATIVE"
    assert res.rebalance_required is True
    assert res.is_empty_portfolio is False

    plan_by_ac = {p.asset_class: p for p in res.rebalance_plan}
    assert plan_by_ac["EQUITY"].direction == "REDUCE"
    assert plan_by_ac["EQUITY"].indicative_amount == Decimal("-30000.00")

    assert plan_by_ac["FIXED_INCOME"].direction == "INCREASE"
    assert plan_by_ac["FIXED_INCOME"].indicative_amount == Decimal("40000.00")
    assert plan_by_ac["FIXED_INCOME"].benchmark_symbol == "AGG"

    assert plan_by_ac["CASH"].direction == "REDUCE"
    assert plan_by_ac["CASH"].indicative_amount == Decimal("-10000.00")


def test_persona_2_mid_career_balanced_moderate() -> None:
    """Persona 2: Priya (Mid-Career / Moderate)

    Target: Moderate (50% Equity, 40% Fixed Income, 10% Cash)
    Current: $50k (50% Equity, 40% Fixed Income, 10% Cash)
    Expected:
      - All allocations balanced on target
      - rebalance_required is False
    """
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(
                asset_class="EQUITY", weight=Decimal("0.50"), value=Decimal("25000.00")
            ),
            CurrentAllocationItem(
                asset_class="FIXED_INCOME", weight=Decimal("0.40"), value=Decimal("20000.00")
            ),
            CurrentAllocationItem(
                asset_class="CASH", weight=Decimal("0.10"), value=Decimal("5000.00")
            ),
        ],
        portfolio_value=Decimal("50000.00"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    assert res.risk_category == "MODERATE"
    assert res.rebalance_required is False
    assert res.max_drift == Decimal("0.0")
    for p in res.rebalance_plan:
        assert p.direction == "HOLD"
        assert p.indicative_amount == Decimal("0.00")


def test_persona_3_early_career_growth_aggressive() -> None:
    """Persona 3: Rohan (Early-Career / Aggressive)

    Target: Aggressive (80% Equity, 10% Fixed Income, 10% Cash)
    Current: $200k (60% Equity, 30% Fixed Income, 10% Cash)
    Expected:
      - Equity: 20% underweight -> INCREASE by $40,000 via SPY
      - Fixed Income: 20% overweight -> REDUCE by $40,000
      - Cash: on target -> HOLD
    """
    req = SuitabilityRebalanceRequest(
        risk_category="AGGRESSIVE",
        current_allocation=[
            CurrentAllocationItem(
                asset_class="EQUITY", weight=Decimal("0.60"), value=Decimal("120000.00")
            ),
            CurrentAllocationItem(
                asset_class="FIXED_INCOME", weight=Decimal("0.30"), value=Decimal("60000.00")
            ),
            CurrentAllocationItem(
                asset_class="CASH", weight=Decimal("0.10"), value=Decimal("20000.00")
            ),
        ],
        portfolio_value=Decimal("200000.00"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    assert res.risk_category == "AGGRESSIVE"
    assert res.rebalance_required is True

    plan_by_ac = {p.asset_class: p for p in res.rebalance_plan}
    assert plan_by_ac["EQUITY"].direction == "INCREASE"
    assert plan_by_ac["EQUITY"].indicative_amount == Decimal("40000.00")
    assert plan_by_ac["EQUITY"].benchmark_symbol == "SPY"

    assert plan_by_ac["FIXED_INCOME"].direction == "REDUCE"
    assert plan_by_ac["FIXED_INCOME"].indicative_amount == Decimal("-40000.00")

    assert plan_by_ac["CASH"].direction == "HOLD"
    assert plan_by_ac["CASH"].indicative_amount == Decimal("0.00")


def test_persona_4_all_cash_new_investor_moderate() -> None:
    """Persona 4: Neha (New Investor with 100% Cash)

    Target: Moderate (50% Equity, 40% Fixed Income, 10% Cash)
    Current: $10,000 Cash only
    Expected:
      - Equity: INCREASE $5,000
      - Fixed Income: INCREASE $4,000
      - Cash: REDUCE $9,000
    """
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(
                asset_class="CASH", weight=Decimal("1.00"), value=Decimal("10000.00")
            ),
        ],
        portfolio_value=Decimal("100000.00") / 10,
    )
    res = suitability_service.evaluate_suitability_rebalance(req)
    plan_by_ac = {p.asset_class: p for p in res.rebalance_plan}

    assert plan_by_ac["EQUITY"].indicative_amount == Decimal("5000.00")
    assert plan_by_ac["FIXED_INCOME"].indicative_amount == Decimal("4000.00")
    assert plan_by_ac["CASH"].indicative_amount == Decimal("-9000.00")


def test_persona_5_empty_portfolio_handling() -> None:
    """Persona 5: Empty Portfolio (No Holdings)

    Flags is_empty_portfolio=True, produces clean target recommendations without fake drift.
    """
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[],
        portfolio_value=Decimal("0.0"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    assert res.is_empty_portfolio is True
    assert res.rebalance_required is True
    assert len(res.rebalance_plan) == 3
    for p in res.rebalance_plan:
        assert p.direction == "INCREASE"
        assert p.current_weight == Decimal("0.0")


# ==============================================================================
# C. Custom Allocation Validation & Correctness Tests (Reviewer Finding PR #160)
# ==============================================================================


def test_custom_allocation_duplicate_asset_class_rejected() -> None:
    """Duplicate asset classes must be rejected with DUPLICATE_ASSET_CLASS."""
    # Exact duplicate
    req_exact = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.50")),
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.50")),
        ],
    )
    with pytest.raises(SuitabilityException) as exc_info:
        suitability_service.evaluate_suitability_rebalance(req_exact)
    assert exc_info.value.error_code == "DUPLICATE_ASSET_CLASS"
    assert "Duplicate asset class 'EQUITY'" in exc_info.value.message

    # Case-insensitive duplicate (e.g., 'equity' and 'EQUITY')
    req_case = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="equity", weight=Decimal("0.50")),
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.50")),
        ],
    )
    with pytest.raises(SuitabilityException) as exc_info_case:
        suitability_service.evaluate_suitability_rebalance(req_case)
    assert exc_info_case.value.error_code == "DUPLICATE_ASSET_CLASS"


def test_custom_allocation_incomplete_total_rejected_80_percent() -> None:
    """Custom allocation totaling 80% (0.80) must be rejected with INVALID_ALLOCATION_TOTAL."""
    # Fractional scale (0.80)
    req_frac = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.50")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.30")),
        ],
        portfolio_value=Decimal("100000.00"),
    )
    with pytest.raises(SuitabilityException) as exc_frac:
        suitability_service.evaluate_suitability_rebalance(req_frac)
    assert exc_frac.value.error_code == "INVALID_ALLOCATION_TOTAL"
    assert "Total custom allocation weights must sum to 1.0" in exc_frac.value.message

    # Percentage scale (80.0%)
    req_pct = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("50.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("30.0")),
        ],
        portfolio_value=Decimal("100000.00"),
    )
    with pytest.raises(SuitabilityException) as exc_pct:
        suitability_service.evaluate_suitability_rebalance(req_pct)
    assert exc_pct.value.error_code == "INVALID_ALLOCATION_TOTAL"
    assert "Total custom allocation percentage must equal 100%" in exc_pct.value.message


def test_custom_allocation_excess_total_rejected_120_percent() -> None:
    """Custom allocation totaling 120% (1.20) must be rejected with INVALID_ALLOCATION_TOTAL."""
    # Fractional scale (1.20)
    req_frac = SuitabilityRebalanceRequest(
        risk_category="CONSERVATIVE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.60")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.40")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.20")),
        ],
    )
    with pytest.raises(SuitabilityException) as exc_frac:
        suitability_service.evaluate_suitability_rebalance(req_frac)
    assert exc_frac.value.error_code == "INVALID_ALLOCATION_TOTAL"

    # Percentage scale (120.0%)
    req_pct = SuitabilityRebalanceRequest(
        risk_category="CONSERVATIVE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("60.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("40.0")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("20.0")),
        ],
    )
    with pytest.raises(SuitabilityException) as exc_pct:
        suitability_service.evaluate_suitability_rebalance(req_pct)
    assert exc_pct.value.error_code == "INVALID_ALLOCATION_TOTAL"


def test_custom_allocation_tolerance_boundaries() -> None:
    """Validate 0.1% tolerance boundary: 0.9995 accepted and normalized, 0.998 rejected."""
    # Accepted within tolerance (0.9995 on fractional scale) -> must be normalized to exactly 1.0
    req_ok = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.4995")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.5000")),
        ],
    )
    res_ok = suitability_service.evaluate_suitability_rebalance(req_ok)
    assert res_ok.risk_category == "MODERATE"
    assert sum(item.current_weight for item in res_ok.drift_summary) == Decimal("1.000000")
    assert sum(item.target_weight for item in res_ok.drift_summary) == Decimal("1.000000")
    assert sum(item.drift for item in res_ok.drift_summary) == Decimal("0.000000")

    # Default threshold (0.01): EQUITY drift (-0.025%) within threshold -> HOLD with 0.0 adj
    plan_by_ac = {item.asset_class: item for item in res_ok.rebalance_plan}
    assert plan_by_ac["EQUITY"].direction == "HOLD"
    assert plan_by_ac["EQUITY"].adjustment_weight == Decimal("0.000000")

    # With drift_threshold=0.0: all positions actionable and sum(adj_weight) == 0.000000
    req_all_trades = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.4995")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.5000")),
        ],
        drift_threshold=Decimal("0.000000"),
    )
    res_all_trades = suitability_service.evaluate_suitability_rebalance(req_all_trades)
    assert sum(item.adjustment_weight for item in res_all_trades.rebalance_plan) == Decimal(
        "0.000000"
    )

    # Rejected outside tolerance (0.998 on fractional scale)
    req_bad = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.498")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.500")),
        ],
    )
    with pytest.raises(SuitabilityException) as exc_bad:
        suitability_service.evaluate_suitability_rebalance(req_bad)
    assert exc_bad.value.error_code == "INVALID_ALLOCATION_TOTAL"


def test_custom_allocation_percentage_scale_boundary_normalization() -> None:
    """Validate exact normalization and zero-sum conservation at percentage scale boundaries."""
    portfolio_val = Decimal("100000.00")

    # 1. Lower boundary: 99.9% (50.0% + 30.0% + 19.9%)
    req_lower = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("50.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("30.0")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("19.9")),
        ],
        portfolio_value=portfolio_val,
        drift_threshold=Decimal("0.000000"),  # All non-zero drift actionable
    )
    res_lower = suitability_service.evaluate_suitability_rebalance(req_lower)
    assert sum(item.current_weight for item in res_lower.drift_summary) == Decimal("1.000000")
    assert sum(item.target_weight for item in res_lower.drift_summary) == Decimal("1.000000")
    assert sum(item.drift for item in res_lower.drift_summary) == Decimal("0.000000")
    assert sum(item.adjustment_weight for item in res_lower.rebalance_plan) == Decimal("0.000000")
    assert sum(
        item.indicative_amount for item in res_lower.rebalance_plan if item.indicative_amount
    ) == Decimal("0.00")

    # Under default threshold (0.01), verify EQUITY (+0.05% drift) is HOLD with 0.0 adj
    req_lower_default_thresh = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("50.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("30.0")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("19.9")),
        ],
        portfolio_value=portfolio_val,
    )
    res_lower_default = suitability_service.evaluate_suitability_rebalance(req_lower_default_thresh)
    plan_by_ac = {item.asset_class: item for item in res_lower_default.rebalance_plan}
    assert plan_by_ac["EQUITY"].direction == "HOLD"
    assert plan_by_ac["EQUITY"].adjustment_weight == Decimal("0.000000")
    assert plan_by_ac["EQUITY"].indicative_amount == Decimal("0.00")

    # 2. Reviewer explicit finding case: 99.95% (20.0% + 30.0% + 49.95%)
    # Target Moderate: 50% Equity, 40% Fixed Income, 10% Cash
    # All drifts exceed default 1% threshold: Equity -30%, Fixed Income -10%, Cash +40%
    req_finding = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("20.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("30.0")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("49.95")),
        ],
        portfolio_value=portfolio_val,
    )
    res_finding = suitability_service.evaluate_suitability_rebalance(req_finding)
    assert sum(item.current_weight for item in res_finding.drift_summary) == Decimal("1.000000")
    assert sum(item.target_weight for item in res_finding.drift_summary) == Decimal("1.000000")
    assert sum(item.drift for item in res_finding.drift_summary) == Decimal("0.000000")
    assert sum(item.adjustment_weight for item in res_finding.rebalance_plan) == Decimal("0.000000")
    assert sum(
        item.indicative_amount for item in res_finding.rebalance_plan if item.indicative_amount
    ) == Decimal("0.00")

    # 3. Upper boundary: 100.1% (50.0% + 30.0% + 20.1%)
    req_upper = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("50.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("30.0")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("20.1")),
        ],
        portfolio_value=portfolio_val,
        drift_threshold=Decimal("0.000000"),  # All non-zero drift actionable
    )
    res_upper = suitability_service.evaluate_suitability_rebalance(req_upper)
    assert sum(item.current_weight for item in res_upper.drift_summary) == Decimal("1.000000")
    assert sum(item.target_weight for item in res_upper.drift_summary) == Decimal("1.000000")
    assert sum(item.drift for item in res_upper.drift_summary) == Decimal("0.000000")
    assert sum(item.adjustment_weight for item in res_upper.rebalance_plan) == Decimal("0.000000")
    assert sum(
        item.indicative_amount for item in res_upper.rebalance_plan if item.indicative_amount
    ) == Decimal("0.00")


def test_custom_allocation_fractional_scale_boundary_normalization() -> None:
    """Validate exact normalization and zero-sum conservation at fractional scale boundaries."""
    portfolio_val = Decimal("200000.00")

    # 1. Lower boundary: 0.999 (0.500 + 0.300 + 0.199)
    # Target Conservative: Equity 20%, Fixed Income 70%, Cash 10%
    # Drifts: Equity +30%, Fixed Income -40%, Cash +10% -> all exceed 1% threshold
    req_lower = SuitabilityRebalanceRequest(
        risk_category="CONSERVATIVE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.500")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.300")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.199")),
        ],
        portfolio_value=portfolio_val,
    )
    res_lower = suitability_service.evaluate_suitability_rebalance(req_lower)
    assert sum(item.current_weight for item in res_lower.drift_summary) == Decimal("1.000000")
    assert sum(item.drift for item in res_lower.drift_summary) == Decimal("0.000000")
    assert sum(item.adjustment_weight for item in res_lower.rebalance_plan) == Decimal("0.000000")
    assert sum(
        item.indicative_amount for item in res_lower.rebalance_plan if item.indicative_amount
    ) == Decimal("0.00")

    # 2. Upper boundary: 1.001 (0.500 + 0.300 + 0.201)
    req_upper = SuitabilityRebalanceRequest(
        risk_category="CONSERVATIVE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.500")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.300")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.201")),
        ],
        portfolio_value=portfolio_val,
    )
    res_upper = suitability_service.evaluate_suitability_rebalance(req_upper)
    assert sum(item.current_weight for item in res_upper.drift_summary) == Decimal("1.000000")
    assert sum(item.drift for item in res_upper.drift_summary) == Decimal("0.000000")
    assert sum(item.adjustment_weight for item in res_upper.rebalance_plan) == Decimal("0.000000")
    assert sum(
        item.indicative_amount for item in res_upper.rebalance_plan if item.indicative_amount
    ) == Decimal("0.00")


def test_custom_allocation_quantization_residual_deterministic_allocation() -> None:
    """Validate deterministic allocation of six-decimal quantization residual."""
    # 3 equal weights of 33.3% sum to 99.9%.
    # 33.3 / 99.9 = 1/3 = 0.333333333...
    # Quantized independently to 6 decimals: 0.333333 * 3 = 0.999999.
    # Residual = +0.000001.
    # Alphabetical tie-breaker: CASH < EQUITY < FIXED_INCOME -> CASH gets +0.000001.
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("33.3")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("33.3")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("33.3")),
        ],
    )
    res1 = suitability_service.evaluate_suitability_rebalance(req)
    res2 = suitability_service.evaluate_suitability_rebalance(req)

    weights1 = {item.asset_class: item.current_weight for item in res1.drift_summary}
    weights2 = {item.asset_class: item.current_weight for item in res2.drift_summary}

    # Exactly 1.000000 total
    assert sum(weights1.values()) == Decimal("1.000000")
    # All weights non-negative
    for w in weights1.values():
        assert w > Decimal("0.0")

    # CASH received the residual of 0.000001
    assert weights1["CASH"] == Decimal("0.333334")
    assert weights1["EQUITY"] == Decimal("0.333333")
    assert weights1["FIXED_INCOME"] == Decimal("0.333333")

    # Deterministic and idempotent across repeated runs
    assert weights1 == weights2


def test_custom_allocation_monetary_conservation_fractional_cents() -> None:
    """Validate exact monetary conservation (sum == 0.00) across fractional-cent values."""
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("20.0")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("30.0")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("49.95")),
        ],
        portfolio_value=Decimal("150000.55"),
    )

    for val in [
        Decimal("150000.55"),
        Decimal("100000.01"),
        Decimal("99.99"),
        Decimal("12345.67"),
        Decimal("0.01"),
    ]:
        req.portfolio_value = val
        res = suitability_service.evaluate_suitability_rebalance(req)
        amt_sum = sum(
            item.indicative_amount for item in res.rebalance_plan if item.indicative_amount
        )
        assert amt_sum == Decimal("0.00"), f"Monetary adjustments do not conserve capital on {val}"


def test_custom_allocation_zero_sum_rebalancing_and_value_conservation() -> None:
    """Verify that validated allocations strictly conserve zero-sum drift and portfolio value."""
    portfolio_val = Decimal("150000.00")
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.70")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.20")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.10")),
        ],
        portfolio_value=portfolio_val,
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    # 1. Sum of current weights must equal exactly 1.000000
    curr_sum = sum(item.current_weight for item in res.drift_summary)
    assert curr_sum == Decimal("1.000000")

    # 2. Sum of signed drifts must equal exactly zero
    drift_sum = sum(item.drift for item in res.drift_summary)
    assert drift_sum == Decimal("0.000000")

    # 3. Sum of adjustment weights must equal exactly zero
    adj_sum = sum(item.adjustment_weight for item in res.rebalance_plan)
    assert adj_sum == Decimal("0.000000")

    # 4. Sum of indicative monetary adjustments must equal zero (portfolio value conservation)
    amt_sum = sum(item.indicative_amount for item in res.rebalance_plan if item.indicative_amount)
    assert amt_sum == Decimal("0.00")


# ==============================================================================
# D. Drift Threshold & Action Classification Consistency Tests (Reviewer Finding PR #160)
# ==============================================================================


def test_drift_threshold_nonzero_drift_within_threshold_is_hold_and_zero_adjustment() -> None:
    """Non-zero 0.5% drift within default 1% threshold is BALANCED/HOLD with 0.0 adjustment."""
    # Target Moderate: Equity 50%, Fixed Income 40%, Cash 10%
    # Current: Equity 50.5% (+0.5% drift), Fixed Income 39.5% (-0.5% drift), Cash 10.0% (0.0% drift)
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.505")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.395")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.100")),
        ],
        portfolio_value=Decimal("100000.00"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    # Rebalance is NOT required because all drifts are within 1% threshold
    assert res.rebalance_required is False
    assert res.max_drift == Decimal("0.005000")

    # Drift summary: all items must be BALANCED and HOLD
    for drift_item in res.drift_summary:
        assert drift_item.status == "BALANCED"
        assert drift_item.action == "HOLD"

    # Plan: all items must have direction HOLD, adjustment 0.000000, amount 0.00
    for plan_item in res.rebalance_plan:
        assert plan_item.direction == "HOLD"
        assert plan_item.adjustment_weight == Decimal("0.000000")
        assert plan_item.indicative_amount == Decimal("0.00")
        assert "within tolerance of target" in plan_item.explanation
        assert "no adjustment recommended" in plan_item.explanation

    # Mathematical sums
    assert sum(p.adjustment_weight for p in res.rebalance_plan) == Decimal("0.000000")
    assert sum(p.indicative_amount for p in res.rebalance_plan if p.indicative_amount) == Decimal(
        "0.00"
    )


def test_drift_threshold_inclusive_boundary_exactly_one_percent() -> None:
    """Drift exactly at threshold boundary (abs(drift) == 0.010000) is BALANCED/HOLD."""
    # Target Moderate: Equity 50%, Fixed Income 40%, Cash 10%
    # Current: Equity 51.0% (+1.0%), Fixed Income 39.0% (-1.0%), Cash 10.0% (0.0%)
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.510000")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.390000")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.100000")),
        ],
        portfolio_value=Decimal("100000.00"),
        drift_threshold=Decimal("0.01"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)

    # abs(0.010000) <= 0.01 is inclusive -> BALANCED / HOLD
    assert res.rebalance_required is False
    for drift_item in res.drift_summary:
        assert drift_item.status == "BALANCED"
        assert drift_item.action == "HOLD"

    for plan_item in res.rebalance_plan:
        assert plan_item.direction == "HOLD"
        assert plan_item.adjustment_weight == Decimal("0.000000")
        assert plan_item.indicative_amount == Decimal("0.00")


def test_drift_threshold_just_above_and_just_below_boundary() -> None:
    """Drift just below threshold (0.99%) is HOLD; just above (1.01%) is actionable."""
    portfolio_val = Decimal("100000.00")

    # 1. Just below threshold (0.99% drift)
    req_below = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.509900")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.390100")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.100000")),
        ],
        portfolio_value=portfolio_val,
        drift_threshold=Decimal("0.01"),
    )
    res_below = suitability_service.evaluate_suitability_rebalance(req_below)
    assert res_below.rebalance_required is False
    for p in res_below.rebalance_plan:
        assert p.direction == "HOLD"
        assert p.adjustment_weight == Decimal("0.000000")
        assert p.indicative_amount == Decimal("0.00")

    # 2. Just above threshold (1.01% drift)
    req_above = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.510100")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.389900")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.100000")),
        ],
        portfolio_value=portfolio_val,
        drift_threshold=Decimal("0.01"),
    )
    res_above = suitability_service.evaluate_suitability_rebalance(req_above)
    assert res_above.rebalance_required is True

    plan_map = {p.asset_class: p for p in res_above.rebalance_plan}
    assert plan_map["EQUITY"].direction == "REDUCE"
    assert plan_map["EQUITY"].adjustment_weight == Decimal("-0.010100")
    assert plan_map["EQUITY"].indicative_amount == Decimal("-1010.00")

    assert plan_map["FIXED_INCOME"].direction == "INCREASE"
    assert plan_map["FIXED_INCOME"].adjustment_weight == Decimal("0.010100")
    assert plan_map["FIXED_INCOME"].indicative_amount == Decimal("1010.00")

    assert plan_map["CASH"].direction == "HOLD"
    assert plan_map["CASH"].adjustment_weight == Decimal("0.000000")
    assert plan_map["CASH"].indicative_amount == Decimal("0.00")


def test_drift_threshold_mixed_held_and_actionable_positions() -> None:
    """Verify that held positions receive exactly 0.00 while actionable positions receive trades."""
    # Target Moderate: Equity 50%, Fixed Income 40%, Cash 10%
    # Current: Equity 65% (REDUCE), Fixed Income 24.5% (INCREASE), Cash 10.5% (HOLD)
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.650")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.245")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.105")),
        ],
        portfolio_value=Decimal("100000.00"),
        drift_threshold=Decimal("0.01"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)
    assert res.rebalance_required is True

    plan_by_ac = {p.asset_class: p for p in res.rebalance_plan}

    # Actionable: Equity reduces by 15% ($15,000)
    assert plan_by_ac["EQUITY"].direction == "REDUCE"
    assert plan_by_ac["EQUITY"].adjustment_weight == Decimal("-0.150000")
    assert plan_by_ac["EQUITY"].indicative_amount == Decimal("-15000.00")

    # Actionable: Fixed Income increases by 15.5% ($15,500)
    assert plan_by_ac["FIXED_INCOME"].direction == "INCREASE"
    assert plan_by_ac["FIXED_INCOME"].adjustment_weight == Decimal("0.155000")
    assert plan_by_ac["FIXED_INCOME"].indicative_amount == Decimal("15500.00")

    # Held: Cash (+0.5% drift) within 1% threshold -> strictly HOLD, 0.000000 weight, $0.00 amount
    assert plan_by_ac["CASH"].direction == "HOLD"
    assert plan_by_ac["CASH"].adjustment_weight == Decimal("0.000000")
    assert plan_by_ac["CASH"].indicative_amount == Decimal("0.00")


def test_drift_threshold_custom_configurable_threshold() -> None:
    """Custom drift threshold (0.2%) makes 0.5% drift actionable."""
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.505")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.395")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.100")),
        ],
        portfolio_value=Decimal("100000.00"),
        drift_threshold=Decimal("0.002"),  # 0.2% threshold
    )
    res = suitability_service.evaluate_suitability_rebalance(req)
    assert res.rebalance_required is True

    plan_by_ac = {p.asset_class: p for p in res.rebalance_plan}
    assert plan_by_ac["EQUITY"].direction == "REDUCE"
    assert plan_by_ac["EQUITY"].adjustment_weight == Decimal("-0.005000")
    assert plan_by_ac["EQUITY"].indicative_amount == Decimal("-500.00")

    assert plan_by_ac["FIXED_INCOME"].direction == "INCREASE"
    assert plan_by_ac["FIXED_INCOME"].adjustment_weight == Decimal("0.005000")
    assert plan_by_ac["FIXED_INCOME"].indicative_amount == Decimal("500.00")

    assert plan_by_ac["CASH"].direction == "HOLD"
    assert plan_by_ac["CASH"].adjustment_weight == Decimal("0.000000")
    assert plan_by_ac["CASH"].indicative_amount == Decimal("0.00")


def test_drift_threshold_zero_threshold_enforces_exact_zero_sum_rebalancing() -> None:
    """Setting drift_threshold=0.0 guarantees all non-zero drifts are traded with exact zero-sum."""
    req = SuitabilityRebalanceRequest(
        risk_category="MODERATE",
        current_allocation=[
            CurrentAllocationItem(asset_class="EQUITY", weight=Decimal("0.505")),
            CurrentAllocationItem(asset_class="FIXED_INCOME", weight=Decimal("0.395")),
            CurrentAllocationItem(asset_class="CASH", weight=Decimal("0.100")),
        ],
        portfolio_value=Decimal("100000.00"),
        drift_threshold=Decimal("0.000000"),
    )
    res = suitability_service.evaluate_suitability_rebalance(req)
    assert res.rebalance_required is True

    # When all non-zero drift is actionable, sum of adjustments is exactly 0.000000 and $0.00
    assert sum(p.adjustment_weight for p in res.rebalance_plan) == Decimal("0.000000")
    assert sum(p.indicative_amount for p in res.rebalance_plan if p.indicative_amount) == Decimal(
        "0.00"
    )
