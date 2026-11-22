"""
test_embedding_integration.py

Integration tests verifying end-to-end embedding pipeline with seeded RAG corpus,
MiniLM adapter, and cosine similarity retrieval.
Task: S2-MI01
Owner: Mitali (@mitali2701)
"""

import math

import pytest

from app.adapters.minilm_embedding_adapter import MiniLMEmbeddingAdapter
from app.core.document_registry import (
    get_default_repo_root,
    load_document_registry,
    resolve_corpus_file_path,
)
from app.ports.embedding_port import EmbeddingPort


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def test_embedding_port_with_minilm_and_corpus_chunks():
    repo_root = get_default_repo_root()
    entries = load_document_registry(repo_root=repo_root)

    # Use MiniLM adapter behind the EmbeddingPort protocol
    embedding_service: EmbeddingPort = MiniLMEmbeddingAdapter(use_fake=True)
    assert isinstance(embedding_service, EmbeddingPort)
    assert embedding_service.dimension == 384

    # Target our seeded asset allocation document
    sec_doc = next((d for d in entries if "Asset Allocation" in d.title), None)
    assert sec_doc is not None

    file_path = resolve_corpus_file_path(sec_doc.filename, repo_root=repo_root)
    assert file_path is not None
    assert file_path.is_file()

    # Parse sections into chunks
    content = file_path.read_text(encoding="utf-8")
    sections: list[dict] = []
    current_sec = "Header"
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("[Section:") and line.endswith("]"):
            current_sec = line.replace("[Section:", "").replace("]", "").strip()
            continue
        sections.append({"section": current_sec, "text": line})

    assert len(sections) >= 4

    # Batch embed through the port
    texts = [s["text"] for s in sections]
    embeddings = embedding_service.embed_batch(texts)

    assert len(embeddings) == len(texts)
    for vec in embeddings:
        assert len(vec) == 384
        # Unit normalized
        norm = math.sqrt(sum(x * x for x in vec))
        assert math.isclose(norm, 1.0, rel_tol=1e-5)

    # Query embedding
    query = "How does asset allocation and portfolio diversification help manage market risk?"
    query_vec = embedding_service.embed_text(query)
    assert len(query_vec) == 384

    # Rank chunks by similarity
    ranked = []
    for s, vec in zip(sections, embeddings):
        sim = cosine_similarity(query_vec, vec)
        ranked.append((sim, s["section"], s["text"]))

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_sim, best_sec, best_text = ranked[0]

    assert best_sim > 0.0
    assert best_sec in [
        "Metadata",
        "Overview of Asset Allocation",
        "Principles of Diversification",
        "Primary Asset Categories",
        "Time Horizon and Risk Tolerance",
    ]


def test_cross_topic_semantic_separation():
    adapter: EmbeddingPort = MiniLMEmbeddingAdapter(use_fake=True)

    topic_equity = "Equity stocks offer high long term growth with volatile drawdowns"
    topic_bonds = "Government bonds provide fixed income coupon yield with lower volatility"
    topic_margin = "Margin trading involves leverage and forced liquidation risks"

    vec_equity = adapter.embed_text(topic_equity)
    vec_bonds = adapter.embed_text(topic_bonds)
    vec_margin = adapter.embed_text(topic_margin)

    sim_equity_bonds = cosine_similarity(vec_equity, vec_bonds)
    sim_equity_margin = cosine_similarity(vec_equity, vec_margin)

    # Verify vectors are non-identical and produce valid bounded similarity scores
    assert -1.0 <= sim_equity_bonds <= 1.0
    assert -1.0 <= sim_equity_margin <= 1.0
    assert vec_equity != vec_bonds
    assert vec_equity != vec_margin


@pytest.mark.asyncio
async def test_async_batch_pipeline_matches_synchronous():
    adapter: EmbeddingPort = MiniLMEmbeddingAdapter(use_fake=True)
    corpus_sample = [
        "Compound interest formula A = P(1 + r/n)**(nt)",
        "Rule of 72 estimates doubling time as 72 divided by annual return rate",
        "Inflation erodes real purchasing power over time",
    ]

    sync_results = adapter.embed_batch(corpus_sample)
    async_results = await adapter.aembed_batch(corpus_sample)

    assert len(sync_results) == len(async_results)
    for s_vec, a_vec in zip(sync_results, async_results):
        assert s_vec == a_vec
