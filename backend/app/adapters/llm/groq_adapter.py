"""
groq_adapter.py

Secondary hosted LLM provider adapter using Groq API (`openai/gpt-oss-120b`).
Tier 2 of 3 in the multi-hosted cascade:
Ollama -> Gemini -> Groq -> Cloudflare -> Deterministic.
Enforces identical client-side data minimization, PII/financial scrubbing,
and header-based API key authentication (Bearer token).
Task: S5-MI03 (Multi-Hosted Free-Tier Cascade)
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import json
import logging
import os

import httpx

from app.adapters.llm.exceptions import (
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderQuotaExceededError,
    ProviderResponseError,
    ProviderTimeoutError,
    SchemaValidationError,
)
from app.adapters.llm.hosted_adapter import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    HostedLLMAdapter,
)
from app.adapters.llm.schema_validator import SchemaValidator
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

# Verified free-tier model on Groq LPU inference (OpenAI's open-weight MoE reasoning model)
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"
DEFAULT_GROQ_API_URL = "https://api.groq.com/openai/v1"


class GroqLLMAdapter(LLMProvider):
    """
    Hosted LLM provider adapter connecting to Groq REST API.
    Uses OpenAI-compatible endpoint with Bearer auth and client-side privacy scrubbing.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str = DEFAULT_GROQ_API_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.provider_type = "groq"
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        self.model_name = model_name or DEFAULT_GROQ_MODEL
        self.base_url = base_url.rstrip("/")
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

    def _sanitize_error_message(self, message: str) -> str:
        """Ensure API key is never exposed in error messages or logs."""
        if self.api_key and self.api_key in message:
            return message.replace(self.api_key, "[REDACTED_GROQ_KEY]")
        return message

    def _build_prompts(self, request: LLMRequest) -> tuple[str, str]:
        system_prompt = (
            "You are FinEx educational assistant. Provide clear financial explanations.\n"
            "STRICT COMPLIANCE RULES:\n"
            "1. NEVER give personalized investment advice or recommend stocks to buy/sell.\n"
            "2. NEVER promise guaranteed returns or risk-free profits.\n"
            f"3. Return ONLY valid JSON matching schema '{request.output_schema_ref}'.\n"
            "4. Do not wrap output in extra commentary or text outside the JSON structure."
        )
        # Apply identical client-side privacy sanitization
        sanitized_context = HostedLLMAdapter.sanitize_context_for_external_provider(request.context)
        user_prompt = (
            f"Prompt ID: {request.prompt_id} (Version: {request.prompt_version})\n"
            f"Output Schema: {request.output_schema_ref}\n"
            f"Context: {json.dumps(sanitized_context, default=str)}"
        )
        return system_prompt, user_prompt

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Call Groq /chat/completions with header auth, privacy scrubbing, and validation."""
        if not self.api_key:
            raise ProviderAuthenticationError(
                "No API key configured for Groq hosted provider (GROQ_API_KEY is empty)",
                provider=self.provider_type,
            )

        # Refuse personal risk profile and suitability data from leaving the platform
        if (
            "risk" in request.output_schema_ref.lower()
            or "risk" in request.prompt_id.lower()
            or any(
                k in request.context
                for k in ("willingness_score", "capacity_score", "composite_score")
            )
        ):
            raise ProviderResponseError(
                "Personal suitability and risk profile data cannot be transmitted to external "
                "hosted LLM under FinEx privacy policy; cascading to deterministic fallback",
                provider=self.provider_type,
            )

        client = self._get_client()
        should_close = self._external_client is None
        system_prompt, user_prompt = self._build_prompts(request)

        try:
            content = await self._call_groq(client, system_prompt, user_prompt)

            validated_output = SchemaValidator.parse_and_validate(
                content,
                schema_ref=request.output_schema_ref,
                provider=self.provider_type,
            )

            citations = HostedLLMAdapter(api_key="placeholder")._extract_citations(request)
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
            logger.warning("Groq connection error: %s", sanitized_msg)
            raise ProviderConnectionError(
                f"Groq connection failed: {sanitized_msg}",
                provider=self.provider_type,
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Groq request timed out after %ss", self.timeout_seconds)
            raise ProviderTimeoutError(
                f"Groq request timed out after {self.timeout_seconds}s",
                provider=self.provider_type,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        finally:
            if should_close:
                await client.aclose()

    async def _call_groq(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Execute request against Groq OpenAI-compatible chat completions endpoint."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 400:
            cleaned_text = self._sanitize_error_message(resp.text[:200])
            raise ProviderResponseError(
                f"Groq malformed request (HTTP 400): {cleaned_text}",
                provider="groq",
            )
        if resp.status_code == 404:
            raise ProviderResponseError(
                f"Groq model '{self.model_name}' not found (HTTP 404)",
                provider="groq",
            )
        if resp.status_code == 429:
            raise ProviderQuotaExceededError(
                "Groq free-tier rate limit exceeded (HTTP 429)",
                provider="groq",
            )
        if resp.status_code in (401, 403):
            raise ProviderAuthenticationError(
                f"Groq API key rejected (HTTP {resp.status_code})",
                provider="groq",
            )
        if resp.status_code in (500, 502, 503, 504):
            raise ProviderResponseError(
                f"Groq server error (HTTP {resp.status_code})",
                provider="groq",
            )
        if resp.status_code != 200:
            cleaned_text = self._sanitize_error_message(resp.text[:200])
            raise ProviderResponseError(
                f"Groq returned HTTP {resp.status_code}: {cleaned_text}",
                provider="groq",
            )

        data = resp.json()
        try:
            choices = data.get("choices", [])
            if not choices:
                raise SchemaValidationError("Groq response contained no choices", provider="groq")
            content = choices[0].get("message", {}).get("content", "")
            if not content or not str(content).strip():
                raise SchemaValidationError(
                    "Groq response contained empty message content", provider="groq"
                )
            return content
        except (KeyError, IndexError) as exc:
            raise SchemaValidationError(
                f"Unexpected Groq response structure: {exc}",
                provider="groq",
            ) from exc

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        code = exc.response.status_code
        if code == 400:
            raise ProviderResponseError(
                "Groq malformed request (HTTP 400)",
                provider=self.provider_type,
            ) from exc
        if code == 404:
            raise ProviderResponseError(
                "Groq endpoint not found (HTTP 404)",
                provider=self.provider_type,
            ) from exc
        if code == 429:
            raise ProviderQuotaExceededError(
                "Groq rate limit exceeded (HTTP 429)",
                provider=self.provider_type,
            ) from exc
        if code in (401, 403):
            raise ProviderAuthenticationError(
                f"Groq authentication failed (HTTP {code})",
                provider=self.provider_type,
            ) from exc
        if code in (500, 502, 503, 504):
            raise ProviderResponseError(
                f"Groq server failure (HTTP {code})",
                provider=self.provider_type,
            ) from exc
        cleaned_text = self._sanitize_error_message(exc.response.text[:200])
        raise ProviderResponseError(
            f"Groq error HTTP {code}: {cleaned_text}",
            provider=self.provider_type,
        ) from exc

    async def is_quota_available(self) -> bool:
        """Return True if a valid API key is configured for Groq."""
        return bool(self.api_key and len(self.api_key.strip()) >= 8)
