"""
ollama_adapter.py

Primary LLM provider adapter connecting to local Ollama runtime.
Wraps small local models (e.g. llama3.2:1b) with finite connection and read timeouts.
Task: S5-MI03
Owner: Mitali (@mitali2701)
"""

from __future__ import annotations

import json
import logging

import httpx

from app.adapters.llm.exceptions import (
    ProviderConnectionError,
    ProviderResponseError,
    ProviderTimeoutError,
    SchemaValidationError,
)
from app.adapters.llm.schema_validator import SchemaValidator
from app.ports.llm_provider import LLMProvider, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_OLLAMA_MODEL = "llama3.2:1b"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 3.0


class OllamaLLMAdapter(LLMProvider):
    """Primary LLM provider adapter wrapping local Ollama service."""

    def __init__(
        self,
        base_url: str = DEFAULT_OLLAMA_URL,
        model_name: str = DEFAULT_OLLAMA_MODEL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
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

    def _build_system_prompt(self, request: LLMRequest) -> str:
        return (
            "You are FinEx educational assistant. Provide clear financial explanations.\n"
            "STRICT COMPLIANCE RULES:\n"
            "1. NEVER give personalized investment advice or recommend stocks to buy/sell.\n"
            "2. NEVER promise guaranteed returns or risk-free profits.\n"
            f"3. Return ONLY valid JSON matching schema '{request.output_schema_ref}'.\n"
            "4. Do not wrap output in extra commentary or text outside the JSON structure."
        )

    def _build_user_prompt(self, request: LLMRequest) -> str:
        return (
            f"Prompt ID: {request.prompt_id} (Version: {request.prompt_version})\n"
            f"Output Schema: {request.output_schema_ref}\n"
            f"Context: {json.dumps(request.context, default=str)}"
        )

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

        # De-duplicate while preserving order
        return list(dict.fromkeys(citations))

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Call Ollama /api/chat with timeout, error translation, and schema validation."""
        client = self._get_client()
        should_close = self._external_client is None

        system_prompt = self._build_system_prompt(request)
        user_prompt = self._build_user_prompt(request)

        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.2,
                "seed": 42,
            },
        }

        endpoint = f"{self.base_url}/api/chat"

        try:
            response = await client.post(endpoint, json=payload)
            if response.status_code == 404:
                # Fallback to legacy /api/generate if /api/chat is not available
                gen_payload = {
                    "model": self.model_name,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.2, "seed": 42},
                }
                response = await client.post(f"{self.base_url}/api/generate", json=gen_payload)

            if response.status_code != 200:
                raise ProviderResponseError(
                    f"Ollama returned HTTP {response.status_code}: {response.text[:200]}",
                    provider="ollama",
                )

            data = response.json()
            # Extract content from /api/chat (message.content) or /api/generate (response)
            if "message" in data and isinstance(data["message"], dict):
                content = data["message"].get("content", "")
            elif "response" in data:
                content = data.get("response", "")
            else:
                raise SchemaValidationError(
                    "Ollama response missing expected 'message' or 'response' payload",
                    provider="ollama",
                )

            if not content or not str(content).strip():
                raise SchemaValidationError(
                    "Ollama returned empty text content",
                    provider="ollama",
                )

            validated_output = SchemaValidator.parse_and_validate(
                content,
                schema_ref=request.output_schema_ref,
                provider="ollama",
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
                fallback_used=False,
            )

        except httpx.ConnectError as exc:
            logger.warning("Ollama connection failed at %s: %s", endpoint, exc)
            raise ProviderConnectionError(
                f"Ollama daemon unreachable at {self.base_url}: {exc}",
                provider="ollama",
            ) from exc
        except httpx.TimeoutException as exc:
            logger.warning("Ollama request timed out after %ss: %s", self.timeout_seconds, exc)
            raise ProviderTimeoutError(
                f"Ollama request timed out after {self.timeout_seconds}s",
                provider="ollama",
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("Ollama HTTP transport error: %s", exc)
            raise ProviderResponseError(
                f"Ollama HTTP error: {exc}",
                provider="ollama",
            ) from exc
        finally:
            if should_close:
                await client.aclose()

    async def is_quota_available(self) -> bool:
        """Check if local Ollama daemon is reachable and responding."""
        client = self._get_client()
        should_close = self._external_client is None
        try:
            resp = await client.get(
                f"{self.base_url}/api/version",
                timeout=httpx.Timeout(self.connect_timeout_seconds),
            )
            return resp.status_code == 200
        except Exception:
            return False
        finally:
            if should_close:
                await client.aclose()
