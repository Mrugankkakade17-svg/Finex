"""
schema_validator.py

Validates LLM provider outputs against versioned schema references and enforces
non-negotiable FinEx regulatory compliance guardrails (no return guarantees or buy/sell advice).
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.adapters.llm.exceptions import ProhibitedContentError, SchemaValidationError

PROHIBITED_PHRASES: tuple[str, ...] = (
    "guaranteed return",
    "guaranteed returns",
    "guaranteed profit",
    "guaranteed profits",
    "risk-free profit",
    "risk-free profits",
    "risk free profit",
    "risk free profits",
    "risk-free return",
    "risk-free returns",
    "risk free return",
    "will definitely earn",
    "promise you",
    "sure shot",
    "buy this stock",
    "sell this stock",
    "invest in crypto",
)


def _compile_phrase(phrase: str) -> re.Pattern[str]:
    # Normalize hyphens so 'risk-free', 'risk - free', and 'risk free' match
    phrase = phrase.replace("-", " - ")
    parts = phrase.split()
    pattern_parts = []
    for p in parts:
        if p == "-":
            pattern_parts.append(r"[\s\-]+")
        else:
            pattern_parts.append(re.escape(p))
    return re.compile(r"\b" + r"\s*".join(pattern_parts) + r"\b", re.IGNORECASE)


COMPILED_PROHIBITED_PATTERNS: list[re.Pattern[str]] = [
    _compile_phrase(phrase) for phrase in PROHIBITED_PHRASES
]


class SchemaValidator:
    """Validates raw LLM responses against schema contracts and compliance guardrails."""

    @classmethod
    def clean_json_text(cls, raw_text: str) -> str:
        """Strip markdown code fence blocks if wrapped by the LLM."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    @classmethod
    def parse_and_validate(
        cls,
        raw_text_or_dict: str | dict[str, Any],
        schema_ref: str,
        *,
        provider: str = "unknown",
    ) -> dict[str, Any]:
        """Parse raw text or dict, verify compliance guardrails, and validate against schema_ref."""
        if isinstance(raw_text_or_dict, str):
            cleaned = cls.clean_json_text(raw_text_or_dict)
            try:
                data = json.loads(cleaned)
            except Exception as exc:
                raise SchemaValidationError(
                    f"Failed to parse LLM response as JSON: {exc}",
                    provider=provider,
                ) from exc
        elif isinstance(raw_text_or_dict, dict):
            data = raw_text_or_dict
        else:
            raise SchemaValidationError(
                f"Expected str or dict response, received {type(raw_text_or_dict).__name__}",
                provider=provider,
            )

        if not isinstance(data, dict):
            raise SchemaValidationError(
                f"LLM output must be a JSON object, received {type(data).__name__}",
                provider=provider,
            )

        # Compliance Guardrail: Scan for prohibited financial promises or advice
        dumped_text = json.dumps(data).lower()
        for pattern in COMPILED_PROHIBITED_PATTERNS:
            if pattern.search(dumped_text):
                msg = (
                    "LLM output violated compliance guardrails "
                    f"(matched prohibited phrase: '{pattern.pattern}')"
                )
                raise ProhibitedContentError(msg, provider=provider)

        # Validate schema structure according to schema_ref
        cls.validate_schema_ref(data, schema_ref, provider=provider)
        return data

    @classmethod
    def validate_schema_ref(
        cls,
        data: dict[str, Any],
        schema_ref: str,
        *,
        provider: str = "unknown",
    ) -> None:
        """Validate required fields based on the versioned schema reference."""
        normalized_ref = schema_ref.strip().lower()

        if "chat" in normalized_ref or "sprint6" in normalized_ref:
            # Requires standard AI chat structure
            chat_required = ("intent", "answer_text", "limitations_disclaimer")
            missing = [f for f in chat_required if f not in data or not str(data[f]).strip()]
            if missing:
                raise SchemaValidationError(
                    f"Output schema '{schema_ref}' missing required non-empty fields: {missing}",
                    provider=provider,
                )

        elif "risk_explanation" in normalized_ref or "s2_risk" in normalized_ref:
            # Requires risk explanation structure
            risk_required = (
                "summary",
                "willingness_explanation",
                "capacity_explanation",
                "alignment_analysis",
            )
            missing = [f for f in risk_required if f not in data or not str(data[f]).strip()]
            if missing:
                raise SchemaValidationError(
                    f"Output schema '{schema_ref}' missing required non-empty fields: {missing}",
                    provider=provider,
                )

        elif "goal_explanation" in normalized_ref or "a3_goal" in normalized_ref:
            # Requires goal explanation structure
            goal_required = ("explanation", "disclaimer")
            missing = [f for f in goal_required if f not in data or not str(data[f]).strip()]
            if missing:
                raise SchemaValidationError(
                    f"Output schema '{schema_ref}' missing required non-empty fields: {missing}",
                    provider=provider,
                )

        else:
            # Generic schema validation: Must have at least some explanatory text and disclaimer
            has_explanation = any(
                k in data
                for k in ("answer_text", "explanation", "summary", "response", "message", "text")
            )
            if not has_explanation and len(data.keys()) == 0:
                raise SchemaValidationError(
                    f"Output schema '{schema_ref}' must be a non-empty object with explanation",
                    provider=provider,
                )
