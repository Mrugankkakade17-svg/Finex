"""
hosted_adapter.py

Free-tier hosted LLM provider adapter (Google Gemini API, Groq).
Used as secondary fallback when local Ollama is offline or times out.
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Literal

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

DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0


class HostedLLMAdapter(LLMProvider):
    """Free-tier hosted LLM provider adapter supporting Google Gemini and Groq."""

    def __init__(
        self,
        provider_type: Literal["gemini", "groq"] = "gemini",
        api_key: str | None = None,
        model_name: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.provider_type = provider_type
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self._external_client = http_client

        if self.provider_type == "gemini":
            self.model_name = model_name or DEFAULT_GEMINI_MODEL
            self.api_key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
        elif self.provider_type == "groq":
            self.model_name = model_name or DEFAULT_GROQ_MODEL
            self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        else:
            raise ValueError(f"Unsupported hosted provider type: '{provider_type}'")

    def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        timeout = httpx.Timeout(
            self.timeout_seconds,
            connect=self.connect_timeout_seconds,
        )
        return httpx.AsyncClient(timeout=timeout)

    def _build_prompts(self, request: LLMRequest) -> tuple[str, str]:
        system_prompt = (
            "You are FinEx educational assistant. Provide clear financial explanations.\n"
            "STRICT COMPLIANCE RULES:\n"
            "1. NEVER give personalized investment advice or recommend stocks to buy/sell.\n"
            "2. NEVER promise guaranteed returns or risk-free profits.\n"
            f"3. Return ONLY valid JSON matching schema '{request.output_schema_ref}'.\n"
            "4. Do not wrap output in extra commentary or text outside the JSON structure."
        )
        user_prompt = (
            f"Prompt ID: {request.prompt_id} (Version: {request.prompt_version})\n"
            f"Output Schema: {request.output_schema_ref}\n"
            f"Context: {json.dumps(request.context, default=str)}"
        )
        return system_prompt, user_prompt

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
        """Call hosted provider REST endpoint with error handling and fallback metadata."""
        if not self.api_key:
            raise ProviderAuthenticationError(
                f"No API key configured for hosted provider '{self.provider_type}'",
                provider=self.provider_type,
            )

        client = self._get_client()
        should_close = self._external_client is None
        system_prompt, user_prompt = self._build_prompts(request)

        try:
            if self.provider_type == "gemini":
                content = await self._call_gemini(client, system_prompt, user_prompt)
            else:
                content = await self._call_groq(client, system_prompt, user_prompt)

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
            logger.warning("Hosted provider connection error (%s): %s", self.provider_type, exc)
            raise ProviderConnectionError(
                f"Hosted provider connection failed: {exc}",
                provider=self.provider_type,
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Hosted provider timed out (%s): %s", self.provider_type, exc)
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
        """Execute request against Google Gemini REST API."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )
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

        resp = await client.post(url, json=payload)
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
        if resp.status_code != 200:
            raise ProviderResponseError(
                f"Gemini returned HTTP {resp.status_code}: {resp.text[:200]}",
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
            if not parts or "text" not in parts[0]:
                raise SchemaValidationError(
                    "Gemini candidate missing text parts", provider="gemini"
                )
            return parts[0]["text"]
        except (KeyError, IndexError) as exc:
            raise SchemaValidationError(
                f"Unexpected Gemini response structure: {exc}",
                provider="gemini",
            ) from exc

    async def _call_groq(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Execute request against Groq REST API (OpenAI-compatible)."""
        url = "https://api.groq.com/openai/v1/chat/completions"
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
        if resp.status_code != 200:
            raise ProviderResponseError(
                f"Groq returned HTTP {resp.status_code}: {resp.text[:200]}",
                provider="groq",
            )

        data = resp.json()
        try:
            choices = data.get("choices", [])
            if not choices:
                raise SchemaValidationError("Groq response contained no choices", provider="groq")
            content = choices[0].get("message", {}).get("content", "")
            return content
        except (KeyError, IndexError) as exc:
            raise SchemaValidationError(
                f"Unexpected Groq response structure: {exc}",
                provider="groq",
            ) from exc

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        code = exc.response.status_code
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
        raise ProviderResponseError(
            f"Hosted provider error HTTP {code}: {exc.response.text[:200]}",
            provider=self.provider_type,
        ) from exc

    async def is_quota_available(self) -> bool:
        """Return True if an API key is configured for the free hosted tier."""
        return bool(self.api_key and len(self.api_key.strip()) >= 8)
