"""backend/app/adapters."""

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
