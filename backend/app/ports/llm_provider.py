"""
llm_provider.py

WHAT THIS FILE IS FOR
----------------------
Today, LLM calls go through a free/quota-limited endpoint (Databricks
model serving / foundation model access). Later this may move to a paid
endpoint.

This interface defines the contract that application services use to
communicate with an LLM provider instead of calling a vendor SDK
directly.

THE ONE RULE THAT NEVER BENDS :
The LLM explains and interprets. It NEVER calculates an authoritative
financial number, and it NEVER triggers an action directly. Every
response must validate against a versioned JSON schema before it reaches
a client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LLMRequest:
    prompt_id: str  # e.g. "a3_goal_explanation"
    prompt_version: str  # e.g. "v1"
    context: dict[str, Any]  # only authorized deterministic context + retrieved chunks
    output_schema_ref: str  # path/id of the JSON schema the response must satisfy


@dataclass(frozen=True)
class LLMResponse:
    output: dict[str, Any]  # already validated against output_schema_ref
    model: str
    prompt_id: str
    prompt_version: str
    retriever_version: str | None
    citations: list[str]
    fallback_used: bool


@runtime_checkable
class LLMProvider(Protocol):
    """Abstract contract for calling the LLM with a versioned, schema-bound prompt."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Send a request to the LLM, validate the output against
        `output_schema_ref`, and return a structured, cited response.
        Implementations must handle: timeout, quota exceeded, retry-once,
        and a controlled fallback response if validation fails.
        """
        ...

    async def is_quota_available(self) -> bool:
        """Check whether the free-tier daily/per-user AI quota still has
        room, so callers can show a graceful message instead of failing."""
        ...
