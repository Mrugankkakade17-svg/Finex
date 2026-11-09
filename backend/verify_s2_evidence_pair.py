"""Passive, fail-closed verification of the current two-domain S2 evidence pair.

Only bounded local files and read-only Git provenance are inspected. No API,
database, native child, output artifact or fixture fallback is created here.
Domain validators remain the authority for public DTO and financial semantics.
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

from local_s2_evidence import loads, manifest_sha256, private, safe_object
from verify_s1_application import CONTRACT_VERSION, ROOT, SCOPE, AcceptanceFailure, _git, _require
from verify_s2_manual_portfolio import (
    CASE_IDS as PORTFOLIO_CASES,
)
from verify_s2_manual_portfolio import (
    COMMAND as PORTFOLIO_COMMAND,
)
from verify_s2_manual_portfolio import (
    REQUIRED_CHECKS as PORTFOLIO_CHECKS,
)
from verify_s2_manual_portfolio import (
    validate_corpus as validate_portfolio_corpus,
)
from verify_s2_saved_risk import (
    CASE_IDS as RISK_CASES,
)
from verify_s2_saved_risk import (
    COMMAND as RISK_COMMAND,
)
from verify_s2_saved_risk import (
    REQUIRED_CHECKS as RISK_CHECKS,
)
from verify_s2_saved_risk import (
    validate_corpus as validate_risk_corpus,
)

MAX_ARTIFACT = 2097152
MAX_SOURCE = 2097152
SHA = re.compile(r"[0-9a-f]{40}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
REPORT_FIELDS = {
    "schema_version",
    "scope",
    "contract_version",
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
    "owned_pids",
    "child_reaped",
    "temporary_directory_removed",
    "session_ttl_minutes",
    "real_expiry_elapsed_seconds",
    "shutdown",
}
SOURCE_PATHS = frozenset(
    {
        "backend/local_s2_evidence.py",
        "backend/verify_s1_application.py",
        "backend/verify_s2_saved_risk.py",
        "backend/verify_s2_manual_portfolio.py",
        "backend/verify_s2_evidence_pair.py",
        "backend/tests/unit/test_s2_evidence_pair_validation.py",
        "backend/data/questionnaire/risk_questionnaire_v1.json",
        "ai/risk/contract.py",
        "ai/risk/scoring.py",
        "data/fixtures/local_s1/contract_cases.v1.json",
        "docs/features/local-application/S2-saved-risk-contract.md",
        "docs/features/local-application/S2-manual-portfolio-contract.md",
        "backend/tests/unit/test_local_s2_portfolio_native_harness.py",
        "backend/tests/unit/test_s2_saved_risk_corpus.py",
        "backend/tests/unit/test_local_s2_shared_evidence.py",
        "backend/tests/unit/test_local_s2_portfolio_expiry_risk.py",
    }
)


class PairFailure(AcceptanceFailure):
    """A new fixed passive-tool code without changing the frozen S1 allowlist."""

    def __init__(self) -> None:
        self.code = "PAIR_INVALID"
        Exception.__init__(self, self.code)


def _repository_snapshot() -> dict[str, object]:
    return {
        "tested_commit": _git(["rev-parse", "HEAD"]),
        "tested_tree": _git(["rev-parse", "HEAD^{tree}"]),
        "working_tree_dirty": bool(_git(["status", "--porcelain", "--untracked-files=normal"])),
        "tracked_dirty": bool(_git(["diff", "--name-only", "HEAD", "--"])),
    }


def _revision(snapshot: object, tested_sha: str, tested_tree: str) -> dict[str, Any]:
    value = safe_object(
        snapshot, {"tested_commit", "tested_tree", "working_tree_dirty", "tracked_dirty"}
    )
    _require(
        value["tested_commit"] == tested_sha
        and value["tested_tree"] == tested_tree
        and value["working_tree_dirty"] is False
        and value["tracked_dirty"] is False,
        "PAIR_INVALID",
    )
    return value


def _linked(path: Path) -> bool:
    information = path.lstat()
    return stat.S_ISLNK(information.st_mode) or bool(
        getattr(information, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _identity(information: os.stat_result) -> tuple[int, int, int, int]:
    return (
        information.st_dev,
        information.st_ino,
        information.st_size,
        information.st_mtime_ns,
    )


def _regular_bytes(path: Path, maximum: int, *, source: bool = False) -> bytes:
    minimum = 0 if source else 1
    before = path.lstat()
    _require(
        stat.S_ISREG(before.st_mode) and not _linked(path) and minimum <= before.st_size <= maximum,
        "PAIR_INVALID",
    )
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        _require(_identity(opened) == _identity(before), "PAIR_INVALID")
        raw = stream.read(maximum + 1)
        final = os.fstat(stream.fileno())
    after = path.lstat()
    _require(
        minimum <= len(raw) <= maximum
        and len(raw) == before.st_size
        and _identity(before) == _identity(final) == _identity(after)
        # Windows path-stat and descriptor-stat expose ctime differently.
        # Compare each representation to itself across the bounded read.
        and before.st_ctime_ns == after.st_ctime_ns
        and opened.st_ctime_ns == final.st_ctime_ns
        and stat.S_ISREG(after.st_mode)
        and not _linked(path),
        "PAIR_INVALID",
    )
    return raw


def _path(value: object, *, external: bool) -> Path:
    if not isinstance(value, Path):
        raise PairFailure()
    spelling = str(value)
    _require(
        0 < len(spelling) <= 4096
        and "\x00" not in spelling
        and not spelling.startswith(("\\\\", "//")),
        "PAIR_INVALID",
    )
    path = value.absolute()
    for parent in (path, *path.parents):
        _require(not _linked(parent), "PAIR_INVALID")
    resolved = path.resolve(strict=True)
    root = ROOT.resolve(strict=True)
    if external:
        _require(resolved != root and root not in resolved.parents, "PAIR_INVALID")
    else:
        _require(root in resolved.parents, "PAIR_INVALID")
    return path


def _sources(value: object, manifest: object, domain: str) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise PairFailure()
    _require(1 <= len(value) <= 256, "PAIR_INVALID")
    rows: list[dict[str, str]] = []
    for item in value:
        row = safe_object(item, {"path", "sha256"})
        name, digest = row["path"], row["sha256"]
        _require(
            isinstance(name, str)
            and len(name) <= 256
            and (
                name in SOURCE_PATHS
                or bool(re.fullmatch(r"backend/app/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py", name))
            )
            and all(part not in ("", ".", "..") for part in name.split("/"))
            and isinstance(digest, str)
            and bool(HASH.fullmatch(digest)),
            "PAIR_INVALID",
        )
        source = _path(ROOT / name, external=False)
        actual = hashlib.sha256(_regular_bytes(source, MAX_SOURCE, source=True)).hexdigest()
        _require(actual == digest, "PAIR_INVALID")
        rows.append({"path": name, "sha256": digest})
    names = [row["path"] for row in rows]
    required = {
        "backend/local_s2_evidence.py",
        "backend/verify_s2_evidence_pair.py",
        "backend/tests/unit/test_s2_evidence_pair_validation.py",
        "backend/verify_s2_" + ("saved_risk" if domain == "risk" else "manual_portfolio") + ".py",
    }
    _require(
        names == sorted(names) and len(set(names)) == len(names) and required <= set(names),
        "PAIR_INVALID",
    )
    _require(
        isinstance(manifest, str)
        and HASH.fullmatch(manifest) is not None
        and manifest_sha256(rows) == manifest,
        "PAIR_INVALID",
    )
    return rows


def _safe_text(value: object, maximum: int = 4096) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum
        and not private(value)
        and not re.search(r"(?:[A-Za-z]:[\\/]|file://|/(?:Users|home|tmp|var)/)", value)
        and not re.search(r"(?:^|[^A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?:$|[^A-Za-z0-9_-])", value)
    )


def _native(value: object, domain: str) -> None:
    native = safe_object(value, NATIVE_FIELDS)
    starts = 4 if domain == "risk" else 5
    pids = native["owned_pids"]
    _require(
        type(native["starts"]) is int
        and native["starts"] == starts
        and type(native["application_restarts"]) is int
        and native["application_restarts"] == 2
        and isinstance(pids, list)
        and len(pids) == starts
        and all(type(pid) is int and 1 <= pid <= 2147483647 for pid in pids)
        and len(set(pids)) == len(pids)
        and native["child_reaped"] is True
        and native["temporary_directory_removed"] is True
        and type(native["session_ttl_minutes"]) is int
        and native["session_ttl_minutes"] == 1
        and native["shutdown"] == "owned_terminate_and_reap",
        "PAIR_INVALID",
    )
    elapsed = native["real_expiry_elapsed_seconds"]
    _require(
        elapsed is None
        if domain == "risk"
        else (type(elapsed) in (int, float) and math.isfinite(elapsed) and 59 <= elapsed <= 75),
        "PAIR_INVALID",
    )


def _report(
    report: object,
    corpus: dict[str, Any],
    raw: bytes,
    domain: str,
    tested_sha: str,
    tested_tree: str,
) -> list[dict[str, str]]:
    value = safe_object(report, REPORT_FIELDS)
    cases = RISK_CASES if domain == "risk" else PORTFOLIO_CASES
    checks = RISK_CHECKS if domain == "risk" else PORTFOLIO_CHECKS
    schema = (
        "finex.local_s2."
        + ("saved_risk" if domain == "risk" else "manual_portfolio")
        + ".acceptance.v1"
    )
    _require(
        value["schema_version"] == schema
        and value["scope"] == SCOPE
        and value["contract_version"] == CONTRACT_VERSION
        and value["success"] is True
        and value["mode"] == "owned_native_tcp"
        and value["tested_commit"] == tested_sha
        and value["tested_tree"] == tested_tree
        and value["working_tree_dirty"] is False
        and value["tracked_dirty"] is False
        and value["failures"] == []
        and type(value["responses_checked"]) is int
        and len(cases) <= value["responses_checked"] <= 100000
        and value["required_checks"] == list(checks)
        and value["corpus_case_ids"] == list(cases)
        and isinstance(value["corpus_sha256"], str)
        and HASH.fullmatch(value["corpus_sha256"]) is not None
        and value["corpus_sha256"] == hashlib.sha256(raw).hexdigest()
        and isinstance(value["python_version"], str)
        and re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", value["python_version"]) is not None
        and isinstance(value["limitations"], list)
        and 1 <= len(value["limitations"]) <= 16
        and all(_safe_text(text) for text in value["limitations"]),
        "PAIR_INVALID",
    )
    recorded_checks = value["checks"]
    _require(
        isinstance(recorded_checks, list) and len(recorded_checks) == len(checks), "PAIR_INVALID"
    )
    for identifier, item in zip(checks, recorded_checks, strict=True):
        check = safe_object(item, {"id", "passed"})
        _require(check["id"] == identifier and check["passed"] is True, "PAIR_INVALID")
    _native(value["native_process"], domain)
    rows = _sources(value["source_hashes"], value["source_manifest_sha256"], domain)
    _require(
        rows == corpus["source_hashes"]
        and value["source_manifest_sha256"] == corpus["source_manifest_sha256"],
        "PAIR_INVALID",
    )
    return rows


def validate_pair(
    *,
    risk_report: Path,
    risk_corpus: Path,
    portfolio_report: Path,
    portfolio_corpus: Path,
    tested_sha: str,
    tested_tree: str,
) -> None:
    """Validate both independently bound current reports, then repeat provenance."""
    try:
        _require(
            all(
                isinstance(item, str) and SHA.fullmatch(item) is not None
                for item in (tested_sha, tested_tree)
            ),
            "PAIR_INVALID",
        )
        before = _revision(_repository_snapshot(), tested_sha, tested_tree)
        paths = [
            _path(path, external=True)
            for path in (risk_report, risk_corpus, portfolio_report, portfolio_corpus)
        ]
        _require(len({path.resolve(strict=True) for path in paths}) == 4, "PAIR_INVALID")
        captured = [_regular_bytes(path, MAX_ARTIFACT) for path in paths]
        inventories: list[tuple[str, list[dict[str, str]], str]] = []
        for domain, report_index, corpus_index, validator, command, case_ids in (
            ("risk", 0, 1, validate_risk_corpus, RISK_COMMAND, RISK_CASES),
            ("portfolio", 2, 3, validate_portfolio_corpus, PORTFOLIO_COMMAND, PORTFOLIO_CASES),
        ):
            corpus = loads(captured[corpus_index])
            validator(corpus)
            provenance = corpus["provenance"]
            _require(
                provenance["tested_commit"] == tested_sha
                and provenance["tested_tree"] == tested_tree
                and provenance["command"] == command
                and [item["id"] for item in corpus["cases"]] == list(case_ids),
                "PAIR_INVALID",
            )
            _sources(corpus["source_hashes"], corpus["source_manifest_sha256"], domain)
            rows = _report(
                loads(captured[report_index]),
                corpus,
                captured[corpus_index],
                domain,
                tested_sha,
                tested_tree,
            )
            inventories.append((domain, rows, corpus["source_manifest_sha256"]))
        _require(
            before == _revision(_repository_snapshot(), tested_sha, tested_tree), "PAIR_INVALID"
        )
        for domain, rows, manifest in inventories:
            _sources(rows, manifest, domain)
        _require(
            all(
                _regular_bytes(path, MAX_ARTIFACT) == original
                for path, original in zip(paths, captured, strict=True)
            ),
            "PAIR_INVALID",
        )
    except Exception:
        raise PairFailure() from None


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise PairFailure()


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description=__doc__, add_help=False, allow_abbrev=False)
    for option in ("risk-report", "risk-corpus", "portfolio-report", "portfolio-corpus"):
        parser.add_argument("--" + option, type=Path, required=True)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--tested-tree", required=True)
    try:
        options = parser.parse_args(argv)
        validate_pair(
            risk_report=options.risk_report,
            risk_corpus=options.risk_corpus,
            portfolio_report=options.portfolio_report,
            portfolio_corpus=options.portfolio_corpus,
            tested_sha=options.tested_sha,
            tested_tree=options.tested_tree,
        )
    except Exception:
        print("S2 evidence pair: FAIL")
        return 1
    print("S2 evidence pair: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
