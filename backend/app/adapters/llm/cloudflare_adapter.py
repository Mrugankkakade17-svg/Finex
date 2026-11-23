"""
cloudflare_adapter.py

Tertiary hosted LLM provider adapter using Cloudflare Workers AI (`@cf/google/gemma-3-12b-it`).
Tier 3 of 3 in the multi-hosted cascade:
Ollama -> Gemini -> Groq -> Cloudflare -> Deterministic.
Enforces identical client-side data minimization, PII/financial scrubbing,
and header-based API token authentication (Bearer token).
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

# Verified free-tier model on Cloudflare Workers AI (10k Neurons/day free allocation)
DEFAULT_CLOUDFLARE_MODEL = "@cf/google/gemma-3-12b-it"
DEFAULT_CLOUDFLARE_BASE_URL = "https://api.cloudflare.com/client/v4"


class CloudflareLLMAdapter(LLMProvider):
    """
    Hosted LLM provider adapter connecting to Cloudflare Workers AI REST API.
    Runs @cf/google/gemma-3-12b-it with Bearer auth and client-side privacy scrubbing.
    """

    def __init__(
        self,
        account_id: str | None = None,
        api_token: str | None = None,
        model_name: str | None = None,
        base_url: str = DEFAULT_CLOUDFLARE_BASE_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.provider_type = "cloudflare"
        self.account_id = account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
        self.api_token = api_token or os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
        self.model_name = model_name or DEFAULT_CLOUDFLARE_MODEL
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
        """Ensure API token and account ID are never exposed in error messages or logs."""
        if self.api_token and self.api_token in message:
            message = message.replace(self.api_token, "[REDACTED_CLOUDFLARE_TOKEN]")
        if self.account_id and self.account_id in message:
            message = message.replace(self.account_id, "[REDACTED_CLOUDFLARE_ACCOUNT]")
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
        """Call Cloudflare Workers AI with header auth, privacy scrubbing, and validation."""
        if not self.api_token or not self.account_id:
            raise ProviderAuthenticationError(
                "Cloudflare API credentials not configured "
                "(CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN required)",
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
            content = await self._call_cloudflare(client, system_prompt, user_prompt)

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
            logger.warning("Cloudflare connection error: %s", sanitized_msg)
            raise ProviderConnectionError(
                f"Cloudflare connection failed: {sanitized_msg}",
                provider=self.provider_type,
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Cloudflare request timed out after %ss", self.timeout_seconds)
            raise ProviderTimeoutError(
                f"Cloudflare request timed out after {self.timeout_seconds}s",
                provider=self.provider_type,
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._handle_http_status_error(exc)
            raise
        finally:
            if should_close:
                await client.aclose()

    async def _call_cloudflare(
        self,
        client: httpx.AsyncClient,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        """Execute request against Cloudflare Workers AI REST endpoint."""
        url = f"{self.base_url}/accounts/{self.account_id}/ai/run/{self.model_name}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        }

        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 400:
            cleaned_text = self._sanitize_error_message(resp.text[:200])
            raise ProviderResponseError(
                f"Cloudflare malformed request (HTTP 400): {cleaned_text}",
                provider="cloudflare",
            )
        if resp.status_code == 404:
            raise ProviderResponseError(
                f"Cloudflare model '{self.model_name}' or account not found (HTTP 404)",
                provider="cloudflare",
            )
        if resp.status_code == 429:
            raise ProviderQuotaExceededError(
                "Cloudflare Workers AI daily neuron limit or rate limit exceeded (HTTP 429)",
                provider="cloudflare",
            )
        if resp.status_code in (401, 403):
            raise ProviderAuthenticationError(
                f"Cloudflare API token rejected (HTTP {resp.status_code})",
                provider="cloudflare",
            )
        if resp.status_code in (500, 502, 503, 504):
            raise ProviderResponseError(
                f"Cloudflare server error (HTTP {resp.status_code})",
                provider="cloudflare",
            )
        if resp.status_code != 200:
            cleaned_text = self._sanitize_error_message(resp.text[:200])
            raise ProviderResponseError(
                f"Cloudflare returned HTTP {resp.status_code}: {cleaned_text}",
                provider="cloudflare",
            )

        data = resp.json()
        # Cloudflare response format check
        if data.get("success") is False:
            errors = data.get("errors", [])
            err_msg = "; ".join(str(e.get("message", e)) for e in errors) or "Unknown error"
            err_lower = err_msg.lower()
            if "quota" in err_lower or "limit" in err_lower or "neuron" in err_lower:
                raise ProviderQuotaExceededError(
                    f"Cloudflare quota exceeded: {err_msg}",
                    provider="cloudflare",
                )
            raise ProviderResponseError(
                f"Cloudflare API error: {err_msg}",
                provider="cloudflare",
            )

        content: str = ""
        result = data.get("result")
        if isinstance(result, dict):
            content = result.get("response") or result.get("output") or result.get("text") or ""
        elif isinstance(result, str):
            content = result
        elif "choices" in data:
            choices = data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")

        if not content or not str(content).strip():
            raise SchemaValidationError(
                "Cloudflare response contained empty content", provider="cloudflare"
            )
        return str(content)

    def _handle_http_status_error(self, exc: httpx.HTTPStatusError) -> None:
        code = exc.response.status_code
        if code == 400:
            raise ProviderResponseError(
                "Cloudflare malformed request (HTTP 400)",
                provider=self.provider_type,
            ) from exc
        if code == 404:
            raise ProviderResponseError(
                "Cloudflare endpoint not found (HTTP 404)",
                provider=self.provider_type,
            ) from exc
        if code == 429:
            raise ProviderQuotaExceededError(
                "Cloudflare rate limit exceeded (HTTP 429)",
                provider=self.provider_type,
            ) from exc
        if code in (401, 403):
            raise ProviderAuthenticationError(
                f"Cloudflare authentication failed (HTTP {code})",
                provider=self.provider_type,
            ) from exc
        if code in (500, 502, 503, 504):
            raise ProviderResponseError(
                f"Cloudflare server failure (HTTP {code})",
                provider=self.provider_type,
            ) from exc
        cleaned_text = self._sanitize_error_message(exc.response.text[:200])
        raise ProviderResponseError(
            f"Cloudflare error HTTP {code}: {cleaned_text}",
            provider=self.provider_type,
        ) from exc

    async def is_quota_available(self) -> bool:
        """Return True if account ID and API token are configured for Cloudflare."""
        return bool(self.account_id and self.api_token and len(self.api_token.strip()) >= 8)
