"""
Unit tests for S1-AI-02 RAG Prototype and Document Chunking.
Owner: Palak
Task: S1-AI-02
"""

import importlib.util
import os
import pytest

AI_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(AI_DIR, "01_rag_prototype.py")

spec = importlib.util.spec_from_file_location("rag_prototype_mod", MODULE_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load module from {MODULE_PATH}")
rag_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag_mod)


def test_document_registry_structure():
    registry_path = os.path.join(AI_DIR, "document_registry.json")
    registry = rag_mod.load_document_registry(registry_path)

    assert len(registry) >= 3, "Must have at least 3 approved sample financial documents"
    for doc in registry:
        assert "doc_id" in doc
        assert "title" in doc
        assert "filename" in doc
        assert "source" in doc
        assert "document_date" in doc
        assert "doc_type" in doc
        assert os.path.exists(os.path.join(AI_DIR, doc["filename"]))


def test_chunking_metadata_attachment():
    factsheet_path = os.path.join(AI_DIR, "sample_factsheet.txt")
    chunks = rag_mod.chunk_financial_document(
        filepath=factsheet_path,
        source_name="FinEx_Global_Equity_Factsheet_Q3",
        doc_date="2026-08-01",
        doc_id=1,
    )

    assert len(chunks) >= 4
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "doc_id" in chunk
        assert "source" in chunk
        assert "document_date" in chunk
        assert "section" in chunk
        assert "chunk_index" in chunk
        assert "text" in chunk
        assert chunk["source"] == "FinEx_Global_Equity_Factsheet_Q3"
        assert chunk["document_date"] == "2026-08-01"


def test_ingest_all_registered_documents():
    all_chunks = rag_mod.ingest_all_registered_documents(AI_DIR)
    assert len(all_chunks) >= 10, "Expected at least 10 chunks across 3 documents"
    sources = {c["source"] for c in all_chunks}
    assert len(sources) == 3, "Expected chunks from 3 distinct sources"


def test_retrieval_five_golden_questions():
    all_chunks = rag_mod.ingest_all_registered_documents(AI_DIR)
    results = rag_mod.run_evaluation_suite(all_chunks)

    assert len(results) == 5
    for res in results:
        assert res["retrieved_chunk"] is not None, f"Failed retrieval for {res['question_id']}"
        assert res["retrieved_chunk"]["section"] is not None
        assert res["retrieved_chunk"]["source"] is not None
        assert res["passed"] is True, f"Failed match on {res['question_id']}: {res['question']}"
