"""
composite_provider.py

Resilient Composite LLM Provider implementing the three-tier fallback cascade:
Primary (Ollama) -> Secondary (Free Hosted) -> Tertiary (Deterministic Fallback).
Guarantees: Provider outage still returns a safe answer, never an unhandled exception.
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import logging
from typing import Any

from app.adapters.llm.deterministic_adapter import DeterministicFallbackAdapter
from app.adapters.llm.exceptions import LLMProviderError
from app.adapters.llm.hosted_adapter import HostedLLMAdapter
from app.adapters.llm.ollama_adapter import OllamaLLMAdapter
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class CompositeLLMProvider(LLMProvider):
    """
    Composite LLM provider implementing the cascade:
    1. Primary: Local Ollama
    2. Secondary: Free Hosted Fallback (Google Gemini API: gemini-3.5-flash-lite)
    3. Tertiary: 100% Offline Deterministic Fallback
    """

    def __init__(
        self,
        primary_provider: LLMProvider | None = None,
        hosted_provider: LLMProvider | None = None,
        deterministic_fallback: LLMProvider | None = None,
        enable_primary: bool = True,
        enable_hosted: bool = True,
        force_fallback: bool = False,
    ) -> None:
        self.primary_provider = primary_provider or OllamaLLMAdapter()
        self.hosted_provider = hosted_provider or HostedLLMAdapter()
        self.deterministic_fallback = deterministic_fallback or DeterministicFallbackAdapter()
        self.enable_primary = enable_primary
        self.enable_hosted = enable_hosted
        self.force_fallback = force_fallback

        self.last_provider_used: str = "none"
        self.last_fallback_reason: str | None = None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Execute generation through the resilient fallback cascade.
        Under no circumstances does a provider outage crash or raise an unhandled error;
        it is guaranteed to return a validated, safe response.
        """
        if self.force_fallback:
            logger.info("force_fallback active; dispatching directly to deterministic fallback")
            self.last_provider_used = "deterministic_fallback"
            return await self.deterministic_fallback.generate(request)

        # Stage 1: Try Primary Provider (Ollama)
        if self.enable_primary and self.primary_provider is not None:
            try:
                response = await self.primary_provider.generate(request)
                self.last_provider_used = "primary_ollama"
                self.last_fallback_reason = None
                return response
            except (LLMProviderError, Exception) as exc:
                self.last_fallback_reason = f"Primary failed: {exc}"
                logger.warning(
                    "Primary LLM provider failed (%s); cascading to hosted fallback...",
                    exc,
                )

        # Stage 2: Try Secondary Provider (Free Hosted Fallback)
        if self.enable_hosted and self.hosted_provider is not None:
            try:
                response = await self.hosted_provider.generate(request)
                self.last_provider_used = "hosted_fallback"
                return response
            except (LLMProviderError, Exception) as exc:
                self.last_fallback_reason = f"Hosted failed: {exc}"
                logger.warning(
                    "Hosted LLM provider failed (%s); cascading to deterministic fallback...",
                    exc,
                )

        # Stage 3: Tertiary Safe Deterministic Fallback (Guaranteed Safe)
        logger.info("Executing safe deterministic fallback for request '%s'", request.prompt_id)
        self.last_provider_used = "deterministic_fallback"
        return await self.deterministic_fallback.generate(request)

    async def is_quota_available(self) -> bool:
        """
        Check overall provider availability.
        Returns True if primary or hosted has quota, or offline fallback is ready.
        """
        if self.enable_primary and self.primary_provider is not None:
            if await self.primary_provider.is_quota_available():
                return True

        if self.enable_hosted and self.hosted_provider is not None:
            if await self.hosted_provider.is_quota_available():
                return True

        return await self.deterministic_fallback.is_quota_available()

    async def health_status(self) -> dict[str, Any]:
        """Diagnostic health report for ops hardening and telemetry."""
        ollama_ok = (
            await self.primary_provider.is_quota_available() if self.primary_provider else False
        )
        hosted_ok = (
            await self.hosted_provider.is_quota_available() if self.hosted_provider else False
        )
        deterministic_ok = await self.deterministic_fallback.is_quota_available()

        return {
            "primary_ollama_available": ollama_ok,
            "hosted_fallback_available": hosted_ok,
            "deterministic_fallback_available": deterministic_ok,
            "last_provider_used": self.last_provider_used,
            "last_fallback_reason": self.last_fallback_reason,
        }
