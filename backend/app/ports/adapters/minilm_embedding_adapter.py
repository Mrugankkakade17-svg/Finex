"""
minilm_embedding_adapter.py (ports/adapters re-export)

Allows importing MiniLMEmbeddingAdapter from app.ports.adapters as specified
in the architectural blueprint.
"""

from app.adapters.minilm_embedding_adapter import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    EXPECTED_DIMENSION,
    MODEL_LICENSE,
    DeterministicMockBackend,
    MiniLMEmbeddingAdapter,
)

__all__ = [
    "MiniLMEmbeddingAdapter",
    "DeterministicMockBackend",
    "DEFAULT_MODEL_NAME",
    "DEFAULT_MODEL_REVISION",
    "EXPECTED_DIMENSION",
    "MODEL_LICENSE",
]
