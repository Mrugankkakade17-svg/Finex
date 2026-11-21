"""
test_rag_corpus_registry.py

Unit tests for FinEx RAG Document Registry and Seeded Corpus.
Task: S2-MI01
Owner: Mitali (@mitali2701)
"""

import json
import tempfile
from pathlib import Path

import pytest

from app.core.document_registry import (
    CorpusFileNotFoundError,
    DuplicateDocumentIdError,
    MissingMetadataError,
    RegistrySchemaError,
    UnregisteredCorpusDocumentError,
    get_default_repo_root,
    load_document_registry,
    validate_document_registry,
)


def test_real_project_registry_loads_and_passes_strict_validation():
    repo_root = get_default_repo_root()
    entries = validate_document_registry(repo_root=repo_root, check_corpus_completeness=True)

    # Must contain at least the 3 existing and 5 new seeded documents = 8 documents
    assert len(entries) >= 8

    # Check each entry has licence and version
    for entry in entries:
        assert entry.doc_id > 0
        assert len(entry.title) > 0
        assert len(entry.version) > 0
        assert len(entry.licence) > 0
        assert entry.is_active is True


def test_seeded_corpus_files_exist_on_disk():
    repo_root = get_default_repo_root()
    corpus_dir = repo_root / "data" / "rag_corpus"
    assert corpus_dir.is_dir(), f"Expected directory {corpus_dir} to exist"

    expected_files = [
        "sec_asset_allocation_diversification.txt",
        "cfpb_compound_interest_and_time_value.txt",
        "sec_mutual_funds_and_etfs.txt",
        "cfpb_risk_tolerance_and_time_horizon.txt",
        "sec_margin_trading_and_leverage_risks.txt",
    ]

    for fname in expected_files:
        p = corpus_dir / fname
        assert p.is_file(), f"Expected seeded corpus document {fname} to exist"
        content = p.read_text(encoding="utf-8")
        assert len(content) > 200, f"Corpus document {fname} appears empty or truncated"
        assert "[Section:" in content, f"Expected [Section: ...] tags in {fname}"


def test_every_registry_document_has_licence_and_version():
    repo_root = get_default_repo_root()
    entries = load_document_registry(repo_root=repo_root)

    for doc in entries:
        has_ver = doc.version is not None and doc.version.strip() != ""
        assert has_ver, f"Doc {doc.doc_id} missing version"
        has_lic = doc.licence is not None and doc.licence.strip() != ""
        assert has_lic, f"Doc {doc.doc_id} missing licence"


def test_registry_rejects_duplicate_document_id():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 1,
                        "title": "Doc A",
                        "filename": "doc_a.txt",
                        "version": "1.0",
                        "licence": "Apache-2.0",
                    },
                    {
                        "doc_id": 1,
                        "title": "Doc B",
                        "filename": "doc_b.txt",
                        "version": "1.0",
                        "licence": "Apache-2.0",
                    },
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(DuplicateDocumentIdError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "Duplicate doc_id 1 detected" in str(exc_info.value)


def test_registry_rejects_missing_licence():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 10,
                        "title": "Unlicensed Doc",
                        "filename": "unlicensed.txt",
                        "version": "1.0",
                        # missing licence
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(MissingMetadataError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "missing mandatory 'licence'" in str(exc_info.value)


def test_registry_rejects_missing_version():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 11,
                        "title": "Versionless Doc",
                        "filename": "versionless.txt",
                        "licence": "Public Domain",
                        # missing version
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(MissingMetadataError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "missing mandatory 'version'" in str(exc_info.value)


def test_registry_rejects_non_existent_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 12,
                        "title": "Ghost Doc",
                        "filename": "does_not_exist_on_disk.txt",
                        "version": "1.0",
                        "licence": "Apache-2.0",
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(CorpusFileNotFoundError) as exc_info:
            validate_document_registry(
                registry_path=reg_file, repo_root=tmp, check_corpus_completeness=False
            )
        assert "points to non-existent file" in str(exc_info.value)


def test_registry_rejects_unregistered_corpus_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        corpus_dir = tmp / "data" / "rag_corpus"
        corpus_dir.mkdir(parents=True)

        valid_doc = corpus_dir / "valid.txt"
        valid_doc.write_text("Valid text", encoding="utf-8")

        unregistered_doc = corpus_dir / "unregistered_leak.txt"
        unregistered_doc.write_text("Unregistered leak text", encoding="utf-8")

        reg_file = tmp / "ai" / "document_registry.json"
        reg_file.parent.mkdir(parents=True)
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 1,
                        "title": "Valid Doc",
                        "filename": "data/rag_corpus/valid.txt",
                        "version": "1.0",
                        "licence": "Apache-2.0",
                    }
                ]
            ),
            encoding="utf-8",
        )

        with pytest.raises(UnregisteredCorpusDocumentError) as exc_info:
            validate_document_registry(
                registry_path=reg_file, repo_root=tmp, check_corpus_completeness=True
            )
        assert "Seeded corpus file is not registered" in str(exc_info.value)


def test_registry_rejects_malformed_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"
        reg_file.write_text("{ this is not valid json }", encoding="utf-8")

        with pytest.raises(RegistrySchemaError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "Malformed JSON" in str(exc_info.value)
