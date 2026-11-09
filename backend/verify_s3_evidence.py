"""Passive S3 evidence guards; no child, API, database or output creation.

Original artifact bytes and each current runtime source are read boundedly,
checked twice and bound to the exact clean checkout before any success.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import stat
from pathlib import Path
from typing import Any, NoReturn

from local_s2_evidence import loads, manifest_sha256, safe_object
from verify_s1_application import ROOT, SHA_PATTERN, AcceptanceFailure, _git, _require
from verify_s3_foundation import (
    APP_SOURCE,
    CASE_IDS,
    COMMAND,
    FOUNDATION_VERSION,
    HASH,
    MAX_ARTIFACT,
    REPORT_SCHEMA,
    REQUIRED_CHECKS,
    SCOPE_FIELDS,
    SOURCE_PATHS,
    private,
    validate_corpus,
)

MAX_SOURCE = 2097152
REPORT_FIELDS = {
    "schema_version",
    *SCOPE_FIELDS,
    "success",
    "mode",
    "tested_commit",
    "tested_tree",
    "working_tree_dirty",
    "tracked_dirty",
    "source_hashes",
    "source_manifest_sha256",
    "checks",
    "required_checks",
    "failures",
    "responses_checked",
    "corpus_sha256",
    "corpus_case_ids",
    "native_process",
    "python_version",
    "limitations",
}
NATIVE_FIELDS = {
    "starts",
    "application_restarts",
    "durable_restarts",
    "storage_fault_restarts",
    "owned_pids",
    "child_reaped",
    "temporary_directory_removed",
    "session_ttl_minutes",
    "real_expiry_elapsed_seconds",
    "shutdown",
}


def repository_snapshot() -> dict[str, object]:
    return {
        "tested_commit": _git(["rev-parse", "HEAD"]),
        "tested_tree": _git(["rev-parse", "HEAD^{tree}"]),
        "working_tree_dirty": bool(_git(["status", "--porcelain", "--untracked-files=normal"])),
        "tracked_dirty": bool(_git(["diff", "--name-only", "HEAD", "--"])),
    }


def _revision(value: object, sha: str, tree: str) -> dict[str, Any]:
    snapshot = safe_object(
        value, {"tested_commit", "tested_tree", "working_tree_dirty", "tracked_dirty"}
    )
    _require(
        snapshot["tested_commit"] == sha
        and snapshot["tested_tree"] == tree
        and snapshot["working_tree_dirty"] is False
        and snapshot["tracked_dirty"] is False,
        "CORPUS_INVALID",
    )
    return snapshot


def _linked(path: Path) -> bool:
    info = path.lstat()
    junction = getattr(path, "is_junction", None)
    return (
        stat.S_ISLNK(info.st_mode)
        or bool(
            getattr(info, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 1024)
        )
        or (callable(junction) and bool(junction()))
    )


def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _path(value: object, *, external: bool) -> Path:
    _require(isinstance(value, Path), "CORPUS_INVALID")
    if not isinstance(value, Path):
        raise AcceptanceFailure("CORPUS_INVALID")
    spelling = str(value)
    _require(
        0 < len(spelling) <= 4096
        and "\x00" not in spelling
        and not spelling.startswith(("\\\\", "//")),
        "CORPUS_INVALID",
    )
    path = value.absolute()
    _require(all(not _linked(item) for item in (path, *path.parents)), "CORPUS_INVALID")
    resolved, root = path.resolve(strict=True), ROOT.resolve(strict=True)
    _require(
        (resolved != root and root not in resolved.parents)
        if external
        else root in resolved.parents,
        "CORPUS_INVALID",
    )
    return path


def regular_bytes(path: Path, maximum: int, *, source: bool = False) -> bytes:
    before = path.lstat()
    minimum = 0 if source else 1
    _require(
        stat.S_ISREG(before.st_mode) and not _linked(path) and minimum <= before.st_size <= maximum,
        "CORPUS_INVALID",
    )
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _require(_identity(before) == _identity(opened), "CORPUS_INVALID")
        raw = stream.read(maximum + 1)
        ended = os.fstat(stream.fileno())
    after = path.lstat()
    _require(
        minimum <= len(raw) <= maximum
        and len(raw) == before.st_size
        and _identity(before) == _identity(ended) == _identity(after)
        and before.st_ctime_ns == after.st_ctime_ns
        and opened.st_ctime_ns == ended.st_ctime_ns
        and stat.S_ISREG(after.st_mode)
        and not _linked(path),
        "CORPUS_INVALID",
    )
    return raw


def _sources(value: object, manifest: object) -> list[dict[str, str]]:
    _require(isinstance(value, list) and 1 <= len(value) <= 256, "CORPUS_INVALID")
    if not isinstance(value, list):
        raise AcceptanceFailure("CORPUS_INVALID")
    rows = []
    for supplied in value:
        row = safe_object(supplied, {"path", "sha256"})
        name, digest = row["path"], row["sha256"]
        _require(
            isinstance(name, str)
            and len(name) <= 256
            and (name in SOURCE_PATHS or APP_SOURCE.fullmatch(name) is not None)
            and isinstance(digest, str)
            and HASH.fullmatch(digest) is not None,
            "CORPUS_INVALID",
        )
        path = _path(ROOT / name, external=False)
        _require(
            hashlib.sha256(regular_bytes(path, MAX_SOURCE, source=True)).hexdigest() == digest,
            "CORPUS_INVALID",
        )
        rows.append({"path": name, "sha256": digest})
    expected = set(SOURCE_PATHS)
    expected.update(
        path.relative_to(ROOT).as_posix() for path in (ROOT / "backend/app").rglob("*.py")
    )
    names = [row["path"] for row in rows]
    _require(
        names == sorted(expected)
        and len(set(names)) == len(names)
        and isinstance(manifest, str)
        and HASH.fullmatch(manifest) is not None
        and manifest_sha256(rows) == manifest,
        "CORPUS_INVALID",
    )
    return rows


def _native(value: object) -> None:
    native = safe_object(value, NATIVE_FIELDS)
    numbers = {
        "starts": 6,
        "application_restarts": 4,
        "durable_restarts": 2,
        "storage_fault_restarts": 2,
        "session_ttl_minutes": 1,
    }
    _require(
        all(
            type(native[key]) is int and native[key] == expected
            for key, expected in numbers.items()
        ),
        "CORPUS_INVALID",
    )
    pids = native["owned_pids"]
    _require(
        isinstance(pids, list)
        and len(pids) == 6
        and all(type(pid) is int and 1 <= pid <= 2147483647 for pid in pids)
        and len(set(pids)) == 6
        and native["child_reaped"] is True
        and native["temporary_directory_removed"] is True
        and native["shutdown"] == "owned_terminate_and_reap",
        "CORPUS_INVALID",
    )
    elapsed = native["real_expiry_elapsed_seconds"]
    _require(
        type(elapsed) in (int, float) and math.isfinite(elapsed) and 59 <= elapsed <= 75,
        "CORPUS_INVALID",
    )


def _report(
    value: object, corpus: dict[str, Any], original: bytes, sha: str, tree: str
) -> list[dict[str, str]]:
    report = safe_object(value, REPORT_FIELDS)
    _require(
        report["schema_version"] == REPORT_SCHEMA
        and all(report[key] == expected for key, expected in SCOPE_FIELDS.items())
        and report["foundation_version"] == FOUNDATION_VERSION
        and report["success"] is True
        and report["mode"] == "owned_native_tcp"
        and report["tested_commit"] == sha
        and report["tested_tree"] == tree
        and report["working_tree_dirty"] is False
        and report["tracked_dirty"] is False
        and report["failures"] == []
        and report["required_checks"] == list(REQUIRED_CHECKS)
        and report["corpus_case_ids"] == list(CASE_IDS)
        and type(report["responses_checked"]) is int
        and len(CASE_IDS) <= report["responses_checked"] <= 100000
        and report["corpus_sha256"] == hashlib.sha256(original).hexdigest(),
        "CORPUS_INVALID",
    )
    checks = report["checks"]
    _require(isinstance(checks, list) and len(checks) == len(REQUIRED_CHECKS), "CORPUS_INVALID")
    for identifier, supplied in zip(REQUIRED_CHECKS, checks, strict=True):
        check = safe_object(supplied, {"id", "passed"})
        _require(check["id"] == identifier and check["passed"] is True, "CORPUS_INVALID")
    _native(report["native_process"])
    _require(
        isinstance(report["python_version"], str)
        and re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", report["python_version"])
        is not None
        and isinstance(report["limitations"], list)
        and 1 <= len(report["limitations"]) <= 16
        and all(
            isinstance(item, str) and 1 <= len(item) <= 4096 and not private(item)
            for item in report["limitations"]
        ),
        "CORPUS_INVALID",
    )
    rows = _sources(report["source_hashes"], report["source_manifest_sha256"])
    _require(
        rows == corpus["source_hashes"]
        and report["source_manifest_sha256"] == corpus["source_manifest_sha256"],
        "CORPUS_INVALID",
    )
    return rows


def validate_artifacts(*, report: Path, corpus: Path, tested_sha: str, tested_tree: str) -> None:
    """Validate the current successful report/corpus pair without execution."""
    try:
        _require(
            all(
                isinstance(value, str) and SHA_PATTERN.fullmatch(value) is not None
                for value in (tested_sha, tested_tree)
            ),
            "CORPUS_INVALID",
        )
        before = _revision(repository_snapshot(), tested_sha, tested_tree)
        paths = [_path(path, external=True) for path in (report, corpus)]
        _require(paths[0].resolve(strict=True) != paths[1].resolve(strict=True), "CORPUS_INVALID")
        raw_report, raw_corpus = (regular_bytes(path, MAX_ARTIFACT) for path in paths)
        captured = loads(raw_corpus)
        validate_corpus(captured)
        provenance = captured["provenance"]
        _require(
            provenance["command"] == COMMAND
            and provenance["tested_commit"] == tested_sha
            and provenance["tested_tree"] == tested_tree,
            "CORPUS_INVALID",
        )
        rows = _report(loads(raw_report), captured, raw_corpus, tested_sha, tested_tree)
        _require(
            _revision(repository_snapshot(), tested_sha, tested_tree) == before, "CORPUS_INVALID"
        )
        _sources(rows, captured["source_manifest_sha256"])
        _require(
            regular_bytes(paths[0], MAX_ARTIFACT) == raw_report
            and regular_bytes(paths[1], MAX_ARTIFACT) == raw_corpus
            and _revision(repository_snapshot(), tested_sha, tested_tree) == before,
            "CORPUS_INVALID",
        )
    except Exception:
        raise AcceptanceFailure("CORPUS_INVALID") from None


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AcceptanceFailure("CLI_ARGUMENTS_INVALID")


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description=__doc__, add_help=False, allow_abbrev=False)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--tested-tree", required=True)
    try:
        options = parser.parse_args(argv)
        validate_artifacts(
            report=options.report,
            corpus=options.corpus,
            tested_sha=options.tested_sha,
            tested_tree=options.tested_tree,
        )
    except Exception:
        print("S3 evidence: CORPUS_INVALID")
        return 1
    print("S3 evidence: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
