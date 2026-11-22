"""
deterministic_adapter.py

Safe, template-based deterministic fallback adapter.
Operates completely offline with zero network calls and zero external API dependencies.
Guarantees 100% reproducible safe answers conforming to the requested schema.
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import re
from typing import Any

from app.adapters.llm.schema_validator import SchemaValidator
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse

FALLBACK_MODEL_NAME = "deterministic-fallback-v1"

PROHIBITED_ADVICE_KEYWORDS: list[str] = [
    r"\bshould I buy\b",
    r"\bshould I sell\b",
    r"\bwhich stock to buy\b",
    r"\bpredict tomorrow\b",
    r"\bguaranteed return\b",
    r"\bhot stock\b",
    r"\bguaranteed profit\b",
    r"\brisk-free\b",
]

COMPILED_REFUSAL_PATTERNS = [re.compile(p, re.IGNORECASE) for p in PROHIBITED_ADVICE_KEYWORDS]

OUTAGE_DISCLAIMER = (
    "FinEx educational prototype: Safe deterministic fallback generated during provider outage. "
    "Not personalized financial, legal, or investment advice."
)


class DeterministicFallbackAdapter(LLMProvider):
    """Pure offline, template-driven fallback provider executing with zero network calls."""

    def __init__(self, model_name: str = FALLBACK_MODEL_NAME) -> None:
        self.model_name = model_name

    def _is_refusal_query(self, query: str) -> bool:
        if not query:
            return False
        return any(pattern.search(query) for pattern in COMPILED_REFUSAL_PATTERNS)

    def _extract_citations(self, request: LLMRequest) -> list[str]:
        citations = []
        raw_citations = request.context.get("citations", [])
        if isinstance(raw_citations, list):
            for item in raw_citations:
                if isinstance(item, str):
                    citations.append(item)
                elif isinstance(item, dict) and "chunk_id" in item:
                    citations.append(str(item["chunk_id"]))
                elif hasattr(item, "chunk_id"):
                    citations.append(str(getattr(item, "chunk_id")))

        raw_chunks = request.context.get("chunks", [])
        if isinstance(raw_chunks, list):
            for chunk in raw_chunks:
                if isinstance(chunk, dict) and "chunk_id" in chunk:
                    citations.append(str(chunk["chunk_id"]))
                elif isinstance(chunk, str) and chunk.startswith("chunk-"):
                    citations.append(chunk)

        # De-duplicate while preserving order
        return list(dict.fromkeys(citations))

    def _generate_chat_output(self, request: LLMRequest, citations: list[str]) -> dict[str, Any]:
        query = str(
            request.context.get("query")
            or request.context.get("message")
            or request.context.get("question")
            or ""
        )

        if self._is_refusal_query(query):
            return {
                "intent": "REFUSAL_FINANCIAL_ADVICE",
                "answer_text": (
                    "As an educational assistant, FinEx cannot provide specific buy/sell "
                    "recommendations or predict individual stock performance. We encourage "
                    "reviewing asset allocation fundamentals and consulting an advisor."
                ),
                "citations": citations,
                "limitations_disclaimer": OUTAGE_DISCLAIMER,
                "safe_fallback_used": True,
            }

        topic = "general financial education"
        lower_q = query.lower()
        if "diversif" in lower_q or "allocat" in lower_q:
            topic = "portfolio diversification and asset allocation"
            explanation = (
                "Asset allocation and diversification spread capital across non-correlated "
                "asset classes (such as equities, debt, and cash) to balance risk."
            )
        elif "volatil" in lower_q or "risk" in lower_q:
            topic = "market volatility and risk management"
            explanation = (
                "Volatility measures the frequency and magnitude of price fluctuations over "
                "time. Managing risk involves distinguishing between volatility and loss."
            )
        elif "compound" in lower_q or "dca" in lower_q or "dollar cost" in lower_q:
            topic = "dollar-cost averaging and compounding"
            explanation = (
                "Dollar-cost averaging (DCA) commits fixed capital at disciplined intervals "
                "regardless of short-term fluctuations, harnessing compound growth."
            )
        else:
            explanation = (
                "FinEx educational curriculum emphasizes fundamental concepts: emergency "
                "funds, aligning allocation with goals, and managing portfolio risk."
            )

        citation_note = f" (Referencing {len(citations)} curriculum sources)." if citations else ""

        return {
            "intent": "CONCEPT_EDUCATION",
            "answer_text": f"Educational overview regarding {topic}: {explanation}{citation_note}",
            "citations": citations,
            "limitations_disclaimer": OUTAGE_DISCLAIMER,
            "safe_fallback_used": True,
        }

    def _generate_risk_output(self, request: LLMRequest) -> dict[str, Any]:
        risk_category = request.context.get("risk_category", "Moderate")
        willingness = request.context.get("willingness_score", 50.0)
        capacity = request.context.get("capacity_score", 50.0)
        composite = request.context.get("composite_score", 50.0)

        return {
            "summary": (
                f"Your assessment indicates a {risk_category} risk profile with a composite "
                f"score of {composite:.1f}, reflecting your self-reported responses."
            ),
            "willingness_explanation": (
                f"Your self-reported willingness score of {willingness:.1f} indicates your "
                "behavioral comfort with short-term market volatility."
            ),
            "capacity_explanation": (
                f"Your self-reported capacity score of {capacity:.1f} indicates your financial "
                "ability to absorb fluctuations based on time horizon and liquidity."
            ),
            "alignment_analysis": (
                "Your willingness and capacity scores indicate consistent alignment, "
                "supporting a balanced portfolio structure."
            ),
            "key_influencing_factors": [
                {
                    "dimension": "willingness",
                    "question_id": "W1",
                    "question_text": "Reaction to market drawdown",
                    "answer_code": "W1_B",
                    "answer_label": "Wait patiently for recovery",
                    "score": 3,
                    "impact": "Balanced Stance",
                    "explanation": "Consistent with disciplined market participation.",
                }
            ],
            "limitations_and_disclaimers": [
                OUTAGE_DISCLAIMER,
                "This profile is educational and does not constitute investment advice.",
            ],
            "is_fallback": True,
        }

    def _generate_goal_output(self, request: LLMRequest) -> dict[str, Any]:
        goal_name = request.context.get("goal_name", "Financial Goal")
        return {
            "explanation": (
                f"For your goal '{goal_name}', deterministic tracking models project portfolio "
                "progression based on disciplined contributions and target asset allocation."
            ),
            "disclaimer": OUTAGE_DISCLAIMER,
        }

    def _generate_generic_output(self, request: LLMRequest) -> dict[str, Any]:
        prompt_id = request.prompt_id
        return {
            "response": (
                f"Deterministic fallback processed request '{prompt_id}'. "
                "All operational calculations remain deterministic and non-networked."
            ),
            "explanation": "Deterministic educational response generated safely during outage.",
            "disclaimer": OUTAGE_DISCLAIMER,
        }

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Produce safe deterministic output conforming to schema with zero network calls."""
        citations = self._extract_citations(request)
        normalized_ref = request.output_schema_ref.strip().lower()

        if "risk" in normalized_ref:
            raw_output = self._generate_risk_output(request)
        elif "goal" in normalized_ref:
            raw_output = self._generate_goal_output(request)
        elif "chat" in normalized_ref or "sprint6" in normalized_ref:
            raw_output = self._generate_chat_output(request, citations)
        else:
            raw_output = self._generate_generic_output(request)

        validated_output = SchemaValidator.parse_and_validate(
            raw_output,
            schema_ref=request.output_schema_ref,
            provider="deterministic_fallback",
        )

        retriever_version = request.context.get("retriever_version")

        return LLMResponse(
            output=validated_output,
            model=self.model_name,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            retriever_version=str(retriever_version) if retriever_version else None,
            citations=citations,
            fallback_used=True,
        )

    async def is_quota_available(self) -> bool:
        """Deterministic offline fallback is always available."""
        return True
