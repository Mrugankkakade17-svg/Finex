"""Deterministic Risk Scoring Engine v1.

Evaluates risk profiles based on approved questionnaire weights, separating
Willingness (psychological) and Capacity (financial) dimensions into normalized
scores and mapping them to Conservative, Moderate, or Aggressive categories.

STRICT COMPLIANCE:
- 100% Deterministic (No LLM for numeric scoring)
- Auditable & Reproducible
- Safe rule-based non-LLM explanation fallback
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from ai.risk.schemas import (
    DimensionScore,
    NonLLMExplanation,
    QuestionAnswer,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskCategory,
    RiskScoreBreakdown,
)

def _find_canonical_config() -> Path:
    """Resolve canonical S2-DAT-02 risk questionnaire configuration path."""
    candidates = [
        Path(__file__).resolve().parents[2] / "backend" / "data" / "questionnaire" / "risk_questionnaire_v1.json",
        Path.cwd() / "backend" / "data" / "questionnaire" / "risk_questionnaire_v1.json",
        Path.cwd() / "data" / "questionnaire" / "risk_questionnaire_v1.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_CONFIG_PATH = _find_canonical_config()


class RiskScoringEngine:
    """Deterministic scoring engine implementing FinEx Risk Questionnaire v1."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if not path.exists():
            path = _find_canonical_config()
            if not path.exists():
                raise FileNotFoundError(f"Canonical questionnaire config not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self._build_indexes()

    def _build_indexes(self) -> None:
        """Build fast lookup dictionaries from questionnaire configuration."""
        self.questionnaire_id = self.config["questionnaire"]["questionnaire_id"]
        self.version_label = self.config["questionnaire"]["version_label"]

        self.questions_by_id: Dict[str, Dict[str, Any]] = {}
        self.answers_by_code: Dict[str, Dict[str, Any]] = {}
        self.dimension_questions: Dict[str, List[str]] = {"willingness": [], "capacity": []}

        for q in self.config["questions"]:
            qid = q["question_id"].upper()
            dim = q["dimension"].lower()
            self.questions_by_id[qid] = q
            if dim in self.dimension_questions:
                self.dimension_questions[dim].append(qid)

            for a in q["answers"]:
                code = a["code"].upper()
                self.answers_by_code[code] = {
                    "question_id": qid,
                    "dimension": dim,
                    "score": a["proposed_score"],
                    "label": a["label"],
                }

        scoring_cfg = self.config.get("scoring", {})
        self.raw_min = scoring_cfg.get("dimension_raw_range", {}).get("min", 5)
        self.raw_max = scoring_cfg.get("dimension_raw_range", {}).get("max", 25)
        self.w_weight = scoring_cfg.get("combination", {}).get("willingness_weight", 0.5)
        self.c_weight = scoring_cfg.get("combination", {}).get("capacity_weight", 0.5)
        self.boundaries = scoring_cfg.get(
            "category_boundaries",
            [
                {"min": 0, "max": 33.99, "category": "Conservative"},
                {"min": 34, "max": 66.99, "category": "Moderate"},
                {"min": 67, "max": 100, "category": "Aggressive"},
            ],
        )

    def normalize_dimension(self, raw_sum: int) -> float:
        """Normalize raw dimension sum (5..25) to standard 0..100 scale."""
        if self.raw_max == self.raw_min:
            return 0.0
        clamped_raw = max(self.raw_min, min(self.raw_max, raw_sum))
        normalized = ((clamped_raw - self.raw_min) / (self.raw_max - self.raw_min)) * 100.0
        return round(normalized, 4)

    def calculate_composite_score(self, willingness_score: float, capacity_score: float) -> float:
        """Compute weighted composite score from willingness and capacity."""
        composite = (willingness_score * self.w_weight) + (capacity_score * self.c_weight)
        return round(composite, 4)

    def map_to_category(self, composite_score: float) -> Tuple[RiskCategory, str]:
        """Map composite score to canonical RiskCategory and uppercase code."""
        # Clean boundary checks
        if composite_score < 34.0:
            return RiskCategory.CONSERVATIVE, "CONSERVATIVE"
        elif composite_score < 67.0:
            return RiskCategory.MODERATE, "MODERATE"
        else:
            return RiskCategory.AGGRESSIVE, "AGGRESSIVE"

    def _generate_explanation(
        self,
        willingness_score: float,
        capacity_score: float,
        composite_score: float,
        category: RiskCategory,
    ) -> NonLLMExplanation:
        """Generate safe, rule-based deterministic explanation without LLM."""
        # Willingness narrative
        if willingness_score < 34.0:
            w_desc = "Your responses reflect a low tolerance for market volatility, indicating an emotional preference for capital preservation over rapid growth."
        elif willingness_score < 67.0:
            w_desc = "Your responses indicate a moderate comfort level with market fluctuations, seeking balanced growth without taking excessive emotional stress."
        else:
            w_desc = "Your responses demonstrate a strong psychological resilience to short-term drawdowns, with an appetite for aggressive growth opportunities."

        # Capacity narrative
        if capacity_score < 34.0:
            c_desc = "Your current financial profile suggests a shorter investment horizon, liquidity needs, or lower emergency reserves, limiting your capacity to absorb capital losses."
        elif capacity_score < 67.0:
            c_desc = "Your financial position shows an adequate investment horizon, stable income, and sufficient emergency buffer to support a balanced investment strategy."
        else:
            c_desc = "Your financial profile indicates a long-term investment horizon, strong income stability, and robust emergency savings capable of weathering economic cycles."

        # Alignment analysis
        w_cat, _ = self.map_to_category(willingness_score)
        c_cat, _ = self.map_to_category(capacity_score)

        if w_cat == RiskCategory.AGGRESSIVE and c_cat == RiskCategory.CONSERVATIVE:
            alignment = (
                "Important Guidance: Your personal appetite for risk is high, but your current financial capacity is conservative. "
                "In financial planning, objective capacity must guard against excessive downside risk."
            )
        elif w_cat == RiskCategory.CONSERVATIVE and c_cat == RiskCategory.AGGRESSIVE:
            alignment = (
                "Guidance: While your strong financial position can technically absorb market risk, your psychological preference is conservative. "
                "Your portfolio strategy should honor your comfort zone to prevent panic-selling."
            )
        elif w_cat == c_cat:
            alignment = f"Your psychological risk willingness and objective financial capacity are harmoniously aligned in the {category.value} tier."
        else:
            alignment = f"Your profile balances a {w_cat.value.lower()} willingness with a {c_cat.value.lower()} capacity, yielding an overall {category.value} classification."

        summary = (
            f"You have been categorized as a {category.value} investor (Composite Risk Score: {composite_score:.1f}/100), "
            f"reflecting a Willingness Score of {willingness_score:.1f}/100 and a Capacity Score of {capacity_score:.1f}/100."
        )

        return NonLLMExplanation(
            summary=summary,
            willingness_rationale=w_desc,
            capacity_rationale=c_desc,
            alignment_note=alignment,
            is_fallback=True,
        )

    def evaluate(
        self,
        request: RiskAssessmentRequest,
        calculated_at: Optional[Union[datetime, str]] = None,
    ) -> RiskAssessmentResult:
        """Evaluate a set of answers deterministically and return validated result."""
        # 1. Validate questionnaire ID
        if request.questionnaire_id != self.questionnaire_id:
            raise ValueError(
                f"Invalid questionnaire_id: '{request.questionnaire_id}'. Expected '{self.questionnaire_id}'."
            )

        # 2. Check duplicate answers for the same question
        seen_questions = set()
        answers_map: Dict[str, QuestionAnswer] = {}
        for ans in request.answers:
            qid = ans.question_id.upper()
            if qid in seen_questions:
                raise ValueError(f"Duplicate answer submitted for question: '{qid}'")
            seen_questions.add(qid)
            answers_map[qid] = ans

        # 3. Check that all required questions are answered
        missing_questions = []
        for qid, q in self.questions_by_id.items():
            if q.get("required", True) and qid not in answers_map:
                missing_questions.append(qid)

        if missing_questions:
            raise ValueError(f"Missing required questions: {sorted(missing_questions)}")

        # 4. Calculate raw sums for each dimension
        w_raw = 0
        c_raw = 0

        for qid, ans in answers_map.items():
            if qid not in self.questions_by_id:
                raise ValueError(f"Unknown question_id: '{qid}'")

            code = ans.answer_code.upper()
            if code not in self.answers_by_code:
                raise ValueError(f"Invalid answer_code: '{code}' for question '{qid}'")

            answer_meta = self.answers_by_code[code]
            if answer_meta["question_id"] != qid:
                raise ValueError(f"Answer code '{code}' does not belong to question '{qid}'")

            score = answer_meta["score"]
            dim = answer_meta["dimension"]

            if dim == "willingness":
                w_raw += score
            elif dim == "capacity":
                c_raw += score

        # 5. Normalization (0..100)
        w_normalized = self.normalize_dimension(w_raw)
        c_normalized = self.normalize_dimension(c_raw)

        # 6. Composite Score (0..100)
        composite = self.calculate_composite_score(w_normalized, c_normalized)

        # 7. Category Mapping
        category, cat_code = self.map_to_category(composite)

        # 8. Deterministic Explanation
        explanation = self._generate_explanation(w_normalized, c_normalized, composite, category)

        # 9. Structure Result with deterministic or live timestamp
        if calculated_at is not None:
            ts = calculated_at.isoformat() if isinstance(calculated_at, datetime) else str(calculated_at)
        elif request.calculated_at is not None:
            ts = request.calculated_at
        else:
            ts = datetime.now(timezone.utc).isoformat()

        breakdown = RiskScoreBreakdown(
            willingness=DimensionScore(
                dimension="willingness",
                raw_score=w_raw,
                min_raw=self.raw_min,
                max_raw=self.raw_max,
                normalized_score=w_normalized,
                weight=self.w_weight,
            ),
            capacity=DimensionScore(
                dimension="capacity",
                raw_score=c_raw,
                min_raw=self.raw_min,
                max_raw=self.raw_max,
                normalized_score=c_normalized,
                weight=self.c_weight,
            ),
        )

        return RiskAssessmentResult(
            questionnaire_id=self.questionnaire_id,
            version=self.version_label,
            willingness_score=w_normalized,
            capacity_score=c_normalized,
            composite_score=composite,
            risk_category=category,
            risk_category_code=cat_code,
            breakdown=breakdown,
            explanation=explanation,
            model_version="deterministic_v1.0.0",
            schema_version="v1.0.0",
            calculated_at=ts,
        )


# Singleton instance for quick module access
_engine = None


def calculate_risk_score(
    answers: Union[List[Dict[str, str]], List[QuestionAnswer]],
    questionnaire_id: str = "risk_questionnaire_v1",
    version: str = "v1",
    user_id: Optional[str] = None,
    calculated_at: Optional[Union[datetime, str]] = None,
) -> RiskAssessmentResult:
    """Top-level convenience function for deterministic risk scoring."""
    global _engine
    if _engine is None:
        _engine = RiskScoringEngine()

    parsed_answers: List[QuestionAnswer] = []
    for a in answers:
        if isinstance(a, QuestionAnswer):
            parsed_answers.append(a)
        elif isinstance(a, dict):
            parsed_answers.append(QuestionAnswer(**a))
        else:
            raise TypeError(f"Invalid answer format: {type(a)}")

    ts_str = None
    if calculated_at is not None:
        ts_str = calculated_at.isoformat() if isinstance(calculated_at, datetime) else str(calculated_at)

    request = RiskAssessmentRequest(
        questionnaire_id=questionnaire_id,
        version=version,
        user_id=user_id,
        calculated_at=ts_str,
        answers=parsed_answers,
    )
    return _engine.evaluate(request, calculated_at=calculated_at)
