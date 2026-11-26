"""
exceptions.py

Custom exception hierarchy for FinEx LLM provider adapters and fallback cascades.
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations


class LLMProviderError(Exception):
    """Base exception for all LLM provider adapter errors."""

    def __init__(self, message: str, provider: str = "unknown") -> None:
        super().__init__(message)
        self.message = message
        self.provider = provider


class ProviderConnectionError(LLMProviderError):
    """Raised when an external LLM endpoint cannot be reached."""


class ProviderTimeoutError(LLMProviderError):
    """Raised when an LLM provider request times out."""


class ProviderQuotaExceededError(LLMProviderError):
    """Raised when rate limits or quotas are exceeded (e.g. HTTP 429)."""


class ProviderAuthenticationError(LLMProviderError):
    """Raised when API credentials are missing, rejected, or expired (e.g. HTTP 401/403)."""


class ProviderResponseError(LLMProviderError):
    """Raised when the provider returns an unexpected HTTP error (e.g. 500, 502, 503)."""


class SchemaValidationError(LLMProviderError):
    """Raised when the LLM output fails validation against the requested JSON schema."""


class ProhibitedContentError(LLMProviderError):
    """Raised when the LLM response contains prohibited financial advice or return guarantees."""
