"""
document_registry.py

WHAT THIS FILE IS FOR
----------------------
This module provides the schema, loader, and strict validation engine for
FinEx's RAG Document Registry (`ai/document_registry.json`).

Acceptance Criteria & Quality Invariants:
1. Every document MUST have an identifiable licence and version.
2. Every document ID MUST be unique.
3. Every registry entry MUST resolve to an existing corpus file on disk.
4. Every seeded file in `data/rag_corpus/` MUST be registered.
5. Path traversal, duplicate IDs, or missing required metadata MUST be rejected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class DocumentRegistryError(Exception):
    """Base exception for document registry errors."""


class RegistrySchemaError(DocumentRegistryError, ValueError):
    """Raised when registry JSON does not conform to required schema."""


class UnsafePathError(RegistrySchemaError):
    """Raised when a document path attempts directory traversal or is an absolute path."""


class MissingMetadataError(DocumentRegistryError, ValueError):
    """Raised when a document is missing mandatory metadata such as licence or version."""


class DuplicateDocumentIdError(DocumentRegistryError, ValueError):
    """Raised when duplicate document IDs exist in the registry."""


class CorpusFileNotFoundError(DocumentRegistryError, FileNotFoundError):
    """Raised when a registered document file cannot be found on disk."""


class UnregisteredCorpusDocumentError(DocumentRegistryError, ValueError):
    """Raised when a corpus file in data/rag_corpus is not registered in the registry."""


@dataclass(frozen=True)
class DocumentEntry:
    doc_id: int
    title: str
    filename: str
    source: str
    doc_type: str
    document_date: str
    version: str
    licence: str
    source_url: str | None = None
    filepath: str | None = None
    uploaded_by: int | None = None
    is_active: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


def get_default_repo_root() -> Path:
    # Resolves: backend/app/core/document_registry.py -> 3 up to backend -> 1 up to repo root
    return Path(__file__).resolve().parent.parent.parent.parent


def get_default_registry_path(repo_root: Path | str | None = None) -> Path:
    root = Path(repo_root) if repo_root else get_default_repo_root()
    return root / "ai" / "document_registry.json"


def resolve_corpus_file_path(filename: str, repo_root: Path | str | None = None) -> Path | None:
    """Resolve a document's filename against canonical locations.

    Checks repo root, ai/, or data/rag_corpus/. Guarantees that resolved paths are
    strictly contained within the repository root and rejects path traversal components
    (e.g., '..') or absolute paths.
    """
    root = (Path(repo_root) if repo_root else get_default_repo_root()).resolve()

    # Reject absolute paths and directory traversal
    raw_path = Path(filename)
    if raw_path.is_absolute() or any(part == ".." for part in raw_path.parts):
        return None

    # Candidate 1: relative to repo root
    cand1 = (root / filename).resolve()
    if cand1.is_file():
        try:
            cand1.relative_to(root)
            return cand1
        except ValueError:
            return None

    # Candidate 2: relative to ai/
    cand2 = (root / "ai" / filename).resolve()
    if cand2.is_file():
        try:
            cand2.relative_to(root)
            return cand2
        except ValueError:
            return None

    # Candidate 3: relative to data/rag_corpus/
    cand3 = (root / "data" / "rag_corpus" / filename).resolve()
    if cand3.is_file():
        try:
            cand3.relative_to(root)
            return cand3
        except ValueError:
            return None

    return None


def compute_file_sha256(file_path: Path | str) -> str:
    """Calculate the SHA-256 hexadecimal digest of a file."""
    import hashlib

    p = Path(file_path)
    if not p.is_file():
        raise FileNotFoundError(f"File not found for checksum calculation: {p}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_document_registry(
    registry_path: Path | str | None = None, repo_root: Path | str | None = None
) -> list[DocumentEntry]:
    """Load and parse document registry without strict disk validation."""
    path = Path(registry_path) if registry_path else get_default_registry_path(repo_root)
    if not path.is_file():
        raise FileNotFoundError(f"Document registry not found at: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as exc:
        raise RegistrySchemaError(f"Malformed JSON in document registry {path}: {exc}") from exc

    if not isinstance(raw_data, list):
        cls_name = type(raw_data).__name__
        raise RegistrySchemaError(f"Document registry root must be a JSON array, got {cls_name}")

    entries: list[DocumentEntry] = []
    seen_ids: set[int] = set()

    for idx, item in enumerate(raw_data):
        if not isinstance(item, dict):
            entry_type = type(item).__name__
            raise RegistrySchemaError(
                f"Registry entry at index {idx} must be dict, got {entry_type}"
            )

        doc_id = item.get("doc_id")
        if doc_id is None or not isinstance(doc_id, int):
            raise RegistrySchemaError(f"Entry at index {idx} has invalid doc_id: {doc_id}")
        if doc_id in seen_ids:
            raise DuplicateDocumentIdError(f"Duplicate doc_id {doc_id} detected in registry")
        seen_ids.add(doc_id)

        title = item.get("title")
        if not title or not isinstance(title, str) or not title.strip():
            raise RegistrySchemaError(f"Entry {doc_id} is missing valid title")

        filename = item.get("filename") or item.get("filepath")
        if not filename or not isinstance(filename, str) or not filename.strip():
            raise RegistrySchemaError(f"Entry {doc_id} is missing valid filename")

        # Reject path traversal and absolute paths
        raw_path = Path(filename)
        if raw_path.is_absolute() or any(p == ".." for p in raw_path.parts):
            raise UnsafePathError(
                f"Entry {doc_id} ('{title}') contains unsafe or escaping path: {filename}"
            )

        filepath_val = item.get("filepath")
        if filepath_val and isinstance(filepath_val, str):
            raw_fpath = Path(filepath_val)
            if raw_fpath.is_absolute() or any(p == ".." for p in raw_fpath.parts):
                raise UnsafePathError(
                    f"Entry {doc_id} ('{title}') contains unsafe or escaping filepath: "
                    f"{filepath_val}"
                )

        version = item.get("version")
        if not version or not isinstance(version, str) or not version.strip():
            raise MissingMetadataError(f"Entry {doc_id} ('{title}') is missing mandatory 'version'")

        licence = item.get("licence") or item.get("license")
        if not licence or not isinstance(licence, str) or not licence.strip():
            raise MissingMetadataError(f"Entry {doc_id} ('{title}') is missing mandatory 'licence'")

        entries.append(
            DocumentEntry(
                doc_id=doc_id,
                title=title.strip(),
                filename=filename.strip(),
                filepath=item.get("filepath"),
                source=item.get("source", "Unknown").strip(),
                doc_type=item.get("doc_type", "general").strip(),
                document_date=item.get("document_date", "").strip(),
                version=version.strip(),
                licence=licence.strip(),
                source_url=item.get("source_url"),
                uploaded_by=item.get("uploaded_by"),
                is_active=bool(item.get("is_active", True)),
                metadata={
                    k: v
                    for k, v in item.items()
                    if k
                    not in {
                        "doc_id",
                        "title",
                        "filename",
                        "filepath",
                        "source",
                        "doc_type",
                        "document_date",
                        "version",
                        "licence",
                        "license",
                        "source_url",
                        "uploaded_by",
                        "is_active",
                    }
                },
            )
        )

    return entries


def validate_document_registry(
    registry_path: Path | str | None = None,
    repo_root: Path | str | None = None,
    check_corpus_completeness: bool = True,
) -> list[DocumentEntry]:
    """Strictly validate document registry entries, metadata, files, and corpus completeness."""
    root = Path(repo_root) if repo_root else get_default_repo_root()
    entries = load_document_registry(registry_path=registry_path, repo_root=root)

    registered_files: set[Path] = set()

    for entry in entries:
        resolved = resolve_corpus_file_path(entry.filename, repo_root=root)
        if resolved is None and entry.filepath:
            resolved = resolve_corpus_file_path(entry.filepath, repo_root=root)

        if resolved is None or not resolved.is_file():
            err_msg = (
                f"Registered document {entry.doc_id} ('{entry.title}') "
                f"points to non-existent file: {entry.filename}"
            )
            raise CorpusFileNotFoundError(err_msg)
        registered_files.add(resolved.resolve())

    if check_corpus_completeness:
        rag_corpus_dir = root / "data" / "rag_corpus"
        if rag_corpus_dir.is_dir():
            for corpus_file in rag_corpus_dir.iterdir():
                if corpus_file.is_file() and corpus_file.suffix in {".txt", ".md", ".json"}:
                    if corpus_file.resolve() not in registered_files:
                        unreg_msg = (
                            f"Seeded corpus file is not registered in document_registry.json: "
                            f"{corpus_file.name}"
                        )
                        raise UnregisteredCorpusDocumentError(unreg_msg)

    return entries


__all__ = [
    "DocumentRegistryError",
    "RegistrySchemaError",
    "UnsafePathError",
    "MissingMetadataError",
    "DuplicateDocumentIdError",
    "CorpusFileNotFoundError",
    "UnregisteredCorpusDocumentError",
    "DocumentEntry",
    "get_default_repo_root",
    "get_default_registry_path",
    "resolve_corpus_file_path",
    "compute_file_sha256",
    "load_document_registry",
    "validate_document_registry",
]
