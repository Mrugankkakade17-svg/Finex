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
import math
from copy import deepcopy
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
        Path(__file__).resolve().parents[2]
        / "backend"
        / "data"
        / "questionnaire"
        / "risk_questionnaire_v1.json",
        Path.cwd() / "backend" / "data" / "questionnaire" / "risk_questionnaire_v1.json",
        Path.cwd() / "data" / "questionnaire" / "risk_questionnaire_v1.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_CONFIG_PATH = _find_canonical_config()


def _snapshot_object(value: object, fields: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != fields:
        raise ValueError("Unsupported rules snapshot object shape.")
    return value


def _snapshot_array(value: object, length: int) -> list[Any]:
    if type(value) is not list or len(value) != length:
        raise ValueError("Unsupported rules snapshot array shape.")
    return value


def _snapshot_text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError("Rules snapshot text must be a nonempty JSON string.")
    return value


def _snapshot_number(value: object) -> None:
    if type(value) is not int and type(value) is not float:
        raise ValueError("Rules snapshot numbers cannot be coerced from other types.")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("Rules snapshot numbers must be finite.")


def _snapshot_timestamp(value: object) -> None:
    parsed = datetime.fromisoformat(_snapshot_text(value))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Rules snapshot metadata times must include an offset.")


class RiskScoringEngine:
    """Deterministic scoring engine implementing FinEx Risk Questionnaire v1."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        if not path.exists():
            raise FileNotFoundError(f"Canonical questionnaire config not found at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self._validate_v1_policy()
        self._build_indexes()

    @classmethod
    def from_config(cls, snapshot: object) -> "RiskScoringEngine":
        """Use an independent validated snapshot without writing temporary files.

        The normal file-backed constructor remains unchanged. Stored history
        uses the same policy/index building and numeric methods, never today's
        file or a replacement calculation time.
        """
        if type(snapshot) is not dict:
            raise ValueError("The rules snapshot must be a JSON object.")
        instance = cls.__new__(cls)
        instance.config = deepcopy(snapshot)
        instance._validate_snapshot_shape()
        # Do not coerce tuples, booleans or numeric strings into JSON policy data.
        json.dumps(instance.config, allow_nan=False)
        instance._validate_v1_policy()
        instance._build_indexes()
        return instance

    def _validate_snapshot_shape(self) -> None:
        """Check stored JSON types/order without changing pilot policy or math.

        Equality-based numeric policy checks alone cannot distinguish True from
        1 or preserve canonical option order. This boundary is used only by the
        explicit snapshot factory; the existing file-backed constructor retains
        its original behavior and the v1 policy remains the numeric authority.
        """
        config = _snapshot_object(self.config, {"questionnaire", "questions", "scoring"})
        metadata = _snapshot_object(
            config["questionnaire"],
            {"questionnaire_id", "version_label", "title", "status", "active_from", "retired_at"},
        )
        for field in ("questionnaire_id", "version_label", "title", "status"):
            _snapshot_text(metadata[field])
        _snapshot_timestamp(metadata["active_from"])
        if metadata["retired_at"] is not None:
            _snapshot_timestamp(metadata["retired_at"])

        questions = _snapshot_array(config["questions"], 10)
        for position, value in enumerate(questions, 1):
            question = _snapshot_object(
                value,
                {
                    "position",
                    "question_id",
                    "dimension",
                    "text",
                    "response_type",
                    "required",
                    "answers",
                },
            )
            if type(question["position"]) is not int or question["position"] != position:
                raise ValueError("Rules snapshot question positions must preserve canonical order.")
            for field in ("question_id", "dimension", "text", "response_type"):
                _snapshot_text(question[field])
            if question["response_type"] != "single_choice" or question["required"] is not True:
                raise ValueError("Unsupported rules snapshot question response shape.")
            answers = _snapshot_array(question["answers"], 5)
            for letter, answer_value in zip("ABCDE", answers):
                answer = _snapshot_object(answer_value, {"code", "label", "proposed_score"})
                _snapshot_text(answer["code"])
                _snapshot_text(answer["label"])
                if answer["code"] != f"{question['question_id']}_{letter}":
                    raise ValueError("Rules snapshot options must preserve canonical order.")
                score = answer["proposed_score"]
                if type(score) is not int or not 1 <= score <= 5:
                    raise ValueError(
                        "Rules snapshot option scores must be JSON integers 1 through 5."
                    )

        scoring = _snapshot_object(
            config["scoring"],
            {
                "status",
                "dimension_raw_range",
                "normalization",
                "combination",
                "category_boundaries",
            },
        )
        _snapshot_text(scoring["status"])
        raw_range = _snapshot_object(scoring["dimension_raw_range"], {"min", "max"})
        for value in raw_range.values():
            _snapshot_number(value)
        if scoring["normalization"] != "((raw_sum - 5) / (25 - 5)) * 100":
            raise ValueError("Unsupported rules snapshot normalization description.")
        combination = _snapshot_object(
            scoring["combination"], {"formula", "willingness_weight", "capacity_weight"}
        )
        if combination["formula"] != "(willingness_score * 0.5) + (capacity_score * 0.5)":
            raise ValueError("Unsupported rules snapshot combination description.")
        for field in ("willingness_weight", "capacity_weight"):
            _snapshot_number(combination[field])
        for value in _snapshot_array(scoring["category_boundaries"], 3):
            boundary = _snapshot_object(value, {"min", "max", "category"})
            _snapshot_number(boundary["min"])
            _snapshot_number(boundary["max"])
            _snapshot_text(boundary["category"])

    def _validate_v1_policy(self) -> None:
        """Fail closed if an approved, immutable v1 policy has drifted."""
        expected_ids = [f"{dimension}{index}" for dimension in ("W", "C") for index in range(1, 6)]
        metadata = self.config["questionnaire"]
        scoring = self.config["scoring"]
        if (
            metadata["questionnaire_id"] != "risk_questionnaire_v1"
            or metadata["version_label"] != "v1"
            or metadata["status"] != "APPROVED"
            or scoring["status"] != "APPROVED"
            or scoring["dimension_raw_range"] != {"min": 5, "max": 25}
            or scoring["combination"]["willingness_weight"] != 0.5
            or scoring["combination"]["capacity_weight"] != 0.5
        ):
            raise ValueError("Unsupported or changed v1 scoring policy; publish a new version.")
        questions = self.config["questions"]
        if [question["question_id"] for question in questions] != expected_ids:
            raise ValueError("Changed v1 questionnaire membership; publish a new version.")
        for question in questions:
            qid = question["question_id"]
            dimension = "willingness" if qid.startswith("W") else "capacity"
            if question["dimension"] != dimension or question["required"] is not True:
                raise ValueError("Changed v1 question dimensions; publish a new version.")
            expected_answers = {f"{qid}_{letter}": score for score, letter in enumerate("ABCDE", 1)}
            actual_answers = {
                answer["code"]: answer["proposed_score"] for answer in question["answers"]
            }
            if actual_answers != expected_answers or len(question["answers"]) != 5:
                raise ValueError("Changed v1 answer weights; publish a new version.")
        expected_boundaries = [
            {"min": 0, "max": 33.99, "category": "Conservative"},
            {"min": 34, "max": 66.99, "category": "Moderate"},
            {"min": 67, "max": 100, "category": "Aggressive"},
        ]
        if scoring["category_boundaries"] != expected_boundaries:
            raise ValueError("Changed v1 category boundaries; publish a new version.")

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
        w_cat, _ = self.map_to_category(willingness_score)
        c_cat, _ = self.map_to_category(capacity_score)
        w_desc = (
            f"Self-reported willingness answers produce {willingness_score:g}/100 "
            f"in the {w_cat.value} model band. This does not verify future behavior."
        )
        c_desc = (
            f"Self-reported capacity answers produce {capacity_score:g}/100 "
            f"in the {c_cat.value} model band. "
            "Financial circumstances are not independently verified."
        )
        alignment = (
            f"The self-reported capacity is {c_cat.value.lower()} in this model and the "
            f"psychological preference is {w_cat.value.lower()} in this model. "
            "Any difference is informational, not a suitability decision or recommendation."
        )
        summary = (
            f"The self-reported v1 questionnaire produces the {category.value} model band "
            f"(composite {composite_score:g}/100). This is educational and not investment advice."
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
                f"Invalid questionnaire_id: '{request.questionnaire_id}'. "
                f"Expected '{self.questionnaire_id}'."
            )

        # 2. Check duplicate answers for the same question
        if request.version != self.version_label:
            raise ValueError("Unsupported questionnaire version.")
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
            ts = (
                calculated_at.isoformat()
                if isinstance(calculated_at, datetime)
                else str(calculated_at)
            )
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
        ts_str = (
            calculated_at.isoformat() if isinstance(calculated_at, datetime) else str(calculated_at)
        )

    request = RiskAssessmentRequest(
        questionnaire_id=questionnaire_id,
        version=version,
        user_id=user_id,
        calculated_at=ts_str,
        answers=parsed_answers,
    )
    return _engine.evaluate(request, calculated_at=calculated_at)
