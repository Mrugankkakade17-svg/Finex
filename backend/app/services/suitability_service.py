"""Suitability Engine Service (S3-LI01).

Implements deterministic educational portfolio suitability, target allocation mapping,
portfolio drift analysis, and rebalance plan generation according to S3-MR01 reference
models, S3-PA01 portfolio analytics, and existing ai.risk scoring engine contracts.

STRICT COMPLIANCE:
- 100% Deterministic (Zero LLM/AI dependency for calculations)
- Mathematical invariants strictly enforced (weights >= 0, sum == 1, equity monotonicity)
- Pure educational boundaries (no regulated personal financial advice, no fake order execution)
- Safe decimal arithmetic for financial precision
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple, Union, cast

from ai.risk.schemas import QuestionAnswer, RiskAssessmentRequest
from ai.risk.scoring import RiskScoringEngine

from app.core.exceptions import SuitabilityException
from app.schemas.suitability import (
    AllocationDriftItem,
    RebalancePlanItem,
    RiskCategoryEnum,
    SuitabilityRebalanceRequest,
    SuitabilityRebalanceResponse,
    TargetAllocationItem,
    TargetAllocationResponse,
)

# ---------------------------------------------------------------------------
# Authoritative S3-MR01 Reference Models & Benchmarks
# ---------------------------------------------------------------------------

_ZERO = Decimal("0.0")
_ONE = Decimal("1.0")
_HUNDRED = Decimal("100.0")
_TOLERANCE = Decimal("0.00001")

# Reference models from S3-MR01 (scripts/seed_reference_data.py and fx_006)
ALLOCATION_MODELS: Dict[str, Dict[str, Any]] = {
    "CONSERVATIVE_V1": {
        "model_code": "CONSERVATIVE_V1",
        "name": "Conservative educational model",
        "risk_category": "CONSERVATIVE",
        "version": "v1",
        "description": (
            "Illustrative reference weights prioritizing capital preservation and income; "
            "not advice."
        ),
    },
    "MODERATE_V1": {
        "model_code": "MODERATE_V1",
        "name": "Moderate educational model",
        "risk_category": "MODERATE",
        "version": "v1",
        "description": (
            "Illustrative reference weights balancing moderate capital growth and income; "
            "not advice."
        ),
    },
    "AGGRESSIVE_V1": {
        "model_code": "AGGRESSIVE_V1",
        "name": "Aggressive educational model",
        "risk_category": "AGGRESSIVE",
        "version": "v1",
        "description": (
            "Illustrative reference weights emphasizing long-term capital appreciation; not advice."
        ),
    },
}

# Target weights per model and asset class
ALLOCATION_TARGETS: Dict[str, Dict[str, Decimal]] = {
    "CONSERVATIVE_V1": {
        "EQUITY": Decimal("0.200000"),
        "FIXED_INCOME": Decimal("0.700000"),
        "CASH": Decimal("0.100000"),
    },
    "MODERATE_V1": {
        "EQUITY": Decimal("0.500000"),
        "FIXED_INCOME": Decimal("0.400000"),
        "CASH": Decimal("0.100000"),
    },
    "AGGRESSIVE_V1": {
        "EQUITY": Decimal("0.800000"),
        "FIXED_INCOME": Decimal("0.100000"),
        "CASH": Decimal("0.100000"),
    },
}

# Approved benchmark / ETF proxies from S3-MR01 benchmark_map
BENCHMARK_PROXIES: Dict[str, Dict[str, str]] = {
    "EQUITY": {
        "benchmark_symbol": "SPY",
        "benchmark_name": "Synthetic S&P 500 ETF proxy",
    },
    "FIXED_INCOME": {
        "benchmark_symbol": "AGG",
        "benchmark_name": "Synthetic U.S. aggregate bond ETF proxy",
    },
    "CASH": {
        "benchmark_symbol": "CSHX",
        "benchmark_name": "Synthetic short-term cash proxy",
    },
}

EDUCATIONAL_DISCLAIMER = (
    "Educational suitability and allocation demonstration only. "
    "Not regulated personal financial, investment, legal, or tax advice. "
    "Reference models illustrate hypothetical asset distributions based on "
    "general risk profiles. Past performance is no guarantee of future returns. "
    "Trading costs, commissions, management fees, and taxes are not modeled. "
    "Investors must independently assess their own objectives and consult a "
    "licensed financial professional before making investment decisions."
)


class SuitabilityService:
    """Deterministic service for suitability, target allocations, drift, and rebalancing."""

    def __init__(self, risk_scoring_engine: Optional[RiskScoringEngine] = None):
        self._scoring_engine = risk_scoring_engine or RiskScoringEngine()

    def resolve_risk_category(
        self,
        risk_category: Optional[str] = None,
        questionnaire_answers: Optional[List[QuestionAnswer]] = None,
    ) -> Tuple[RiskCategoryEnum, Optional[Dict[str, Any]]]:
        """Resolve canonical RiskCategoryEnum from either direct input or questionnaire answers."""
        if questionnaire_answers:
            req = RiskAssessmentRequest(answers=questionnaire_answers)
            result = self._scoring_engine.evaluate(req)
            category_str = result.risk_category.value
            canonical_cat = RiskCategoryEnum.from_str(category_str)
            summary = {
                "composite_score": result.composite_score,
                "category": category_str,
                "dimension_scores": {
                    "willingness": result.breakdown.willingness.normalized_score,
                    "capacity": result.breakdown.capacity.normalized_score,
                },
                "summary": result.explanation.summary if result.explanation else None,
            }
            return canonical_cat, summary

        if risk_category:
            canonical_cat = RiskCategoryEnum.from_str(risk_category)
            return canonical_cat, None

        raise SuitabilityException(
            "Either 'risk_category' or 'questionnaire_answers' must be provided.",
            error_code="MISSING_SUITABILITY_INPUT",
            status_code=400,
        )

    def get_model_code_for_category(self, category: RiskCategoryEnum) -> str:
        """Map canonical risk category to authoritative reference model code."""
        if category == RiskCategoryEnum.CONSERVATIVE:
            return "CONSERVATIVE_V1"
        if category == RiskCategoryEnum.MODERATE:
            return "MODERATE_V1"
        if category == RiskCategoryEnum.AGGRESSIVE:
            return "AGGRESSIVE_V1"
        raise SuitabilityException(
            f"Unsupported risk category: {category}",
            error_code="INVALID_RISK_CATEGORY",
            status_code=400,
        )

    def validate_allocation_invariants(
        self, targets: Dict[str, Decimal], model_code: Optional[str] = None
    ) -> bool:
        """Verify mathematical invariants for an allocation model:

        1. Finite and non-negative: all w >= 0
        2. Sum of weights equals 1.0 (within numerical tolerance)
        3. No duplicate asset classes
        """
        if not targets:
            raise SuitabilityException(
                "Target allocations cannot be empty.", error_code="EMPTY_TARGET_ALLOCATION"
            )

        total = Decimal("0.0")
        for asset_class, weight in targets.items():
            if not isinstance(weight, Decimal):
                weight = Decimal(str(weight))
            if weight.is_nan() or weight.is_infinite():
                raise SuitabilityException(
                    f"Target weight for {asset_class} is non-finite.",
                    error_code="NON_FINITE_WEIGHT",
                )
            if weight < _ZERO:
                raise SuitabilityException(
                    f"Target weight for {asset_class} must be non-negative, got {weight}.",
                    error_code="NEGATIVE_WEIGHT",
                )
            total += weight

        if abs(total - _ONE) > _TOLERANCE:
            raise SuitabilityException(
                f"Target allocation weights must sum to 1.0, got {total}.",
                error_code="INVALID_WEIGHT_SUM",
            )

        return True

    def verify_equity_monotonicity(self) -> bool:
        """Verify the global invariant that equity allocation is non-decreasing with risk."""
        c_eq = ALLOCATION_TARGETS["CONSERVATIVE_V1"]["EQUITY"]
        m_eq = ALLOCATION_TARGETS["MODERATE_V1"]["EQUITY"]
        a_eq = ALLOCATION_TARGETS["AGGRESSIVE_V1"]["EQUITY"]
        if not (c_eq <= m_eq <= a_eq):
            raise SuitabilityException(
                f"Equity monotonicity violation: {c_eq} <= {m_eq} <= {a_eq} failed.",
                error_code="MONOTONICITY_VIOLATION",
            )
        return True

    def get_target_allocation(
        self, risk_category: Union[RiskCategoryEnum, str]
    ) -> TargetAllocationResponse:
        """Return the authoritative target allocation model and approved proxy benchmarks."""
        if isinstance(risk_category, str):
            category = RiskCategoryEnum.from_str(risk_category)
        else:
            category = risk_category

        model_code = self.get_model_code_for_category(category)
        model_meta = ALLOCATION_MODELS.get(model_code)
        if not model_meta:
            raise SuitabilityException(
                f"Reference model not found for code: {model_code}",
                error_code="MODEL_NOT_FOUND",
                status_code=404,
            )

        raw_targets = ALLOCATION_TARGETS.get(model_code)
        if not raw_targets:
            raise SuitabilityException(
                f"Allocation targets not found for model: {model_code}",
                error_code="TARGETS_NOT_FOUND",
                status_code=404,
            )

        self.validate_allocation_invariants(raw_targets, model_code=model_code)
        self.verify_equity_monotonicity()

        items: List[TargetAllocationItem] = []
        for asset_class, weight in raw_targets.items():
            benchmark = BENCHMARK_PROXIES.get(
                asset_class,
                {"benchmark_symbol": "CUSTOM", "benchmark_name": f"Proxy for {asset_class}"},
            )
            pct = weight * _HUNDRED
            items.append(
                TargetAllocationItem(
                    asset_class=asset_class,
                    target_weight=weight,
                    target_pct=pct,
                    benchmark_symbol=benchmark["benchmark_symbol"],
                    benchmark_name=benchmark["benchmark_name"],
                )
            )

        return TargetAllocationResponse(
            risk_category=category.value,
            model_code=model_code,
            model_name=model_meta["name"],
            version=model_meta["version"],
            description=model_meta["description"],
            allocations=items,
            invariants_satisfied=True,
            educational_disclaimer=EDUCATIONAL_DISCLAIMER,
        )

    @staticmethod
    def _normalize_allocation_weights(
        raw_items: List[Tuple[str, Decimal]],
    ) -> Dict[str, Decimal]:
        """Normalize raw weights to sum exactly to Decimal('1.000000').

        Applies high-precision Decimal division by raw total, quantizes each weight
        to 6 decimal places (10^-6), and deterministically allocates any quantization
        residual (1.000000 - sum(quantized_weights)) to the largest weight with stable
        alphabetical tie-breaking.
        """
        raw_total = sum(w for _, w in raw_items)
        if raw_total <= _ZERO:
            raise SuitabilityException(
                "Total allocation weight must be strictly positive for normalization.",
                error_code="INVALID_ALLOCATION_TOTAL",
                status_code=400,
            )

        quantized_map: Dict[str, Decimal] = {}
        for ac, w in raw_items:
            norm_w = w / raw_total
            quantized_map[ac] = norm_w.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        residual = Decimal("1.000000") - sum(quantized_map.values())
        if residual != _ZERO:
            # Deterministically assign residual to the entry with the largest weight,
            # using asset class name as stable tie-breaker.
            best_ac = sorted(
                quantized_map.keys(),
                key=lambda k: (-quantized_map[k], k),
            )[0]
            quantized_map[best_ac] += residual

        # Safety check: ensure all weights remain non-negative
        for ac, w in quantized_map.items():
            if w < _ZERO:
                raise SuitabilityException(
                    f"Normalized weight for asset class '{ac}' became negative ({w}).",
                    error_code="NEGATIVE_WEIGHT",
                    status_code=400,
                )

        final_sum = sum(quantized_map.values())
        if final_sum != Decimal("1.000000"):
            raise SuitabilityException(
                f"Failed to normalize allocation weights to exactly 1.0 (got {final_sum}).",
                error_code="INVALID_ALLOCATION_TOTAL",
                status_code=400,
            )

        return quantized_map

    def calculate_drift(
        self,
        current_allocations: Dict[str, Decimal],
        target_allocations: Dict[str, Decimal],
        drift_threshold: Decimal = Decimal("0.01"),
    ) -> Tuple[List[AllocationDriftItem], Decimal, bool]:
        """Calculate allocation drift between current portfolio holdings and target allocation.

        Formula: drift = current_weight - target_weight
        """
        # Collect union of all asset classes
        all_classes = sorted(list(set(current_allocations.keys()) | set(target_allocations.keys())))
        drift_items: List[AllocationDriftItem] = []
        max_drift = _ZERO

        for ac in all_classes:
            w_curr = current_allocations.get(ac, _ZERO)
            w_target = target_allocations.get(ac, _ZERO)

            if w_curr.is_nan() or w_curr.is_infinite():
                raise SuitabilityException(
                    f"Current weight for asset class {ac} is non-finite",
                    error_code="NON_FINITE_WEIGHT",
                )
            if w_curr < _ZERO:
                raise SuitabilityException(
                    f"Current weight for asset class {ac} must be non-negative, got {w_curr}",
                    error_code="NEGATIVE_WEIGHT",
                )

            drift = w_curr - w_target
            abs_drift = abs(drift)
            if abs_drift > max_drift:
                max_drift = abs_drift

            curr_pct = w_curr * _HUNDRED
            target_pct = w_target * _HUNDRED
            drift_pct = drift * _HUNDRED

            status: Literal["OVERWEIGHT", "UNDERWEIGHT", "BALANCED"]
            action: Literal["INCREASE", "REDUCE", "HOLD"]
            if drift > drift_threshold:
                status = "OVERWEIGHT"
                action = "REDUCE"
            elif drift < -drift_threshold:
                status = "UNDERWEIGHT"
                action = "INCREASE"
            else:
                status = "BALANCED"
                action = "HOLD"

            drift_items.append(
                AllocationDriftItem(
                    asset_class=ac,
                    current_weight=w_curr,
                    current_pct=curr_pct,
                    target_weight=w_target,
                    target_pct=target_pct,
                    drift=drift,
                    drift_pct=drift_pct,
                    status=status,
                    action=action,
                )
            )

        rebalance_required = any(item.status != "BALANCED" for item in drift_items)
        return drift_items, max_drift, rebalance_required

    def generate_rebalance_plan(
        self,
        drift_items: List[AllocationDriftItem],
        portfolio_value: Optional[Decimal] = None,
    ) -> List[RebalancePlanItem]:
        """Generate deterministic, explainable rebalance recommendations from drift items.

        Formula: adjustment_weight = target_weight - current_weight = -drift
        Conserves portfolio capital exactly: sum(indicative_amounts) == Decimal('0.00').
        """
        # Pre-compute indicative monetary amounts ensuring exact zero-sum conservation
        amounts_map: Dict[str, Optional[Decimal]] = {}
        if portfolio_value is not None and portfolio_value > _ZERO:
            raw_amts: Dict[str, Decimal] = {
                item.asset_class: (
                    (item.target_weight - item.current_weight) * portfolio_value
                ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                for item in drift_items
            }
            monetary_residual = Decimal("0.00") - sum(raw_amts.values())
            if monetary_residual != Decimal("0.00"):
                candidates = [
                    item.asset_class
                    for item in drift_items
                    if (item.target_weight - item.current_weight) != _ZERO
                ]
                if candidates:
                    # Deterministically assign monetary rounding residual (e.g. ±$0.01)
                    # to the non-zero adjustment with the largest absolute amount,
                    # using asset class name as stable tie-breaker.
                    best_ac = sorted(
                        candidates,
                        key=lambda k: (-abs(raw_amts[k]), k),
                    )[0]
                    raw_amts[best_ac] += monetary_residual
            amounts_map = cast(Dict[str, Optional[Decimal]], raw_amts)
        else:
            amounts_map = {item.asset_class: None for item in drift_items}

        plan_items: List[RebalancePlanItem] = []

        for item in drift_items:
            ac = item.asset_class
            w_curr = item.current_weight
            w_target = item.target_weight
            drift = item.drift

            # Required adjustment fraction is -drift = target - current
            adj_weight = w_target - w_curr

            direction: Literal["INCREASE", "REDUCE", "HOLD"]
            if adj_weight > Decimal("0.000001"):
                direction = "INCREASE"
            elif adj_weight < Decimal("-0.000001"):
                direction = "REDUCE"
            else:
                direction = "HOLD"

            # Benchmark proxy info
            benchmark = BENCHMARK_PROXIES.get(ac)
            benchmark_symbol = benchmark["benchmark_symbol"] if benchmark else None
            benchmark_name = benchmark["benchmark_name"] if benchmark else None

            # Indicative monetary amount from pre-computed conserved amounts map
            indicative_amount = amounts_map.get(ac)

            # Educational explanation
            explanation = self._build_educational_explanation(
                asset_class=ac,
                current_pct=item.current_pct,
                target_pct=item.target_pct,
                drift_pct=item.drift_pct,
                direction=direction,
                indicative_amount=indicative_amount,
                benchmark_symbol=benchmark_symbol,
            )

            plan_items.append(
                RebalancePlanItem(
                    asset_class=ac,
                    current_weight=w_curr,
                    target_weight=w_target,
                    drift=drift,
                    adjustment_weight=adj_weight,
                    direction=direction,
                    indicative_amount=indicative_amount,
                    benchmark_symbol=benchmark_symbol,
                    benchmark_name=benchmark_name,
                    explanation=explanation,
                )
            )

        return plan_items

    def _build_educational_explanation(
        self,
        asset_class: str,
        current_pct: Decimal,
        target_pct: Decimal,
        drift_pct: Decimal,
        direction: str,
        indicative_amount: Optional[Decimal],
        benchmark_symbol: Optional[str],
    ) -> str:
        """Formulate a transparent, educational non-advisory adjustment explanation."""
        proxy_note = f" via proxy {benchmark_symbol}" if benchmark_symbol else ""
        if direction == "HOLD":
            return (
                f"{asset_class} is at {current_pct:.1f}%, within tolerance of target "
                f"({target_pct:.1f}%); no adjustment recommended."
            )
        if direction == "REDUCE":
            amount_str = (
                f" (~${abs(indicative_amount):,.2f})" if indicative_amount is not None else ""
            )
            return (
                f"{asset_class} is currently {current_pct:.1f}%, which is "
                f"{abs(drift_pct):.1f}% overweight relative to target ({target_pct:.1f}%). "
                f"Consider reducing exposure by {abs(drift_pct):.1f}%{amount_str} "
                f"to restore target risk alignment."
            )
        # INCREASE
        amount_str = f" (~${abs(indicative_amount):,.2f})" if indicative_amount is not None else ""
        return (
            f"{asset_class} is currently {current_pct:.1f}%, which is "
            f"{abs(drift_pct):.1f}% underweight relative to target ({target_pct:.1f}%). "
            f"Consider increasing exposure by {abs(drift_pct):.1f}%{amount_str}{proxy_note} "
            f"to restore target risk alignment."
        )

    def evaluate_suitability_rebalance(
        self,
        request: SuitabilityRebalanceRequest,
        portfolio_summary: Optional[Any] = None,
    ) -> SuitabilityRebalanceResponse:
        """Execute the end-to-end suitability, drift, and rebalancing calculation."""
        # 1. Resolve risk category and target model
        category, risk_summary = self.resolve_risk_category(
            risk_category=request.risk_category,
            questionnaire_answers=request.questionnaire_answers,
        )
        target_resp = self.get_target_allocation(category)
        targets_map = {item.asset_class: item.target_weight for item in target_resp.allocations}

        # 2. Extract current allocations & portfolio value
        current_map: Dict[str, Decimal] = {}
        total_val: Optional[Decimal] = None
        is_empty = False

        if portfolio_summary is not None:
            # Consuming PortfolioSummaryResponse from S3-PA01
            raw_val = getattr(portfolio_summary, "total_value", None)
            if raw_val is not None:
                total_val = Decimal(str(raw_val))

            holdings_count = getattr(portfolio_summary, "holdings_count", 0)
            if holdings_count == 0 or (total_val is not None and total_val <= _ZERO):
                is_empty = True

            asset_allocations = getattr(portfolio_summary, "asset_allocation", []) or []
            summary_raw_items: List[Tuple[str, Decimal]] = []
            for item in asset_allocations:
                cat = str(getattr(item, "category", "")).strip().upper()
                pct = Decimal(str(getattr(item, "percentage", 0)))
                if cat and pct > _ZERO:
                    summary_raw_items.append((cat, pct))
            if summary_raw_items and not is_empty:
                current_map = self._normalize_allocation_weights(summary_raw_items)
        elif request.current_allocation:
            # Direct client-supplied allocation: validate asset uniqueness, finite weights,
            # and verify total equals 1.0 (or 100%) within documented tolerance for zero-sum drift.
            seen_classes: set[str] = set()
            raw_items: List[Tuple[str, Decimal]] = []

            for item in request.current_allocation:
                ac = str(item.asset_class).strip().upper()
                if not ac:
                    raise SuitabilityException(
                        "Asset class identifier cannot be empty.",
                        error_code="INVALID_ASSET_CLASS",
                        status_code=400,
                    )
                if ac in seen_classes:
                    raise SuitabilityException(
                        f"Duplicate asset class '{ac}' detected in custom allocation. "
                        "Each asset class must appear at most once.",
                        error_code="DUPLICATE_ASSET_CLASS",
                        status_code=400,
                    )
                seen_classes.add(ac)

                w = Decimal(str(item.weight))
                if w.is_nan() or w.is_infinite():
                    raise SuitabilityException(
                        f"Weight for asset class '{ac}' must be a finite number.",
                        error_code="NON_FINITE_WEIGHT",
                        status_code=400,
                    )
                if w < _ZERO:
                    raise SuitabilityException(
                        f"Weight for asset class '{ac}' cannot be negative ({w}).",
                        error_code="NEGATIVE_WEIGHT",
                        status_code=400,
                    )
                raw_items.append((ac, w))

            raw_total = sum(w for _, w in raw_items)

            # Determine whether input is on percentage scale (0-100) or fractional scale (0-1)
            # Scale tolerance: 0.1% for percentage scale, 0.001 (0.1%) for fractional scale
            is_percentage_scale = any(w > _ONE for _, w in raw_items) or raw_total > Decimal("1.5")
            if is_percentage_scale:
                diff = abs(raw_total - _HUNDRED)
                if diff > Decimal("0.1"):
                    raise SuitabilityException(
                        "Total custom allocation percentage must equal 100% (within ±0.1% "
                        f"tolerance). Got {raw_total:.4f}% (difference {diff:.4f}% exceeds "
                        "0.1% tolerance).",
                        error_code="INVALID_ALLOCATION_TOTAL",
                        status_code=400,
                    )
            else:
                diff = abs(raw_total - _ONE)
                if diff > Decimal("0.001"):
                    raise SuitabilityException(
                        "Total custom allocation weights must sum to 1.0 (within ±0.001 "
                        f"tolerance). Got {raw_total:.6f} (difference {diff:.6f} exceeds "
                        "0.001 tolerance).",
                        error_code="INVALID_ALLOCATION_TOTAL",
                        status_code=400,
                    )

            # Exactly normalize accepted weights to sum to Decimal('1.000000')
            current_map = self._normalize_allocation_weights(raw_items)

            if request.portfolio_value is not None:
                total_val = Decimal(str(request.portfolio_value))
                if total_val <= _ZERO:
                    is_empty = True
        else:
            # Neither portfolio_id summary nor current_allocation supplied
            is_empty = True

        # 3. Handle empty portfolio explicitly without fabricating fake drift
        if is_empty:
            empty_drift: List[AllocationDriftItem] = []
            empty_plan: List[RebalancePlanItem] = []
            for item in target_resp.allocations:
                ac = item.asset_class
                empty_drift.append(
                    AllocationDriftItem(
                        asset_class=ac,
                        current_weight=_ZERO,
                        current_pct=_ZERO,
                        target_weight=item.target_weight,
                        target_pct=item.target_pct,
                        drift=-item.target_weight,
                        drift_pct=-item.target_pct,
                        status="UNDERWEIGHT",
                        action="INCREASE",
                    )
                )
                amt = (
                    (item.target_weight * total_val).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                    if (total_val is not None and total_val > _ZERO)
                    else None
                )
                empty_plan.append(
                    RebalancePlanItem(
                        asset_class=ac,
                        current_weight=_ZERO,
                        target_weight=item.target_weight,
                        drift=-item.target_weight,
                        adjustment_weight=item.target_weight,
                        direction="INCREASE",
                        indicative_amount=amt,
                        benchmark_symbol=item.benchmark_symbol,
                        benchmark_name=item.benchmark_name,
                        explanation=(
                            f"Portfolio is unallocated; allocate {item.target_pct:.1f}% to "
                            f"{ac} to establish initial target profile."
                        ),
                    )
                )
            return SuitabilityRebalanceResponse(
                risk_category=category.value,
                model_code=target_resp.model_code,
                portfolio_id=request.portfolio_id,
                portfolio_value=total_val,
                risk_score_summary=risk_summary,
                drift_summary=empty_drift,
                rebalance_plan=empty_plan,
                max_drift=_ONE,
                rebalance_required=True,
                is_empty_portfolio=True,
                educational_disclaimer=EDUCATIONAL_DISCLAIMER,
            )

        # 4. Standard drift and rebalance plan generation
        drift_items, max_drift, rebal_req = self.calculate_drift(
            current_allocations=current_map,
            target_allocations=targets_map,
            drift_threshold=request.drift_threshold,
        )

        plan = self.generate_rebalance_plan(
            drift_items=drift_items,
            portfolio_value=total_val,
        )

        return SuitabilityRebalanceResponse(
            risk_category=category.value,
            model_code=target_resp.model_code,
            portfolio_id=request.portfolio_id,
            portfolio_value=total_val,
            risk_score_summary=risk_summary,
            drift_summary=drift_items,
            rebalance_plan=plan,
            max_drift=max_drift,
            rebalance_required=rebal_req,
            is_empty_portfolio=False,
            educational_disclaimer=EDUCATIONAL_DISCLAIMER,
        )


# Global singleton service instance
suitability_service = SuitabilityService()
