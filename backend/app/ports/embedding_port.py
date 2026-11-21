"""
embedding_port.py

WHAT THIS FILE IS FOR
----------------------
This module defines the abstract embedding contract for FinEx.

The domain and application layers use this port to generate dense semantic
vector embeddings from financial text (e.g., educational documents, regulatory
bulletins, user queries, market news) without taking a direct dependency on
vendor SDKs, Sentence Transformers, Hugging Face, or PyTorch.

THE CORE CONTRACT:
1. Embed single texts or batches of texts into dense floating-point vectors.
2. Expose expected vector dimensionality (e.g., 384 for MiniLM-L6-v2).
3. Validate inputs strictly: non-empty, trimmed, string type.
4. Support both synchronous and asynchronous workflows.
5. Provide traceable model identification and version metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

# Type alias for dense embedding vector
EmbeddingVector = list[float]


class EmbeddingError(Exception):
    """Base exception for all embedding-related errors."""


class EmptyInputError(EmbeddingError, ValueError):
    """Raised when text provided to an embedding function is empty or whitespace only."""


class EmbeddingModelLoadError(EmbeddingError, RuntimeError):
    """Raised when the underlying embedding model fails to initialize or load."""


class EmbeddingInferenceError(EmbeddingError, RuntimeError):
    """Raised when embedding inference fails on given inputs."""


class DimensionMismatchError(EmbeddingError, ValueError):
    """Raised when the output vector dimension does not match the port's declared dimension."""


@dataclass(frozen=True)
class EmbeddingMetadata:
    """Metadata describing an embedding model adapter."""

    model_name: str
    dimension: int
    model_version: str | None = None
    provider: str = "local"
    license: str = "Apache-2.0"
    description: str | None = None


@runtime_checkable
class EmbeddingPort(Protocol):
    """Abstract protocol for text embedding providers.

    All embedding adapters must satisfy this contract.
    """

    @property
    def model_name(self) -> str:
        """The identifier of the embedding model (e.g.

        'sentence-transformers/all-MiniLM-L6-v2').
        """
        ...

    @property
    def dimension(self) -> int:
        """The output vector dimensionality (e.g. 384)."""
        ...

    def get_metadata(self) -> EmbeddingMetadata:
        """Return structured model metadata including name, version, license, and dimension."""
        ...

    def embed_text(self, text: str) -> EmbeddingVector:
        """Synchronously generate an embedding vector for a single text.

        Raises:
            EmptyInputError: If text is empty or contains only whitespace.
            TypeError: If input is not a string.
            EmbeddingInferenceError: If model inference fails.
            DimensionMismatchError: If the output dimension does not match `self.dimension`.
        """
        ...

    def embed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Synchronously generate embedding vectors for a batch of texts.

        An empty input sequence returns an empty list.

        Raises:
            EmptyInputError: If any text in the batch is empty or whitespace only.
            TypeError: If any item in texts is not a string.
            EmbeddingInferenceError: If batch inference fails.
            DimensionMismatchError: If any output vector dimension does not match.
        """
        ...

    async def aembed_text(self, text: str) -> EmbeddingVector:
        """Asynchronously generate an embedding vector for a single text."""
        ...

    async def aembed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        """Asynchronously generate embedding vectors for a batch of texts."""
        ...
