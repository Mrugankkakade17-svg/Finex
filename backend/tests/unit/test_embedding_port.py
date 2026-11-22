"""
test_embedding_port.py

Unit tests covering the EmbeddingPort contract, metadata structures, and error hierarchies.
Task: S2-MI01
Owner: Mitali (@mitali2701)
"""

from typing import Sequence

import pytest

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


class DummyValidPort:
    """Minimal compliant implementation for contract testing."""

    @property
    def model_name(self) -> str:
        return "dummy-model"

    @property
    def dimension(self) -> int:
        return 384

    def get_metadata(self) -> EmbeddingMetadata:
        return EmbeddingMetadata(
            model_name=self.model_name,
            dimension=self.dimension,
            model_version="1.0.0",
            provider="dummy",
            license="Apache-2.0",
            description="Dummy test embedding port",
        )

    def embed_text(self, text: str) -> EmbeddingVector:
        if not isinstance(text, str):
            raise TypeError("Expected string")
        if not text.strip():
            raise EmptyInputError("Empty text")
        return [0.1] * self.dimension

    def embed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        if not texts:
            return []
        return [self.embed_text(t) for t in texts]

    async def aembed_text(self, text: str) -> EmbeddingVector:
        return self.embed_text(text)

    async def aembed_batch(self, texts: Sequence[str]) -> list[EmbeddingVector]:
        return self.embed_batch(texts)


def test_embedding_port_runtime_checkable():
    port = DummyValidPort()
    assert isinstance(port, EmbeddingPort)


def test_embedding_port_missing_method_fails_protocol():
    class IncompletePort:
        @property
        def model_name(self) -> str:
            return "incomplete"

    port = IncompletePort()
    assert not isinstance(port, EmbeddingPort)


def test_embedding_metadata_fields():
    meta = EmbeddingMetadata(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
        model_version="e4ce9877abf3ed59ced85d227e74ce20d8059e63",
        provider="local-cpu",
        license="Apache-2.0",
        description="MiniLM 384-dimensional dense semantic embeddings",
    )
    assert meta.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert meta.dimension == 384
    assert meta.model_version == "e4ce9877abf3ed59ced85d227e74ce20d8059e63"
    assert meta.provider == "local-cpu"
    assert meta.license == "Apache-2.0"
    assert meta.description is not None
    assert meta.is_normalized is True


def test_embedding_exceptions_hierarchy():
    assert issubclass(EmptyInputError, (EmbeddingError, ValueError))
    assert issubclass(EmbeddingModelLoadError, (EmbeddingError, RuntimeError))
    assert issubclass(EmbeddingInferenceError, (EmbeddingError, RuntimeError))
    assert issubclass(DimensionMismatchError, (EmbeddingError, ValueError))


def test_dummy_port_embed_text_success():
    port = DummyValidPort()
    vec = port.embed_text("Portfolio risk and asset diversification")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert all(isinstance(x, float) for x in vec)


def test_dummy_port_embed_batch_success():
    port = DummyValidPort()
    batch = ["Asset allocation", "Compound interest", "Exchange traded funds"]
    res = port.embed_batch(batch)
    assert len(res) == 3
    for vec in res:
        assert len(vec) == 384


def test_dummy_port_empty_input_handling():
    port = DummyValidPort()
    with pytest.raises(EmptyInputError):
        port.embed_text("")
    with pytest.raises(EmptyInputError):
        port.embed_text("   \n\t  ")


def test_dummy_port_invalid_type_handling():
    port = DummyValidPort()
    with pytest.raises(TypeError):
        port.embed_text(12345)  # type: ignore
    with pytest.raises(TypeError):
        port.embed_text(None)  # type: ignore


def test_dummy_port_empty_batch():
    port = DummyValidPort()
    assert port.embed_batch([]) == []


@pytest.mark.asyncio
async def test_dummy_port_async_methods():
    port = DummyValidPort()
    vec = await port.aembed_text("Liquid emergency reserve")
    assert len(vec) == 384

    batch_vecs = await port.aembed_batch(["Goal 1", "Goal 2"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 384
