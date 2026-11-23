"""
hosted_adapter.py

Free-tier hosted LLM provider adapter using Google Gemini API (`gemini-3.8-flash`).
Used as secondary fallback when local Ollama is offline or times out.
Enforces strict client-side data minimization, PII/financial scrubbing,
and header-based API key authentication (x-goog-api-key).
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Literal

import httpx

from app.adapters.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderQuotaExceededError,
    ProviderResponseError,
    ProviderTimeoutError,
    SchemaValidationError,
)
from app.adapters.llm.schema_validator import SchemaValidator
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

# Currently supported and active Google Gemini model with verified free-tier (September 2026 update)
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0

# Privacy Whitelist: Only conceptual, curriculum, and non-PII keys may reach hosted provider
SAFE_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "query",
        "question",
        "message",
        "topic",
        "concept",
        "curriculum_topic",
        "chunks",
        "citations",
        "retriever_version",
    }
)

# Explicit sensitive financial, personal identifiers, and user suitability data
# prohibited from external transmission
SENSITIVE_CONTEXT_KEYS: frozenset[str] = frozenset(
    {
        "user_id",
        "email",
        "phone",
        "pan",
        "aadhaar",
        "ssn",
        "account_id",
        "account_number",
        "iban",
        "balance",
        "available_balance",
        "current_balance",
        "transactions",
        "holdings",
        "portfolio_value",
        "total_wealth",
        "salary",
        "net_worth",
        "password",
        "token",
        "secret",
        "credentials",
        "willingness_score",
        "capacity_score",
        "composite_score",
        "risk_category",
        "goal_name",
    }
)

# Regex patterns for masking sensitive PII / financial numbers in freeform text queries
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PAN_REGEX = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
AADHAAR_REGEX = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")
PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b")
IDENTIFIER_REGEX = re.compile(r"\b\d{10,18}\b")
AMOUNT_REGEX = re.compile(
    r"(?:Rs\.?|INR|₹|\$|USD|EUR|GBP)\s*[\d,]+(?:\.\d+)?|\b[\d,]+(?:\.\d+)?\s*(?:lakhs?|crores?|k|million|billion)\b",
    re.IGNORECASE,
)


class HostedLLMAdapter(LLMProvider):
    """
    Free-tier hosted LLM provider adapter connecting to Google Gemini REST API.
    Enforces strict client-side data minimization and header-based credential authentication.
    """

    def __init__(
        self,
        provider_type: Literal["gemini"] = "gemini",
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if provider_type != "gemini":
            raise ValueError(
                f"Unsupported hosted provider type: '{provider_type}'. "
                "S5-MI03 designates Google Gemini API ('gemini') as the free hosted fallback."
            )
        self.provider_type = provider_type
        self.model_name = model_name or DEFAULT_GEMINI_MODEL
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self._external_client = http_client

    def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=self.connect_timeout_seconds,
        )
        return httpx.AsyncClient(timeout=timeout)

    @classmethod
    def mask_pii_text(cls, text: str) -> str:
        """Mask sensitive email, PAN, Aadhaar, phone, account numbers, and currency."""
        if not text:
            return text
        sanitized = EMAIL_REGEX.sub("[REDACTED_EMAIL]", text)
        sanitized = PAN_REGEX.sub("[REDACTED_PAN]", sanitized)
        sanitized = AADHAAR_REGEX.sub("[REDACTED_AADHAAR]", sanitized)
        sanitized = PHONE_REGEX.sub("[REDACTED_PHONE]", sanitized)
        sanitized = IDENTIFIER_REGEX.sub("[REDACTED_IDENTIFIER]", sanitized)
        sanitized = AMOUNT_REGEX.sub("[REDACTED_AMOUNT]", sanitized)
        return sanitized

    @classmethod
    def sanitize_context_for_external_provider(cls, context: dict[str, Any]) -> dict[str, Any]:
        """
        Enforce strict data minimization:
        - Whitelists only safe conceptual/curriculum keys.
        - Excludes all sensitive financial fields (balances, accounts, PAN, user_id).
        - Masks any PII/amounts in freeform text fields.
        """
        sanitized: dict[str, Any] = {}
        for key, val in context.items():
            if key in SENSITIVE_CONTEXT_KEYS:
                # Omit sensitive keys completely from external transmission
                continue
            if key in SAFE_CONTEXT_KEYS:
                if isinstance(val, str):
                    sanitized[key] = cls.mask_pii_text(val)
                elif isinstance(val, list):
                    clean_list: list[Any] = []
                    for item in val:
                        if isinstance(item, str):
                            clean_list.append(cls.mask_pii_text(item))
                        elif isinstance(item, dict):
                            clean_list.append(cls.sanitize_context_for_external_provider(item))
                        else:
                            clean_list.append(item)
                    sanitized[key] = clean_list
                elif isinstance(val, dict):
                    sanitized[key] = cls.sanitize_context_for_external_provider(val)
                else:
                    sanitized[key] = val
        return sanitized

    def _build_prompts(self, request: LLMRequest) -> tuple[str, str]:
        system_prompt = (
            "You are FinEx educational assistant. Provide clear financial explanations.\n"
            "STRICT COMPLIANCE RULES:\n"
            "1. NEVER give personalized investment advice or recommend stocks to buy/sell.\n"
            "2. NEVER promise guaranteed returns or risk-free profits.\n"
            f"3. Return ONLY valid JSON matching schema '{request.output_schema_ref}'.\n"
            "4. Do not wrap output in extra commentary or text outside the JSON structure."
        )
        # Apply client-side privacy sanitization before serializing context
        sanitized_context = self.sanitize_context_for_external_provider(request.context)
        user_prompt = (
            f"Prompt ID: {request.prompt_id} (Version: {request.prompt_version})\n"
            f"Output Schema: {request.output_schema_ref}\n"
            f"Context: {json.dumps(sanitized_context, default=str)}"
        )
        return system_prompt, user_prompt

    def _sanitize_error_message(self, message: str) -> str:
        """Ensure API keys are never exposed in exceptions or logs."""
        if self.api_key and self.api_key in message:
            return message.replace(self.api_key, "[REDACTED_API_KEY]")
        return message

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

        return list(dict.fromkeys(citations))

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Call Gemini REST endpoint with header auth, privacy scrubbing, and validation."""
        if not self.api_key:
            raise ProviderAuthenticationError(
                "No API key configured for Google Gemini hosted provider (GEMINI_API_KEY is empty)",
                provider=self.provider_type,
            )

        client = self._get_client()
        should_close = self._external_client is None
        system_prompt, user_prompt = self._build_prompts(request)

        try:
            content = await self._call_gemini(client, system_prompt, user_prompt)

            validated_output = SchemaValidator.parse_and_validate(
                content,
                schema_ref=request.output_schema_ref,
                provider=self.provider_type,
            )

            citations = self._extract_citations(request)
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

        except httpx.ConnectError as exc:
            sanitized_msg = self._sanitize_error_message(str(exc))
            logger.warning(
                "Hosted provider connection error (%s): %s",
                self.provider_type,
                sanitized_msg,
            )
            raise ProviderConnectionError(
                f"Hosted provider connection failed: {sanitized_msg}",
                provider=self.provider_type,
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning(
                "Hosted provider timed out (%s) after %ss",
                self.provider_type,
                self.timeout_seconds,
            )
            raise ProviderTimeoutError(
                f"Hosted provider timed out after {self.timeout_seconds}s",
                provider=self.provider_type,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        finally:
            if should_close:
                await client.aclose()

    async def _call_gemini(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """
        Execute request against Google Gemini REST API.
        Transmits API key via 'x-goog-api-key' header; never in URL parameters.
        """
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": f"{system_prompt}\n\n{user_prompt}"}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 400:
            cleaned_text = self._sanitize_error_message(resp.text[:200])
            raise ProviderResponseError(
                f"Gemini malformed request (HTTP 400): {cleaned_text}",
                provider="gemini",
            )
        if resp.status_code == 404:
            raise ProviderResponseError(
                f"Gemini model '{self.model_name}' not found (HTTP 404)",
                provider="gemini",
            )
        if resp.status_code == 429:
            raise ProviderQuotaExceededError(
                "Gemini free-tier rate limit exceeded (HTTP 429)",
                provider="gemini",
            )
        if resp.status_code in (401, 403):
            raise ProviderAuthenticationError(
                f"Gemini API key rejected (HTTP {resp.status_code})",
                provider="gemini",
            )
        if resp.status_code in (500, 502, 503, 504):
            raise ProviderResponseError(
                f"Gemini server error (HTTP {resp.status_code})",
                provider="gemini",
            )
        if resp.status_code != 200:
            cleaned_text = self._sanitize_error_message(resp.text[:200])
            raise ProviderResponseError(
                f"Gemini returned HTTP {resp.status_code}: {cleaned_text}",
                provider="gemini",
            )

        data = resp.json()
        try:
            candidates = data.get("candidates", [])
            if not candidates:
                raise SchemaValidationError(
                    "Gemini response contained no candidates", provider="gemini"
                )
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts or "text" not in parts[0] or not str(parts[0]["text"]).strip():
                raise SchemaValidationError(
                    "Gemini candidate missing text parts or empty response", provider="gemini"
                )
            return parts[0]["text"]
        except (KeyError, IndexError) as exc:
            raise SchemaValidationError(
                f"Unexpected Gemini response structure: {exc}",
                provider="gemini",
            ) from exc

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        code = exc.response.status_code
        if code == 400:
            raise ProviderResponseError(
                "Hosted provider malformed request (HTTP 400)",
                provider=self.provider_type,
            ) from exc
        if code == 404:
            raise ProviderResponseError(
                "Hosted provider endpoint not found (HTTP 404)",
                provider=self.provider_type,
            ) from exc
        if code == 429:
            raise ProviderQuotaExceededError(
                "Hosted provider rate limit exceeded (HTTP 429)",
                provider=self.provider_type,
            ) from exc
        if code in (401, 403):
            raise ProviderAuthenticationError(
                f"Hosted provider authentication failed (HTTP {code})",
                provider=self.provider_type,
            ) from exc
        if code in (500, 502, 503, 504):
            raise ProviderResponseError(
                f"Hosted provider server failure (HTTP {code})",
                provider=self.provider_type,
            ) from exc
        cleaned_text = self._sanitize_error_message(exc.response.text[:200])
        raise ProviderResponseError(
            f"Hosted provider error HTTP {code}: {cleaned_text}",
            provider=self.provider_type,
        ) from exc

    async def is_quota_available(self) -> bool:
        """Return True if an API key is configured for Google Gemini."""
        return bool(self.api_key and len(self.api_key.strip()) >= 8)
