"""
backend/app/adapters/llm/__init__.py

Package initialization for FinEx LLM provider adapters, fallback cascades,
and deterministic educational fallback.
Task: S5-MI03 (Multi-Hosted Free-Tier Cascade)
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.adapters.llm.cloudflare_adapter import (
    DEFAULT_CLOUDFLARE_MODEL,
    CloudflareLLMAdapter,
)
from app.adapters.llm.composite_provider import CompositeLLMProvider
from app.adapters.llm.deterministic_adapter import (
    FALLBACK_MODEL_NAME,
    DeterministicFallbackAdapter,
)
from app.adapters.llm.exceptions import (
    LLMProviderError,
    ProhibitedContentError,
    ProviderAuthenticationError,
    ProviderConnectionError,
    ProviderQuotaExceededError,
    ProviderResponseError,
    ProviderTimeoutError,
    SchemaValidationError,
)
from app.adapters.llm.groq_adapter import (
    DEFAULT_GROQ_MODEL,
    GroqLLMAdapter,
)
from app.adapters.llm.hosted_adapter import HostedLLMAdapter
from app.adapters.llm.ollama_adapter import (
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_URL,
    OllamaLLMAdapter,
)
from app.adapters.llm.schema_validator import SchemaValidator
from app.ports.llm_provider import LLMProvider

if TYPE_CHECKING:
    from app.config.settings import Settings


def get_llm_provider(settings: Optional[Settings] = None) -> LLMProvider:
    """Factory creating configured CompositeLLMProvider based on application settings."""
    if settings is None:
        from app.config.settings import get_settings

        settings = get_settings()

    ollama_url = getattr(settings, "ollama_base_url", DEFAULT_OLLAMA_URL)
    ollama_model = getattr(settings, "ollama_model", DEFAULT_OLLAMA_MODEL)
    timeout = getattr(settings, "llm_timeout_seconds", 10.0)

    hosted_type = getattr(settings, "hosted_llm_provider", "gemini")
    gemini_key = getattr(settings, "gemini_api_key", None)
    hosted_model = getattr(settings, "hosted_llm_model", None)

    groq_key = getattr(settings, "groq_api_key", None)
    groq_model = getattr(settings, "groq_model", DEFAULT_GROQ_MODEL)

    cf_account_id = getattr(settings, "cloudflare_account_id", None)
    cf_api_token = getattr(settings, "cloudflare_api_token", None)
    cf_model = getattr(settings, "cloudflare_model", DEFAULT_CLOUDFLARE_MODEL)

    primary = OllamaLLMAdapter(
        base_url=ollama_url,
        model_name=ollama_model,
        timeout_seconds=timeout,
    )

    gemini = (
        HostedLLMAdapter(
            provider_type="gemini",
            api_key=gemini_key or None,
            model_name=hosted_model,
            timeout_seconds=timeout,
        )
        if hosted_type == "gemini"
        else None
    )

    groq = GroqLLMAdapter(
        api_key=groq_key or None,
        model_name=groq_model,
        timeout_seconds=timeout,
    )

    cloudflare = CloudflareLLMAdapter(
        account_id=cf_account_id or None,
        api_token=cf_api_token or None,
        model_name=cf_model,
        timeout_seconds=timeout,
    )

    deterministic = DeterministicFallbackAdapter()

    return CompositeLLMProvider(
        primary_provider=primary,
        gemini_provider=gemini,
        groq_provider=groq,
        cloudflare_provider=cloudflare,
        deterministic_fallback=deterministic,
    )


__all__ = [
    "LLMProvider",
    "OllamaLLMAdapter",
    "HostedLLMAdapter",
    "GroqLLMAdapter",
    "CloudflareLLMAdapter",
    "DeterministicFallbackAdapter",
    "CompositeLLMProvider",
    "SchemaValidator",
    "get_llm_provider",
    "DEFAULT_OLLAMA_URL",
    "DEFAULT_OLLAMA_MODEL",
    "DEFAULT_GROQ_MODEL",
    "DEFAULT_CLOUDFLARE_MODEL",
    "FALLBACK_MODEL_NAME",
    "LLMProviderError",
    "ProviderConnectionError",
    "ProviderTimeoutError",
    "ProviderQuotaExceededError",
    "ProviderAuthenticationError",
    "ProviderResponseError",
    "SchemaValidationError",
    "ProhibitedContentError",
]
