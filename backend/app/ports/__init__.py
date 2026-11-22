"""
backend/app/ports

Abstract interfaces the whole FinEx team codes against instead of vendor
SDKs. See each file's module docstring for what it's for. Concrete
implementations (e.g. `LakebaseOperationalStore`, `MiniLMEmbeddingAdapter`)
live elsewhere (typically under `backend/app/adapters/`) and get built as
later sprints need them.
"""

from app.ports.embedding_port import (
    DimensionMismatchError,
    EmbeddingError,
    EmbeddingInferenceError,
    EmbeddingMetadata,
    EmbeddingModelLoadError,
    EmbeddingPort,
    EmbeddingVector,
    EmptyInputError,
)

__all__ = [
    "EmbeddingPort",
    "EmbeddingMetadata",
    "EmbeddingVector",
    "EmbeddingError",
    "EmptyInputError",
    "EmbeddingModelLoadError",
    "EmbeddingInferenceError",
    "DimensionMismatchError",
]
