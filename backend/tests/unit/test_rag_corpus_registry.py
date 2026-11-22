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
    UnsafePathError,
    compute_file_sha256,
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


def test_registry_rejects_path_traversal():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"

        # Traversal in filename
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 99,
                        "title": "Escape Attempt",
                        "filename": "../../../etc/passwd",
                        "version": "1.0",
                        "licence": "Apache-2.0",
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(UnsafePathError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "unsafe or escaping path" in str(exc_info.value)

        # Absolute path in filename
        abs_target = "C:/secret.txt" if Path("C:/").exists() else "/secret.txt"
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 100,
                        "title": "Absolute Escape",
                        "filename": abs_target,
                        "version": "1.0",
                        "licence": "Apache-2.0",
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(UnsafePathError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "unsafe or escaping path" in str(exc_info.value)


def test_registry_rejects_whitespace_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        reg_file = tmp / "document_registry.json"

        # Whitespace licence
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 101,
                        "title": "Whitespace Licence",
                        "filename": "doc.txt",
                        "version": "1.0",
                        "licence": "    \t  ",
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(MissingMetadataError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "missing mandatory 'licence'" in str(exc_info.value)

        # Whitespace version
        reg_file.write_text(
            json.dumps(
                [
                    {
                        "doc_id": 102,
                        "title": "Whitespace Version",
                        "filename": "doc.txt",
                        "version": "   \n ",
                        "licence": "Apache-2.0",
                    }
                ]
            ),
            encoding="utf-8",
        )
        with pytest.raises(MissingMetadataError) as exc_info:
            load_document_registry(registry_path=reg_file)
        assert "missing mandatory 'version'" in str(exc_info.value)


def test_corpus_files_sha256_checksums():
    repo_root = get_default_repo_root()
    expected_checksums = {
        1: (
            "ai/sample_factsheet.txt",
            "b6f7bb781eb8664d4898f85b92673037a6a718cf619ca18529b77644e1f24a18",
        ),
        2: (
            "ai/sample_fund_prospectus.txt",
            "06a51cd9cd1e759a0b30b7b7a93054520904f0c1e48d1a269d6a4e18b07069e7",
        ),
        3: (
            "ai/sample_market_commentary.txt",
            "33816b14162d0f1a35cde71238797152812215c7e4101e0e5970f0bc8c3af454",
        ),
        4: (
            "data/rag_corpus/sec_asset_allocation_diversification.txt",
            "0a8f67cc3e079772c36a94e193fca7ec202e2ead6b981d575c2a6a0f959973eb",
        ),
        5: (
            "data/rag_corpus/cfpb_compound_interest_and_time_value.txt",
            "2fb4b2dd078bbd0c01a5a0590e860fea5cefe7ed42f627e1ea1f4b008f065aa1",
        ),
        6: (
            "data/rag_corpus/sec_mutual_funds_and_etfs.txt",
            "ab80754d24aa47c8dabf6a7d1df31304d7494425715eb1b5b46e1ff63e82b886",
        ),
        7: (
            "data/rag_corpus/cfpb_risk_tolerance_and_time_horizon.txt",
            "318ee5de89a49e45cc3cbbc7fe1213d316cc92b55554f5bed13fe42f359ad809",
        ),
        8: (
            "data/rag_corpus/sec_margin_trading_and_leverage_risks.txt",
            "b9161be77442383d71aa9e3985e16c92007e314749ea18224945dcb8a86e3dca",
        ),
    }

    entries = validate_document_registry(repo_root=repo_root)
    for entry in entries:
        assert entry.doc_id in expected_checksums
        expected_path, expected_hash = expected_checksums[entry.doc_id]
        actual_path = repo_root / expected_path
        assert actual_path.is_file(), f"File missing: {actual_path}"
        actual_hash = compute_file_sha256(actual_path)
        assert actual_hash == expected_hash, (
            f"Doc #{entry.doc_id} ({entry.title}) SHA-256 hash mismatch! "
            f"Expected {expected_hash}, got {actual_hash}"
        )
