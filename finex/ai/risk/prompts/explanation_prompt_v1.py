"""Prompt templates and version registry for FinEx Risk Explanation v1 (S2-AI-02).

Strict Compliance:
- Zero recalculation of numeric scores or category mapping.
- Beginner-friendly explanations without financial jargon.
- Direct citation of top influencing questionnaire answers.
- Strict regulatory disclaimers: no guaranteed returns, educational purpose only.
- Strict JSON output structure.
"""

from typing import Any, Dict, List, Optional

PROMPT_VERSION_V1 = "v1.0.0"
SCHEMA_VERSION_V1 = "v1.0.0"

SYSTEM_PROMPT_V1 = """You are the FinEx AI Financial Education Assistant.
Your task is to explain a user's deterministic risk profiling results in plain, beginner-friendly language.

======================================================================
STRICT OPERATIONAL & COMPLIANCE CONSTRAINTS:
======================================================================
1. ZERO NUMERIC DRIFT:
   - You MUST NEVER change, recalculate, adjust, or contradict the numeric scores or category provided in the input.
   - Composite Score, Willingness Score, Capacity Score, and Risk Category are fixed and deterministic.

2. PROHIBITED LANGUAGE & REGULATORY COMPLIANCE:
   - NEVER promise, imply, or guarantee financial returns (e.g., "you will make 10% returns", "safe profit").
   - NEVER provide personalized investment advice or specific ticker recommendations.
   - Clarify that this profile is an educational assessment based solely on self-reported questionnaire answers.

3. BEGINNER-FRIENDLY TONE:
   - Explain financial terms in simple concepts (e.g., explain "volatility" as "the normal ups and downs of prices", "liquidity" as "how quickly you can access your cash").
   - Maintain an encouraging, clear, and objective tone.

4. FACTOR CITATIONS:
   - Directly mention and explain the user's specific answers that most strongly influenced their score (such as reaction to market drops, investment time horizon, or emergency savings cushion).

5. JSON OUTPUT ONLY:
   - You must respond ONLY with a single valid JSON object strictly matching the specified schema. Do not enclose in markdown code blocks if raw JSON is requested, or provide clean JSON inside ```json ... ```.

======================================================================
RESPONSE JSON SCHEMA:
======================================================================
{
  "summary": "String: 2-3 sentences summarizing the overall profile and composite score in beginner terms.",
  "willingness_explanation": "String: 2-3 sentences explaining their psychological comfort with market swings based on their answers.",
  "capacity_explanation": "String: 2-3 sentences explaining their financial ability to take risk (horizon, savings, income).",
  "alignment_analysis": "String: 2-3 sentences explaining whether psychological willingness and financial capacity match or if there is a tension.",
  "key_influencing_factors": [
    {
      "dimension": "willingness" | "capacity",
      "question_id": "String (e.g. W1, C3)",
      "question_text": "String",
      "answer_code": "String (e.g. W1_A, C3_E)",
      "answer_label": "String",
      "score": Integer (1-5),
      "impact": "String (e.g. Low Risk Anchor, Growth Driver, Balance Factor)",
      "explanation": "String explaining how this specific answer shaped the dimension score."
    }
  ],
  "limitations_and_disclaimers": [
    "String: Point-in-time questionnaire disclaimer",
    "String: Educational assessment disclaimer, not individualized financial advice",
    "String: Market investments carry risk of loss with no guaranteed returns"
  ]
}
"""

USER_PROMPT_TEMPLATE_V1 = """Please generate the beginner-friendly risk explanation for the following deterministic assessment:

======================================================================
DETERMINISTIC ASSESSMENT DATA (IMMUTABLE):
======================================================================
- Questionnaire ID: {questionnaire_id} (Version: {version})
- Canonical Risk Category: {risk_category} (Code: {risk_category_code})
- Composite Risk Score: {composite_score}/100
- Willingness Score (Psychological): {willingness_score}/100 (Raw: {willingness_raw}/25)
- Capacity Score (Financial): {capacity_score}/100 (Raw: {capacity_raw}/25)

======================================================================
USER'S QUESTIONNAIRE RESPONSES:
======================================================================
{answers_formatted}

======================================================================
KEY INFLUENCING FACTORS IDENTIFIED BY SCORING ENGINE:
======================================================================
{top_factors_formatted}

Please format your response strictly as the required JSON schema.
"""


def format_user_prompt_v1(
    assessment_data: Dict[str, Any],
    answers_list: List[Dict[str, Any]],
    top_factors: List[Dict[str, Any]],
) -> str:
    """Format the user prompt with deterministic inputs for version v1."""
    answers_lines = []
    for a in answers_list:
        answers_lines.append(
            f"- [{a.get('question_id', '')}] {a.get('question_text', '')}\n"
            f"  User Choice: \"{a.get('answer_label', '')}\" (Code: {a.get('answer_code', '')}, Score: {a.get('score', '')}/5, Dimension: {a.get('dimension', '')})"
        )
    answers_formatted = "\n".join(answers_lines) if answers_lines else "None provided"

    factors_lines = []
    for f in top_factors:
        factors_lines.append(
            f"- [{f.get('dimension', '').upper()}] Question {f.get('question_id', '')}: \"{f.get('answer_label', '')}\" "
            f"(Impact: {f.get('impact', '')}) -> {f.get('explanation', '')}"
        )
    top_factors_formatted = "\n".join(factors_lines) if factors_lines else "Standard balanced factors"

    breakdown = assessment_data.get("breakdown", {})
    w_breakdown = breakdown.get("willingness", {})
    c_breakdown = breakdown.get("capacity", {})

    return USER_PROMPT_TEMPLATE_V1.format(
        questionnaire_id=assessment_data.get("questionnaire_id", "risk_questionnaire_v1"),
        version=assessment_data.get("version", "v1"),
        risk_category=assessment_data.get("risk_category", ""),
        risk_category_code=assessment_data.get("risk_category_code", ""),
        composite_score=assessment_data.get("composite_score", 0.0),
        willingness_score=assessment_data.get("willingness_score", 0.0),
        willingness_raw=w_breakdown.get("raw_score", 0),
        capacity_score=assessment_data.get("capacity_score", 0.0),
        capacity_raw=c_breakdown.get("raw_score", 0),
        answers_formatted=answers_formatted,
        top_factors_formatted=top_factors_formatted,
    )
