"""
composite_provider.py

Resilient Composite LLM Provider implementing the five-tier fallback cascade:
1. Primary: Local Ollama (llama3.2:1b)
2. Secondary: Free Hosted Fallback #1 - Google Gemini (gemini-3.8-flash)
3. Tertiary: Free Hosted Fallback #2 - Groq (openai/gpt-oss-120b)
4. Quaternary: Free Hosted Fallback #3 - Cloudflare Workers AI (@cf/google/gemma-3-12b-it)
5. Quinary: 100% Offline Deterministic Fallback (Guaranteed Safe, Zero External Network Calls)

Guarantees: Provider outage, rate limits (HTTP 429), timeouts, auth errors, or schema
failures still return a safe, validated answer, never an unhandled exception.
Task: S5-MI03 (Multi-Hosted Free-Tier Cascade)
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.adapters.llm.cloudflare_adapter import CloudflareLLMAdapter
from app.adapters.llm.deterministic_adapter import DeterministicFallbackAdapter
from app.adapters.llm.exceptions import LLMProviderError
from app.adapters.llm.groq_adapter import GroqLLMAdapter
from app.adapters.llm.hosted_adapter import HostedLLMAdapter
from app.adapters.llm.ollama_adapter import OllamaLLMAdapter
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class CompositeLLMProvider(LLMProvider):
    """
    Composite LLM provider implementing the 5-tier resilient cascade:
    1. Primary: Local Ollama
    2. Hosted Tier 1: Google Gemini API (gemini-3.8-flash)
    3. Hosted Tier 2: Groq REST API (openai/gpt-oss-120b)
    4. Hosted Tier 3: Cloudflare Workers AI (@cf/google/gemma-3-12b-it)
    5. Final Fallback: 100% Offline Deterministic Educational Fallback
    """

    def __init__(
        self,
        primary_provider: LLMProvider | None = None,
        gemini_provider: LLMProvider | None = None,
        groq_provider: LLMProvider | None = None,
        cloudflare_provider: LLMProvider | None = None,
        deterministic_fallback: LLMProvider | None = None,
        hosted_provider: LLMProvider | None = None,  # Backward compatibility alias
        enable_primary: bool = True,
        enable_gemini: bool = True,
        enable_groq: bool = True,
        enable_cloudflare: bool = True,
        enable_hosted: bool = True,  # Backward compatibility alias
        force_fallback: bool = False,
    ) -> None:
        self.primary_provider = primary_provider or OllamaLLMAdapter()

        # Resolve Gemini / legacy hosted provider
        self.gemini_provider = gemini_provider or hosted_provider or HostedLLMAdapter()
        self.hosted_provider = self.gemini_provider

        # If explicit custom test mocks were passed for 3-tier cascade, preserve that topology
        self.groq_provider: LLMProvider | None
        if groq_provider is not None:
            self.groq_provider = groq_provider
        elif primary_provider is None and hosted_provider is None and gemini_provider is None:
            self.groq_provider = GroqLLMAdapter()
        else:
            self.groq_provider = None
            logger.warning(
                "Groq provider omitted from cascade because custom primary/hosted providers "
                "were passed without an explicit groq_provider (backward-compatible 3-tier mode)."
            )

        self.cloudflare_provider: LLMProvider | None
        if cloudflare_provider is not None:
            self.cloudflare_provider = cloudflare_provider
        elif primary_provider is None and hosted_provider is None and gemini_provider is None:
            self.cloudflare_provider = CloudflareLLMAdapter()
        else:
            self.cloudflare_provider = None
            logger.warning(
                "Cloudflare provider omitted from cascade because custom primary/hosted providers "
                "were passed without an explicit cloudflare_provider "
                "(backward-compatible 3-tier mode)."
            )

        self.deterministic_fallback = deterministic_fallback or DeterministicFallbackAdapter()

        self.enable_primary = enable_primary
        self.enable_gemini = enable_gemini and enable_hosted
        self.enable_hosted = self.enable_gemini
        self.enable_groq = enable_groq
        self.enable_cloudflare = enable_cloudflare
        self.force_fallback = force_fallback

        self.last_provider_used: str = "none"
        self.last_provider_name: str = "none"
        self.last_fallback_reason: str | None = None

    @staticmethod
    def _sanitize_fallback_reason(exc: Exception | str) -> str:
        """
        Sanitize error messages to ensure API tokens, authorization headers,
        PII, and raw prompt/response payloads never leak into logs or telemetry.
        """
        msg = str(exc)
        # Redact Authorization header / Bearer tokens
        msg = re.sub(r"(?i)bearer\s+[A-Za-z0-9_\-\.]+", "[REDACTED_BEARER_TOKEN]", msg)
        msg = re.sub(r"(?i)authorization:\s*[^\s]+", "Authorization: [REDACTED]", msg)
        # Redact Google Gemini API keys
        msg = re.sub(r"AIza[0-9A-Za-z_\-]{20,}", "[REDACTED_GEMINI_KEY]", msg)
        # Redact Groq API keys
        msg = re.sub(r"gsk_[0-9A-Za-z_]{20,}", "[REDACTED_GROQ_KEY]", msg)
        # Redact emails and phone numbers
        msg = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "[REDACTED_EMAIL]", msg)
        msg = re.sub(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
            "[REDACTED_PHONE]",
            msg,
        )
        # Prevent prompt/response body echo by truncating excessively long error strings
        if len(msg) > 200:
            msg = msg[:197] + "..."
        return msg

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Execute generation through the 5-stage resilient cascade.
        Under no circumstances does a provider outage crash or raise an unhandled error;
        it is guaranteed to return a validated, safe response.
        """
        if self.force_fallback:
            logger.info("force_fallback active; dispatching directly to deterministic fallback")
            self.last_provider_used = "deterministic_fallback"
            self.last_provider_name = "deterministic"
            return await self.deterministic_fallback.generate(request)

        # Stage 1: Try Primary Provider (Ollama)
        if self.enable_primary and self.primary_provider is not None:
            try:
                response = await self.primary_provider.generate(request)
                self.last_provider_used = "primary_ollama"
                self.last_provider_name = "ollama"
                self.last_fallback_reason = None
                return response
            except LLMProviderError as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = f"Primary Ollama failed: {clean_msg}"
                logger.warning(
                    "Primary LLM provider failed (%s); cascading to Gemini hosted fallback...",
                    clean_msg,
                )
            except Exception as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = (
                    f"Primary Ollama unexpected error: {type(exc).__name__}: {clean_msg}"
                )
                logger.exception(
                    "Unexpected error in primary Ollama provider (%s); "
                    "cascading to Gemini hosted fallback...",
                    clean_msg,
                )

        # Stage 2: Try Hosted Tier 1 (Google Gemini: gemini-3.8-flash)
        if self.enable_gemini and self.gemini_provider is not None:
            try:
                response = await self.gemini_provider.generate(request)
                self.last_provider_used = "hosted_fallback"
                self.last_provider_name = "gemini"
                return response
            except LLMProviderError as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = f"Gemini hosted failed: {clean_msg}"
                logger.warning(
                    "Gemini hosted provider failed (%s); cascading to Groq hosted fallback...",
                    clean_msg,
                )
            except Exception as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = (
                    f"Gemini hosted unexpected error: {type(exc).__name__}: {clean_msg}"
                )
                logger.exception(
                    "Unexpected error in Gemini hosted provider (%s); "
                    "cascading to Groq hosted fallback...",
                    clean_msg,
                )

        # Stage 3: Try Hosted Tier 2 (Groq: openai/gpt-oss-120b)
        if self.enable_groq and self.groq_provider is not None:
            try:
                response = await self.groq_provider.generate(request)
                self.last_provider_used = "groq_hosted"
                self.last_provider_name = "groq"
                return response
            except LLMProviderError as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = f"Groq hosted failed: {clean_msg}"
                logger.warning(
                    "Groq hosted provider failed (%s); "
                    "cascading to Cloudflare Workers AI fallback...",
                    clean_msg,
                )
            except Exception as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = (
                    f"Groq hosted unexpected error: {type(exc).__name__}: {clean_msg}"
                )
                logger.exception(
                    "Unexpected error in Groq hosted provider (%s); "
                    "cascading to Cloudflare Workers AI fallback...",
                    clean_msg,
                )

        # Stage 4: Try Hosted Tier 3 (Cloudflare Workers AI: @cf/google/gemma-3-12b-it)
        if self.enable_cloudflare and self.cloudflare_provider is not None:
            try:
                response = await self.cloudflare_provider.generate(request)
                self.last_provider_used = "cloudflare_hosted"
                self.last_provider_name = "cloudflare"
                return response
            except LLMProviderError as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = f"Cloudflare hosted failed: {clean_msg}"
                logger.warning(
                    "Cloudflare hosted provider failed (%s); "
                    "cascading to safe deterministic fallback...",
                    clean_msg,
                )
            except Exception as exc:
                clean_msg = self._sanitize_fallback_reason(exc)
                self.last_fallback_reason = (
                    f"Cloudflare hosted unexpected error: {type(exc).__name__}: {clean_msg}"
                )
                logger.exception(
                    "Unexpected error in Cloudflare hosted provider (%s); "
                    "cascading to safe deterministic fallback...",
                    clean_msg,
                )

        # Stage 5: Final Safe Deterministic Fallback (Guaranteed Safe, Offline)
        logger.info("Executing safe deterministic fallback for request '%s'", request.prompt_id)
        self.last_provider_used = "deterministic_fallback"
        self.last_provider_name = "deterministic"
        return await self.deterministic_fallback.generate(request)

    async def is_quota_available(self) -> bool:
        """
        Check overall provider availability across all cascade stages.
        Returns True if primary or any hosted tier has quota, or offline fallback is ready.
        """
        if self.enable_primary and self.primary_provider is not None:
            if await self.primary_provider.is_quota_available():
                return True

        if self.enable_gemini and self.gemini_provider is not None:
            if await self.gemini_provider.is_quota_available():
                return True

        if self.enable_groq and self.groq_provider is not None:
            if await self.groq_provider.is_quota_available():
                return True

        if self.enable_cloudflare and self.cloudflare_provider is not None:
            if await self.cloudflare_provider.is_quota_available():
                return True

        return await self.deterministic_fallback.is_quota_available()

    async def health_status(self) -> dict[str, Any]:
        """Diagnostic health report for ops hardening and telemetry across all tiers."""
        ollama_ok = (
            await self.primary_provider.is_quota_available() if self.primary_provider else False
        )
        gemini_ok = (
            await self.gemini_provider.is_quota_available() if self.gemini_provider else False
        )
        groq_ok = await self.groq_provider.is_quota_available() if self.groq_provider else False
        cloudflare_ok = (
            await self.cloudflare_provider.is_quota_available()
            if self.cloudflare_provider
            else False
        )
        deterministic_ok = await self.deterministic_fallback.is_quota_available()

        return {
            "primary_ollama_available": ollama_ok,
            "hosted_fallback_available": gemini_ok,
            "gemini_available": gemini_ok,
            "groq_available": groq_ok,
            "cloudflare_available": cloudflare_ok,
            "deterministic_fallback_available": deterministic_ok,
            "last_provider_used": self.last_provider_used,
            "last_provider_name": self.last_provider_name,
            "last_fallback_reason": self.last_fallback_reason,
        }
