"""Neutral, byte-exact safety helpers for the two owned S2 acceptance drivers.

No child lifecycle, domain logic, credential or response logging lives here.
The existing S1 evidence writer remains an independent compatibility contract.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any, NoReturn

from verify_s1_application import AcceptanceFailure, _require

PRIVATE_KEYS = frozenset(
    {
        "user",
        "user_id",
        "owner",
        "owner_id",
        "alias",
        "session",
        "session_id",
        "token",
        "bearer",
        "digest",
        "db_path",
        "database",
        "headers",
        "path",
        "logs",
        "diagnostics",
        "nonce",
        "password",
        "secret",
        "authorization",
        "access_token",
        "cookie",
        "set-cookie",
        "expires_at",
    }
)


def private(value: object) -> bool:
    """Only body/request values are inspected; provenance paths are legitimate."""
    if isinstance(value, dict):
        return any(
            not isinstance(key, str) or key.lower() in PRIVATE_KEYS or private(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(private(child) for child in value)
    return isinstance(value, str) and ("Bearer " in value or "github_pat_" in value)


def reflects_private(value: object, forbidden: tuple[str, ...], *, depth: int = 0) -> bool:
    """Check decoded strings, not JSON spelling, without changing captured bytes."""
    _require(depth <= 32, "WIRE_INVALID")
    if isinstance(value, str):
        return any(secret in value for secret in forbidden)
    if isinstance(value, dict):
        return any(
            reflects_private(key, forbidden, depth=depth + 1)
            or reflects_private(child, forbidden, depth=depth + 1)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(reflects_private(child, forbidden, depth=depth + 1) for child in value)
    return False


def safe_object(value: object, fields: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or (fields is not None and set(value) != fields):
        raise AcceptanceFailure("WIRE_INVALID")
    return value


def loads(raw: bytes) -> dict[str, Any]:
    """Strict original UTF-8 JSON; no duplicate fields, NaN, or parser diagnostics."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError()
            result[key] = value
        return result

    def nonfinite(_: str) -> NoReturn:
        raise ValueError()

    try:
        return safe_object(
            json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AcceptanceFailure("WIRE_INVALID") from None


def json_bytes(value: object) -> bytes:
    """The sole S2 corpus serialization, also used for the actual file digest."""
    try:
        return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode(
            "utf-8"
        )
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AcceptanceFailure("OUTPUT_INVALID") from None


def write_new_json(path: Path, value: object) -> None:
    """Serialize before opening, then exclusively write exactly those bytes."""
    raw = json_bytes(value)
    try:
        with path.open("xb") as stream:
            stream.write(raw)
    except FileExistsError:
        raise AcceptanceFailure("OUTPUT_EXISTS") from None
    except OSError:
        raise AcceptanceFailure("OUTPUT_WRITE_FAILED") from None


def output_target(value: Path | None, root: Path) -> Path | None:
    if value is None:
        return None
    try:
        _require(not value.is_symlink() and not value.exists(), "OUTPUT_EXISTS")
        target = value.resolve()
        checkout = root.resolve()
        _require(
            target.parent.is_dir() and target != checkout and checkout not in target.parents,
            "OUTPUT_INVALID",
        )
        return target
    except OSError:
        raise AcceptanceFailure("OUTPUT_INVALID") from None


def manifest_sha256(items: list[dict[str, str]]) -> str:
    _require(isinstance(items, list) and bool(items), "PROVENANCE_INVALID")
    names: list[str] = []
    for item in items:
        _require(isinstance(item, dict) and set(item) == {"path", "sha256"}, "PROVENANCE_INVALID")
        name, digest = item["path"], item["sha256"]
        _require(
            isinstance(name, str)
            and bool(re.fullmatch(r"[A-Za-z0-9_./-]+", name))
            and not name.startswith("/")
            and all(part not in ("", ".", "..") for part in name.split("/"))
            and isinstance(digest, str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", digest)),
            "PROVENANCE_INVALID",
        )
        names.append(name)
    _require(len(names) == len(set(names)), "PROVENANCE_INVALID")
    raw = "".join(
        f"{item['path']} {item['sha256'].upper()}\n"
        for item in sorted(items, key=lambda item: item["path"])
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def runtime_hashes(root: Path, baseline: list[dict[str, str]]) -> list[dict[str, str]]:
    """Both reports bind the same actual bytes of their combined acceptance tools."""
    names = (
        "backend/local_s2_evidence.py",
        "backend/verify_s2_saved_risk.py",
        "backend/verify_s2_manual_portfolio.py",
        "ai/risk/contract.py",
        "ai/risk/scoring.py",
        "backend/data/questionnaire/risk_questionnaire_v1.json",
        "docs/features/local-application/S2-manual-portfolio-contract.md",
        "docs/features/local-application/S2-saved-risk-contract.md",
        "backend/tests/unit/test_local_s2_portfolio_native_harness.py",
        "backend/tests/unit/test_s2_saved_risk_corpus.py",
        "backend/tests/unit/test_local_s2_shared_evidence.py",
        "backend/tests/unit/test_local_s2_portfolio_expiry_risk.py",
        "backend/verify_s2_evidence_pair.py",
        "backend/tests/unit/test_s2_evidence_pair_validation.py",
    )
    try:
        items = baseline + [
            {"path": name, "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
            for name in names
        ]
        manifest_sha256(items)
        return sorted(items, key=lambda item: item["path"])
    except (OSError, ValueError):
        raise AcceptanceFailure("PROVENANCE_UNAVAILABLE") from None
