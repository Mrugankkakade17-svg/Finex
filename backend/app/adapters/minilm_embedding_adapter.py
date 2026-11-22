"""
minilm_embedding_adapter.py

WHAT THIS FILE IS FOR
----------------------
This module implements the MiniLM embedding adapter behind FinEx's
EmbeddingPort protocol.

Model: sentence-transformers/all-MiniLM-L6-v2
Dimension: 384
License: Apache-2.0
Default Device: CPU (8 threads per S0-MI02 baseline benchmark)

KEY DESIGN HIGHLIGHTS:
1. Implements EmbeddingPort interface cleanly.
2. Lazy Loading: Does NOT import PyTorch / SentenceTransformers or load
   model weights on application startup.
3. Injectable Backend: Supports dependency injection of custom backends
   or mock models for fast, network-free, deterministic unit testing.
4. Input & Output Validation: Enforces strict type checking, non-empty
   string constraints, and 384-dimensional output vector assertions.
5. Async Friendly: Provides `aembed_text` and `aembed_batch` offloading CPU
   work to worker threads without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import hashlib
import math
from typing import Any, Sequence

from app.ports.embedding_port import (
    DimensionMismatchError,
    EmbeddingInferenceError,
    EmbeddingMetadata,
    EmbeddingModelLoadError,
    EmbeddingPort,
    EmbeddingVector,
    EmptyInputError,
)

DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODEL_REVISION = "e4ce9877abf3ed59ced85d227e74ce20d8059e63"
EXPECTED_DIMENSION = 384
MODEL_LICENSE = "Apache-2.0"


class DeterministicMockBackend:
    """Fast, reproducible mock backend for offline testing without PyTorch or network access.

    Produces mathematically consistent 384-dimensional L2-normalized vectors
    derived from cryptographic text hashing.
    """

    def __init__(self, dimension: int = EXPECTED_DIMENSION):
        self.dimension = dimension

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for text in texts:
            # Generate deterministic pseudo-random components via SHA-256 rolling digest
            vector: list[float] = []
            seed = text.encode("utf-8")
            h = hashlib.sha256(seed).digest()
            while len(vector) < self.dimension:
                for b in h:
                    # Normalize byte (0-255) to float roughly around 0
                    vector.append((float(b) - 127.5) / 127.5)
                    if len(vector) == self.dimension:
                        break
                h = hashlib.sha256(h + seed).digest()

            # L2 normalize
            norm = math.sqrt(sum(x * x for x in vector))
            if norm > 0.0:
                vector = [x / norm for x in vector]
            results.append(vector)
        return results


class MiniLMEmbeddingAdapter(EmbeddingPort):
    """Adapter for all-MiniLM-L6-v2 implementing EmbeddingPort."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        model_version: str | None = DEFAULT_MODEL_REVISION,
        device: str = "cpu",
        use_fake: bool = False,
        backend: Any | None = None,
        normalize_embeddings: bool = True,
    ):
        """Initialize the MiniLM adapter.

        Model weights are NOT loaded here (lazy initialization).
        """
        self._model_name = model_name
        self._model_version = model_version
        self._device = device
        self._use_fake = use_fake
        self._backend = backend
        self._normalize_embeddings = normalize_embeddings
        self._loaded_model: Any | None = None

        if self._use_fake and self._backend is None:
            self._backend = DeterministicMockBackend(dimension=EXPECTED_DIMENSION)

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return EXPECTED_DIMENSION

    def get_metadata(self) -> EmbeddingMetadata:
        is_mock = self._use_fake or isinstance(self._backend, DeterministicMockBackend)
        provider = "mock" if is_mock else "local-cpu"
        return EmbeddingMetadata(
            model_name=self._model_name,
            dimension=self.dimension,
            model_version=self._model_version,
            provider=provider,
            license=MODEL_LICENSE,
            description="Dense semantic embeddings using all-MiniLM-L6-v2 (384-dimensional).",
            is_normalized=self._normalize_embeddings,
        )

    def _validate_single_input(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError(f"Input text must be a string, got {type(text).__name__}")
        trimmed = text.strip()
        if not trimmed:
            raise EmptyInputError("Text to embed cannot be empty or whitespace only.")
        return trimmed

    def _validate_batch_input(self, texts: Sequence[str]) -> list[str]:
        if not isinstance(texts, (list, tuple)):
            cls_name = type(texts).__name__
            raise TypeError(f"Input texts must be a sequence of strings, got {cls_name}")
        validated: list[str] = []
        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(f"Item at index {i} must be a string, got {type(text).__name__}")
            trimmed = text.strip()
            if not trimmed:
                raise EmptyInputError(f"Item at index {i} cannot be empty or whitespace only.")
            validated.append(trimmed)
        return validated

    def _get_backend(self) -> Any:
        """Lazily load and return the inference backend."""
        if self._backend is not None:
            return self._backend

        if self._loaded_model is not None:
            return self._loaded_model

        try:
            # Try sentence-transformers first
            from sentence_transformers import SentenceTransformer

            self._loaded_model = SentenceTransformer(
                self._model_name,
                device=self._device,
                revision=self._model_version,
            )
            return self._loaded_model
        except ImportError:
            pass
        except Exception as exc:
            raise EmbeddingModelLoadError(
                f"Failed to load SentenceTransformer model '{self._model_name}': {exc}"
            ) from exc

        try:
            # Try transformers pipeline / AutoModel fallback
            import torch
            from transformers import AutoModel, AutoTokenizer

            tokenizer = AutoTokenizer.from_pretrained(
                self._model_name,
                revision=self._model_version,
            )
            model = AutoModel.from_pretrained(
                self._model_name,
                revision=self._model_version,
            )
            model.eval()
            if self._device == "cpu":
                torch.set_num_threads(8)

            class TransformersBackend:
                def __init__(self, tok, mdl, normalize):
                    self.tok = tok
                    self.mdl = mdl
                    self.normalize = normalize

                def encode(self, texts_to_encode: Sequence[str]) -> list[list[float]]:
                    encoded = self.tok(
                        list(texts_to_encode),
                        padding=True,
                        truncation=True,
                        max_length=256,
                        return_tensors="pt",
                    )
                    with torch.no_grad():
                        outputs = self.mdl(**encoded)
                        # Mean pooling with attention mask
                        token_embeddings = outputs.last_hidden_state
                        input_mask_expanded = (
                            encoded["attention_mask"]
                            .unsqueeze(-1)
                            .expand(token_embeddings.size())
                            .float()
                        )
                        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                        pooled = sum_embeddings / sum_mask

                        if self.normalize:
                            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)

                        return pooled.cpu().tolist()

            self._loaded_model = TransformersBackend(tokenizer, model, self._normalize_embeddings)
            return self._loaded_model
        except ImportError as exc:
            raise EmbeddingModelLoadError(
                "Neither 'sentence-transformers' nor 'transformers' + 'torch' are installed. "
                "Install dependencies or pass `backend` / `use_fake=True` for offline testing."
            ) from exc
        except Exception as exc:
            raise EmbeddingModelLoadError(
                f"Failed to initialize Hugging Face transformers model '{self._model_name}': {exc}"
            ) from exc

    def _normalize_vector(self, vec: list[float]) -> list[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0.0:
            return [x / norm for x in vec]
        return vec

    def embed_text(self, text: str) -> EmbeddingVector:
        cleaned = self._validate_single_input(text)
        results = self.embed_batch([cleaned])
        return results[0]

    def embed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        if not texts:
            return []

        cleaned_texts = self._validate_batch_input(texts)
        backend = self._get_backend()

        try:
            if hasattr(backend, "encode"):
                fn = backend.encode
                varnames = getattr(getattr(fn, "__code__", None), "co_varnames", ())
                has_norm_param = "normalize_embeddings" in varnames
                if has_norm_param:
                    raw_output = fn(cleaned_texts, normalize_embeddings=self._normalize_embeddings)
                else:
                    raw_output = fn(cleaned_texts)
            elif callable(backend):
                raw_output = backend(cleaned_texts)
            else:
                err_msg = f"Configured backend {type(backend)} is not callable and has no .encode()"
                raise EmbeddingInferenceError(err_msg)

            # Convert numpy/tensor to standard python list[float]
            vectors: list[EmbeddingVector] = []
            for item in raw_output:
                if hasattr(item, "tolist"):
                    v = item.tolist()
                elif isinstance(item, (list, tuple)):
                    v = [float(x) for x in item]
                else:
                    raise EmbeddingInferenceError(f"Unexpected vector item type: {type(item)}")

                if len(v) != self.dimension:
                    raise DimensionMismatchError(
                        f"Expected embedding dimension {self.dimension}, got {len(v)}"
                    )

                if self._normalize_embeddings:
                    v = self._normalize_vector(v)

                vectors.append(v)

            return vectors

        except (EmptyInputError, TypeError, DimensionMismatchError, EmbeddingModelLoadError):
            raise
        except Exception as exc:
            raise EmbeddingInferenceError(f"Embedding inference failed: {exc}") from exc

    async def aembed_text(self, text: str) -> EmbeddingVector:
        return await asyncio.to_thread(self.embed_text, text)

    async def aembed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        return await asyncio.to_thread(self.embed_batch, texts)
