"""
test_minilm_adapter.py

Unit tests for MiniLMEmbeddingAdapter covering configuration, lazy loading,
dimension assertions, batching, input validation, and error propagation.
Task: S2-MI01
Owner: Mitali (@mitali2701)
"""

import math

import pytest

from app.adapters.minilm_embedding_adapter import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    EXPECTED_DIMENSION,
    MODEL_LICENSE,
    DeterministicMockBackend,
    MiniLMEmbeddingAdapter,
)
from app.ports.embedding_port import (
    DimensionMismatchError,
    EmbeddingInferenceError,
    EmbeddingMetadata,
    EmbeddingPort,
    EmptyInputError,
)


def test_adapter_satisfies_embedding_port_protocol():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    assert isinstance(adapter, EmbeddingPort)


def test_lazy_loading_does_not_initialize_model_on_init():
    adapter = MiniLMEmbeddingAdapter(use_fake=False)
    assert adapter._loaded_model is None
    assert adapter._backend is None


def test_mock_backend_deterministic_output():
    backend = DeterministicMockBackend(dimension=384)
    res1 = backend.encode(["Capital market asset allocation"])
    res2 = backend.encode(["Capital market asset allocation"])
    assert res1 == res2
    assert len(res1[0]) == 384


def test_mock_backend_distinct_inputs():
    backend = DeterministicMockBackend(dimension=384)
    res = backend.encode(["Equity stock risk", "Emergency cash deposit"])
    assert res[0] != res[1]


def test_adapter_with_fake_backend_dimension_and_norm():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    vec = adapter.embed_text("Diversification reduces unsystematic portfolio variance")
    assert len(vec) == EXPECTED_DIMENSION
    assert len(vec) == 384

    # Check L2 normalization: sum(x^2) should be approximately 1.0
    norm = math.sqrt(sum(x * x for x in vec))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)


def test_adapter_metadata():
    adapter = MiniLMEmbeddingAdapter(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_version="e4ce9877abf3ed59ced85d227e74ce20d8059e63",
        use_fake=True,
    )
    meta = adapter.get_metadata()
    assert isinstance(meta, EmbeddingMetadata)
    assert meta.model_name == DEFAULT_MODEL_NAME
    assert meta.model_version == DEFAULT_MODEL_REVISION
    assert meta.dimension == EXPECTED_DIMENSION
    assert meta.license == MODEL_LICENSE
    assert meta.provider == "mock"


def test_adapter_single_vs_batch_equivalence():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    text = "Understanding mutual fund expense ratios and NAV"
    single_vec = adapter.embed_text(text)
    batch_vecs = adapter.embed_batch([text])
    assert len(batch_vecs) == 1
    assert single_vec == batch_vecs[0]


def test_adapter_batch_multiple_texts():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    texts = [
        "What is Regulation T margin debt?",
        "How does the Rule of 72 approximate doubling time?",
        "Difference between ETFs and open-end mutual funds.",
    ]
    vecs = adapter.embed_batch(texts)
    assert len(vecs) == 3
    for v in vecs:
        assert len(v) == 384
        assert math.isclose(math.sqrt(sum(x * x for x in v)), 1.0, rel_tol=1e-5)


def test_adapter_empty_batch():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    assert adapter.embed_batch([]) == []


def test_adapter_input_validation_empty_or_whitespace():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    with pytest.raises(EmptyInputError):
        adapter.embed_text("")
    with pytest.raises(EmptyInputError):
        adapter.embed_text("   \t\n  ")
    with pytest.raises(EmptyInputError):
        adapter.embed_batch(["Valid text", "   ", "Another valid text"])


def test_adapter_input_validation_invalid_types():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    with pytest.raises(TypeError):
        adapter.embed_text(1234)  # type: ignore
    with pytest.raises(TypeError):
        adapter.embed_text(None)  # type: ignore
    with pytest.raises(TypeError):
        adapter.embed_batch("not a list of strings")  # type: ignore
    with pytest.raises(TypeError):
        adapter.embed_batch(["valid", 999])  # type: ignore


def test_adapter_dimension_mismatch_error():
    # Inject backend that returns 128-dimensional vectors instead of 384
    class FaultyDimensionBackend:
        def encode(self, texts):
            return [[0.1] * 128 for _ in texts]

    adapter = MiniLMEmbeddingAdapter(backend=FaultyDimensionBackend())
    with pytest.raises(DimensionMismatchError) as exc_info:
        adapter.embed_text("Test sentence")
    assert "Expected embedding dimension 384, got 128" in str(exc_info.value)


def test_adapter_inference_failure_handling():
    class BrokenInferenceBackend:
        def encode(self, texts):
            raise RuntimeError("CUDA device out of memory simulated error")

    adapter = MiniLMEmbeddingAdapter(backend=BrokenInferenceBackend())
    with pytest.raises(EmbeddingInferenceError) as exc_info:
        adapter.embed_text("Test sentence")
    assert "Embedding inference failed" in str(exc_info.value)


def test_adapter_callable_backend_injection():
    # Test support for simple callable backend
    def simple_callable_backend(texts):
        return [[0.05] * 384 for _ in texts]

    adapter = MiniLMEmbeddingAdapter(backend=simple_callable_backend)
    vec = adapter.embed_text("Test sentence with callable backend")
    assert len(vec) == 384
    assert math.isclose(math.sqrt(sum(x * x for x in vec)), 1.0, rel_tol=1e-5)


@pytest.mark.asyncio
async def test_adapter_async_methods():
    adapter = MiniLMEmbeddingAdapter(use_fake=True)
    vec = await adapter.aembed_text("Real estate investment trust dividend yields")
    assert len(vec) == 384

    batch = await adapter.aembed_batch(["Headline 1", "Headline 2"])
    assert len(batch) == 2
    assert len(batch[0]) == 384
    assert len(batch[1]) == 384
