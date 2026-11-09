"""Deterministic Risk Result Explanation Engine (S2-AI-02).

Produces beginner-friendly, auditable, and regulatory-compliant explanations
for deterministic risk profiling results.

STRICT COMPLIANCE:
- 100% Deterministic numerical calculations remain outside LLM.
- Zero numeric drift (scores, dimensions, and categories are immutable).
- Directly cites key influencing questionnaire answers and factors.
- Safe non-LLM fallback engine guaranteed for offline/error handling.
- Validated via Pydantic & FastAPI schemas with prompt and schema versioning.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from ai.risk.prompts.explanation_prompt_v1 import (
    PROMPT_VERSION_V1,
    SCHEMA_VERSION_V1,
    SYSTEM_PROMPT_V1,
    format_user_prompt_v1,
)
from ai.risk.schemas import (
    KeyInfluencingFactor,
    QuestionAnswer,
    RiskAssessmentAndExplanationResult,
    RiskAssessmentRequest,
    RiskAssessmentResult,
    RiskCategory,
    RiskExplanationRequest,
    RiskExplanationResponse,
)
from ai.risk.scoring import DEFAULT_CONFIG_PATH, RiskScoringEngine

# Regulatory and methodology disclaimers (standard compliance baseline)
STANDARD_DISCLAIMERS = [
    "This risk profile is an educational assessment based strictly on self-reported questionnaire responses and does not constitute individualized financial, legal, or tax advice.",
    "Investments in financial markets carry inherent risks, including the potential loss of principal. Past performance does not guarantee future results, and no specific returns are guaranteed.",
    "Your financial situation and risk tolerance can evolve over time. You should revisit this assessment periodically or whenever significant life events occur.",
]

# Prohibited phrases for compliance guardrails
PROHIBITED_PHRASES = [
    "guaranteed return",
    "guaranteed profit",
    "risk-free profit",
    "will definitely earn",
    "promise you",
    "sure shot",
    "buy this stock",
    "invest in crypto",
]


class RiskExplanationEngine:
    """Orchestrates prompt creation, structured explanation generation, validation, and safe fallback."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        llm_caller: Optional[Callable[[str, str], str]] = None,
        model_name: str = "gemini-1.5-flash",
    ):
        self.scoring_engine = RiskScoringEngine(config_path=config_path)
        self.config = self.scoring_engine.config
        self.llm_caller = llm_caller
        self.model_name = model_name

    def extract_rich_answers(
        self,
        answers: List[QuestionAnswer],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
        """Enrich raw answers with question text, dimension, label, and score."""
        rich_answers: List[Dict[str, Any]] = []
        answers_map: Dict[str, Dict[str, Any]] = {}

        for a in answers:
            qid = a.question_id.upper()
            code = a.answer_code.upper()
            q_info = self.scoring_engine.questions_by_id.get(qid, {})
            a_info = self.scoring_engine.answers_by_code.get(code, {})

            enriched = {
                "question_id": qid,
                "dimension": q_info.get("dimension", a_info.get("dimension", "unknown")),
                "question_text": q_info.get("text", f"Question {qid}"),
                "answer_code": code,
                "answer_label": a_info.get("label", code),
                "score": a_info.get("score", 3),
            }
            rich_answers.append(enriched)
            answers_map[qid] = enriched

        return rich_answers, answers_map

    def identify_influencing_factors(
        self,
        answers_map: Dict[str, Dict[str, Any]],
        willingness_score: float,
        capacity_score: float,
    ) -> List[KeyInfluencingFactor]:
        """Identify key drivers from questionnaire answers that most heavily shaped the outcome."""
        factors: List[KeyInfluencingFactor] = []

        # Willingness key drivers: W1 (Drawdown reaction), W2 (Comfort with swings), W3 (Goal orientation)
        if "W1" in answers_map:
            w1 = answers_map["W1"]
            score = w1["score"]
            if score <= 2:
                impact = "Conservative Drawdown Anchor"
                expl = "Your preference to sell investments during a 20% market dip signals low psychological tolerance for short-term loss."
            elif score >= 4:
                impact = "High Resilience Growth Driver"
                expl = "Your readiness to hold or buy more during market drops indicates strong emotional resilience to volatility."
            else:
                impact = "Balanced Volatility Stance"
                expl = "Your willingness to wait out market dips reflects a steady, patient attitude towards market cycles."
            factors.append(
                KeyInfluencingFactor(
                    dimension="willingness",
                    question_id="W1",
                    question_text=w1["question_text"],
                    answer_code=w1["answer_code"],
                    answer_label=w1["answer_label"],
                    score=score,
                    impact=impact,
                    explanation=expl,
                )
            )

        if "W2" in answers_map:
            w2 = answers_map["W2"]
            score = w2["score"]
            if score <= 2:
                impact = "Stability Preference"
                expl = "Comfort prioritizing predictable value over sharp month-to-month portfolio fluctuations."
            elif score >= 4:
                impact = "Fluctuation Acceptance"
                expl = "Comfort accepting frequent portfolio value swings in pursuit of longer-term upside."
            else:
                impact = "Moderate Fluctuation Tolerance"
                expl = "Balanced comfort with moderate monthly movements."
            factors.append(
                KeyInfluencingFactor(
                    dimension="willingness",
                    question_id="W2",
                    question_text=w2["question_text"],
                    answer_code=w2["answer_code"],
                    answer_label=w2["answer_label"],
                    score=score,
                    impact=impact,
                    explanation=expl,
                )
            )

        # Capacity key drivers: C1 (Time Horizon), C3 (Emergency Savings), C4 (Income Stability)
        if "C1" in answers_map:
            c1 = answers_map["C1"]
            score = c1["score"]
            if score <= 2:
                impact = "Short Horizon Constraint"
                expl = "Need to withdraw funds within 1-3 years necessitates lower volatility to preserve capital."
            elif score >= 4:
                impact = "Long Horizon Enabler"
                expl = "A 5+ year investment timeline allows adequate time to recover from temporary market pullbacks."
            else:
                impact = "Intermediate Horizon"
                expl = "A 3-5 year investment horizon provides moderate room for balanced market exposure."
            factors.append(
                KeyInfluencingFactor(
                    dimension="capacity",
                    question_id="C1",
                    question_text=c1["question_text"],
                    answer_code=c1["answer_code"],
                    answer_label=c1["answer_label"],
                    score=score,
                    impact=impact,
                    explanation=expl,
                )
            )

        if "C3" in answers_map:
            c3 = answers_map["C3"]
            score = c3["score"]
            if score <= 2:
                impact = "Liquidity Buffer Bottleneck"
                expl = "Limited emergency savings (<1 month) limits capacity to absorb sudden financial shocks."
            elif score >= 4:
                impact = "Strong Safety Buffer"
                expl = "Substantial emergency savings (3-6+ months) protects your investment portfolio from forced early liquidation."
            else:
                impact = "Adequate Emergency Buffer"
                expl = "1-3 months of emergency reserves offers reasonable protection against unplanned cash needs."
            factors.append(
                KeyInfluencingFactor(
                    dimension="capacity",
                    question_id="C3",
                    question_text=c3["question_text"],
                    answer_code=c3["answer_code"],
                    answer_label=c3["answer_label"],
                    score=score,
                    impact=impact,
                    explanation=expl,
                )
            )

        return factors

    def generate_safe_fallback(
        self,
        assessment: RiskAssessmentResult,
        answers: Optional[List[QuestionAnswer]] = None,
        generated_at: Optional[str] = None,
    ) -> RiskExplanationResponse:
        """Generate safe, rule-based deterministic explanation without any external LLM dependencies."""
        w_score = assessment.willingness_score
        c_score = assessment.capacity_score
        comp_score = assessment.composite_score
        category = assessment.risk_category.value

        # Rich answers extraction
        answers_list = answers or []
        _, answers_map = self.extract_rich_answers(answers_list)
        factors = self.identify_influencing_factors(answers_map, w_score, c_score)

        # Summary
        summary = (
            f"Based on your questionnaire responses, your overall risk profile is classified as {category} "
            f"with a composite risk score of {comp_score:.1f} out of 100. This score combines your psychological willingness "
            f"to navigate market movements ({w_score:.1f}/100) with your objective financial capacity to absorb potential losses ({c_score:.1f}/100)."
        )

        # Willingness plain explanation
        if w_score < 34.0:
            w_expl = (
                f"Your Willingness Score of {w_score:.1f}/100 indicates a conservative emotional tolerance for market swings. "
                "You feel most confident when your investments maintain steady, predictable value, and significant temporary market declines causes you discomfort."
            )
        elif w_score < 67.0:
            w_expl = (
                f"Your Willingness Score of {w_score:.1f}/100 demonstrates a moderate emotional tolerance. "
                "You understand that investments experience occasional ups and downs and are willing to accept modest fluctuations in return for balanced potential growth."
            )
        else:
            w_expl = (
                f"Your Willingness Score of {w_score:.1f}/100 demonstrates an aggressive appetite for growth. "
                "You have strong emotional comfort with market volatility and view temporary price pullbacks as normal opportunities rather than reasons to exit."
            )

        # Capacity plain explanation
        if c_score < 34.0:
            c_expl = (
                f"Your Capacity Score of {c_score:.1f}/100 suggests a conservative financial ability to bear investment risk. "
                "Factors such as a shorter investment timeframe, low emergency reserves, or near-term liquidity requirements mean preserving your principal is critical."
            )
        elif c_score < 67.0:
            c_expl = (
                f"Your Capacity Score of {c_score:.1f}/100 reflects a sound, moderate financial foundation. "
                "With an intermediate investment timeline and reasonable emergency savings buffer, your finances can comfortably support a balanced mix of growth and stability."
            )
        else:
            c_expl = (
                f"Your Capacity Score of {c_score:.1f}/100 indicates strong financial resilience. "
                "A long-term investment horizon, stable income, and robust emergency savings allow you to weather extended market downturns without risking your daily financial security."
            )

        # Alignment analysis
        w_cat = "Conservative" if w_score < 34.0 else ("Moderate" if w_score < 67.0 else "Aggressive")
        c_cat = "Conservative" if c_score < 34.0 else ("Moderate" if c_score < 67.0 else "Aggressive")

        if w_cat == "Aggressive" and c_cat == "Conservative":
            alignment = (
                "Important Tension: Your psychological desire for high growth is aggressive, but your objective financial capacity is conservative. "
                "In responsible wealth planning, objective financial capacity must take precedence to prevent cash shortages during market downturns."
            )
        elif w_cat == "Conservative" and c_cat == "Aggressive":
            alignment = (
                "Important Note: Even though your strong financial position could absorb aggressive market risk, your psychological preference is conservative. "
                "Your investment strategy should respect your comfort zone so you never feel pressured to make emotional decisions during volatile periods."
            )
        elif w_cat == c_cat:
            alignment = (
                f"Your psychological comfort and financial capacity are in strong harmony within the {category} tier. "
                "This clear alignment makes it straightforward to structure an investment strategy that fits both your emotional mindset and financial realities."
            )
        else:
            alignment = (
                f"Your profile balances a {w_cat.lower()} psychological willingness with a {c_cat.lower()} financial capacity, "
                f"resulting in an overall balanced {category} classification."
            )

        ts = generated_at or datetime.now(timezone.utc).isoformat()

        return RiskExplanationResponse(
            summary=summary,
            willingness_explanation=w_expl,
            capacity_explanation=c_expl,
            alignment_analysis=alignment,
            key_influencing_factors=factors,
            limitations_and_disclaimers=STANDARD_DISCLAIMERS,
            is_fallback=True,
            model_version="deterministic_rule_v1.0.0",
            prompt_version=PROMPT_VERSION_V1,
            schema_version=SCHEMA_VERSION_V1,
            generated_at=ts,
        )

    def validate_llm_json_response(
        self,
        raw_text: str,
        assessment: RiskAssessmentResult,
    ) -> Optional[RiskExplanationResponse]:
        """Validate LLM output against Pydantic schema, safety checks, and compliance rules."""
        # 1. Clean markdown code blocks if present
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # 2. Parse JSON
        try:
            data = json.loads(cleaned)
        except Exception:
            return None

        # 3. Check prohibited return guarantees or advice
        dumped_text = json.dumps(data).lower()
        for phrase in PROHIBITED_PHRASES:
            if phrase in dumped_text:
                return None

        # 4. Validate Pydantic schema
        try:
            # Ensure mandatory fields exist
            if not isinstance(data.get("summary"), str) or not data["summary"]:
                return None
            if not isinstance(data.get("willingness_explanation"), str) or not data["willingness_explanation"]:
                return None
            if not isinstance(data.get("capacity_explanation"), str) or not data["capacity_explanation"]:
                return None
            if not isinstance(data.get("alignment_analysis"), str) or not data["alignment_analysis"]:
                return None

            # Check factor list structure
            raw_factors = data.get("key_influencing_factors", [])
            parsed_factors: List[KeyInfluencingFactor] = []
            for f in raw_factors:
                if isinstance(f, dict):
                    parsed_factors.append(KeyInfluencingFactor(**f))

            disclaimers = data.get("limitations_and_disclaimers", [])
            if not disclaimers:
                disclaimers = STANDARD_DISCLAIMERS

            ts = datetime.now(timezone.utc).isoformat()

            return RiskExplanationResponse(
                summary=data["summary"],
                willingness_explanation=data["willingness_explanation"],
                capacity_explanation=data["capacity_explanation"],
                alignment_analysis=data["alignment_analysis"],
                key_influencing_factors=parsed_factors,
                limitations_and_disclaimers=disclaimers,
                is_fallback=False,
                model_version=self.model_name,
                prompt_version=PROMPT_VERSION_V1,
                schema_version=SCHEMA_VERSION_V1,
                generated_at=ts,
            )
        except Exception:
            return None

    def explain(
        self,
        assessment: RiskAssessmentResult,
        answers: Optional[List[QuestionAnswer]] = None,
        force_fallback: bool = False,
        generated_at: Optional[str] = None,
    ) -> RiskExplanationResponse:
        """Generate structured explanation with automatic fallback on failure."""
        answers_list = answers or []

        # If fallback is forced or no LLM caller configured, run deterministic fallback
        if force_fallback or self.llm_caller is None:
            return self.generate_safe_fallback(assessment, answers=answers_list, generated_at=generated_at)

        # Build prompt
        try:
            rich_answers, answers_map = self.extract_rich_answers(answers_list)
            factors = self.identify_influencing_factors(
                answers_map,
                assessment.willingness_score,
                assessment.capacity_score,
            )
            factors_dict = [f.model_dump() for f in factors]

            assessment_dict = {
                "questionnaire_id": assessment.questionnaire_id,
                "version": assessment.version,
                "risk_category": assessment.risk_category.value,
                "risk_category_code": assessment.risk_category_code,
                "composite_score": assessment.composite_score,
                "willingness_score": assessment.willingness_score,
                "capacity_score": assessment.capacity_score,
                "breakdown": assessment.breakdown.model_dump(),
            }

            user_prompt = format_user_prompt_v1(assessment_dict, rich_answers, factors_dict)
            raw_response = self.llm_caller(SYSTEM_PROMPT_V1, user_prompt)

            validated = self.validate_llm_json_response(raw_response, assessment)
            if validated is not None:
                if generated_at is not None:
                    validated.generated_at = generated_at
                return validated
        except Exception:
            pass

        # Safe fallback on any error
        return self.generate_safe_fallback(assessment, answers=answers_list, generated_at=generated_at)


# Global default engine instance
_explanation_engine: Optional[RiskExplanationEngine] = None


def get_explanation_engine() -> RiskExplanationEngine:
    """Retrieve or initialize singleton RiskExplanationEngine."""
    global _explanation_engine
    if _explanation_engine is None:
        _explanation_engine = RiskExplanationEngine()
    return _explanation_engine


def explain_risk_assessment(
    assessment: RiskAssessmentResult,
    answers: Optional[List[QuestionAnswer]] = None,
    force_fallback: bool = False,
    llm_caller: Optional[Callable[[str, str], str]] = None,
    generated_at: Optional[str] = None,
) -> RiskExplanationResponse:
    """Explain pre-computed risk assessment with fallback safety."""
    if llm_caller is not None:
        engine = RiskExplanationEngine(llm_caller=llm_caller)
    else:
        engine = get_explanation_engine()
    return engine.explain(
        assessment,
        answers=answers,
        force_fallback=force_fallback,
        generated_at=generated_at,
    )


def evaluate_and_explain(
    request: Union[RiskAssessmentRequest, RiskExplanationRequest, Dict[str, Any]],
    force_fallback: bool = False,
    llm_caller: Optional[Callable[[str, str], str]] = None,
) -> RiskAssessmentAndExplanationResult:
    """Convenience function: computes deterministic score and structured explanation together."""
    if isinstance(request, dict):
        if "answers" in request and isinstance(request["answers"], list):
            req_answers = [
                QuestionAnswer(**a) if isinstance(a, dict) else a
                for a in request["answers"]
            ]
            scoring_req = RiskAssessmentRequest(
                questionnaire_id=request.get("questionnaire_id", "risk_questionnaire_v1"),
                version=request.get("version", "v1"),
                user_id=request.get("user_id"),
                calculated_at=request.get("calculated_at"),
                answers=req_answers,
            )
            force_fb = request.get("force_fallback", force_fallback)
        else:
            raise ValueError("Invalid request format: 'answers' list required")
    elif isinstance(request, RiskExplanationRequest):
        if request.assessment is not None:
            explanation = explain_risk_assessment(
                assessment=request.assessment,
                answers=request.answers,
                force_fallback=request.force_fallback or force_fallback,
                llm_caller=llm_caller,
                generated_at=request.calculated_at,
            )
            return RiskAssessmentAndExplanationResult(
                assessment=request.assessment,
                explanation=explanation,
            )
        elif request.answers is not None:
            scoring_req = RiskAssessmentRequest(
                questionnaire_id=request.questionnaire_id,
                version=request.version,
                user_id=request.user_id,
                calculated_at=request.calculated_at,
                answers=request.answers,
            )
            force_fb = request.force_fallback or force_fallback
        else:
            raise ValueError("Either 'assessment' or 'answers' must be provided in RiskExplanationRequest")
    elif isinstance(request, RiskAssessmentRequest):
        scoring_req = request
        force_fb = force_fallback
    else:
        raise TypeError(f"Unsupported request type: {type(request)}")

    # Deterministic calculation outside LLM
    scoring_engine = RiskScoringEngine()
    assessment_result = scoring_engine.evaluate(scoring_req, calculated_at=scoring_req.calculated_at)

    # Explanation generation
    explanation_result = explain_risk_assessment(
        assessment=assessment_result,
        answers=scoring_req.answers,
        force_fallback=force_fb,
        llm_caller=llm_caller,
        generated_at=scoring_req.calculated_at,
    )

    return RiskAssessmentAndExplanationResult(
        assessment=assessment_result,
        explanation=explanation_result,
    )
