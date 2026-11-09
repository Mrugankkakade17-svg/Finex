"""Fail-closed owned-process acceptance for the opted-in synthetic local S1 API.

No external server, developer database, shortened clock, provider, or session
credential can be supplied. The only persisted wire artifacts are safe responses
from two synthetic personas; login responses and child diagnostics stay private.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import queue
import re
import secrets
import shutil
import socket
import sqlite3
import subprocess
import sys
import sysconfig
import tempfile
import threading
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, NoReturn, cast

import httpx

ROOT = Path(__file__).resolve().parent.parent
CORPUS_SCHEMA = "finex.local_s1.corpus.v1"
SCOPE = "local_educational_application"
CONTRACT_VERSION = "local.v1"
COMMAND = "python verify_s1_application.py"
HANDSHAKE_KIND = "finex.local_s1.child.v1"
MAX_BODY = 32768
MAX_DIAGNOSTICS = 131072
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
CID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z", re.ASCII)
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}\Z", re.ASCII)
UTC_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z", re.ASCII
)
CASE_IDS = (
    "initial",
    "me",
    "partial_draft",
    "saved_profile",
    "consent_accepted",
    "completed",
    "repeated_complete",
    "identical_draft",
    "changed_profile",
    "withdrawn",
    "reaccepted",
    "logged_out",
    "session_invalid",
    "consent_required",
    "profile_incomplete",
    "validation_error",
    "consent_version_mismatch",
    "profile_version_mismatch",
)
ERROR_CASES = {
    "session_invalid": ("state", 401, "SESSION_INVALID"),
    "consent_required": ("complete", 409, "CONSENT_REQUIRED"),
    "profile_incomplete": ("complete", 409, "PROFILE_INCOMPLETE"),
    "validation_error": ("draft", 422, "VALIDATION_ERROR"),
    "consent_version_mismatch": ("consent", 409, "CONSENT_VERSION_MISMATCH"),
    "profile_version_mismatch": ("draft", 409, "PROFILE_VERSION_MISMATCH"),
}
SUCCESS_OPERATIONS = {
    "initial": "state",
    "me": "me",
    "partial_draft": "draft",
    "saved_profile": "draft",
    "consent_accepted": "consent",
    "completed": "complete",
    "repeated_complete": "complete",
    "identical_draft": "draft",
    "changed_profile": "draft",
    "withdrawn": "consent",
    "reaccepted": "consent",
    "logged_out": "logout",
}
ROUTES = {
    "state": ("GET", "/api/v1/local-onboarding/state"),
    "draft": ("PUT", "/api/v1/local-onboarding/draft"),
    "consent": ("POST", "/api/v1/local-onboarding/consent"),
    "complete": ("POST", "/api/v1/local-onboarding/complete"),
    "me": ("GET", "/api/v1/local-auth/me"),
    "logout": ("POST", "/api/v1/local-auth/logout"),
}
COMPLETE_REQUEST = {"consent_version": "consent.v1", "profile_schema_version": "profile.v1"}
CONSENT_REQUEST = {"consent_version": "consent.v1", "consent_given": True}
PARTIAL_REQUEST = {
    "profile_schema_version": "profile.v1",
    "display_name": None,
    "experience_level": "beginner",
}
PROFILE_REQUEST = {**PARTIAL_REQUEST, "display_name": "Synthetic learner A"}
CHANGED_REQUEST = {
    **PROFILE_REQUEST,
    "display_name": "Synthetic learner A revised",
    "experience_level": "advanced",
}
REQUIRED_CHECKS = (
    "disabled_prebody_no_database",
    "remote_configuration_no_database",
    "owned_child_handshakes",
    "two_persona_ownership",
    "query_not_authentication",
    "header_query_not_owner",
    "extra_owner_rejected_unchanged",
    "partial_draft",
    "prerequisite_rejections_unchanged",
    "version_rejections_unchanged",
    "malformed_validation_unchanged",
    "first_process_restart",
    "persisted_partial_and_sessions",
    "explicit_completion",
    "repeat_and_identical_preserve_time",
    "profile_change_invalidates",
    "withdrawal_and_reacceptance_gate",
    "durable_per_session_logout",
    "second_process_restart",
    "persisted_data_and_revocation",
    "real_one_minute_expiry",
    "digest_only_storage_no_reflection",
    "complete_wire_corpus",
    "owned_cleanup",
)
SAFE_FAILURE_CODES = frozenset(
    {
        "NOT_IMPLEMENTED",
        "CORPUS_INVALID",
        "HANDSHAKE_INVALID",
        "CONFIGURATION_INVALID",
        "PROVENANCE_INVALID",
        "PROVENANCE_MISMATCH",
        "PROVENANCE_UNAVAILABLE",
        "SOURCE_CHANGED",
        "SOCKET_BIND_FAILED",
        "CHILD_START_FAILED",
        "CHILD_START_TIMEOUT",
        "CHILD_CLEANUP_FAILED",
        "DIAGNOSTICS_UNSAFE",
        "TEMPORARY_DIRECTORY_UNSAFE",
        "TEMPORARY_CLEANUP_FAILED",
        "PROBE_FAILED",
        "WIRE_INVALID",
        "TOKEN_REFLECTION",
        "TTL_FAILED",
        "OUTPUT_EXISTS",
        "OUTPUT_INVALID",
        "OUTPUT_WRITE_FAILED",
        "CLI_ARGUMENTS_INVALID",
        "INTERNAL_FAILURE",
    }
)


class AcceptanceFailure(Exception):
    """Only a fixed diagnostic code, never a response, credential or OS error."""

    def __init__(self, code: str) -> None:
        self.code = code if code in SAFE_FAILURE_CODES else "INTERNAL_FAILURE"
        super().__init__(self.code)


def _require(condition: bool, code: str = "PROBE_FAILED") -> None:
    if not condition:
        raise AcceptanceFailure(code)


def _object(value: object) -> dict[str, Any]:
    _require(isinstance(value, dict), "CORPUS_INVALID")
    return cast(dict[str, Any], value)


def _utc(value: object) -> datetime:
    _require(isinstance(value, str) and bool(UTC_PATTERN.fullmatch(value)), "CORPUS_INVALID")
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        raise AcceptanceFailure("CORPUS_INVALID") from None
    _require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0), "CORPUS_INVALID")
    return parsed


def _forbidden_keys(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            not isinstance(key, str)
            or key.lower()
            in {"access_token", "authorization", "cookie", "set-cookie", "expires_at"}
            or _forbidden_keys(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_forbidden_keys(child) for child in value)
    return False


def _validate_state(data: dict[str, Any]) -> None:
    _require(
        data.get("scope") == SCOPE and data.get("contract_version") == CONTRACT_VERSION,
        "CORPUS_INVALID",
    )
    _require(
        data.get("profile_schema_version") == "profile.v1"
        and data.get("consent_version") == "consent.v1",
        "CORPUS_INVALID",
    )
    _require(
        {"consent", "draft", "onboarding_completed", "completed_at"} <= data.keys(),
        "CORPUS_INVALID",
    )
    draft = _object(data["draft"])
    _require({"display_name", "experience_level", "updated_at"} <= draft.keys(), "CORPUS_INVALID")
    label = draft["display_name"]
    _require(
        label is None or (isinstance(label, str) and len(label) <= 80 and label == label.strip()),
        "CORPUS_INVALID",
    )
    _require(
        draft["experience_level"] in (None, "beginner", "intermediate", "advanced"),
        "CORPUS_INVALID",
    )
    if draft["updated_at"] is not None:
        _utc(draft["updated_at"])
    _require(
        not (label is not None or draft["experience_level"] is not None)
        or draft["updated_at"] is not None,
        "CORPUS_INVALID",
    )
    consent = data["consent"]
    if consent is not None:
        decision = _object(consent)
        _require(
            type(decision.get("accepted")) is bool and decision.get("version") == "consent.v1",
            "CORPUS_INVALID",
        )
        _utc(decision.get("recorded_at"))
    _require(type(data["onboarding_completed"]) is bool, "CORPUS_INVALID")
    if data["onboarding_completed"]:
        _utc(data["completed_at"])
        _require(
            bool(label)
            and draft["experience_level"] is not None
            and draft["updated_at"] is not None
            and isinstance(consent, dict)
            and consent.get("accepted") is True,
            "CORPUS_INVALID",
        )
    else:
        _require(data["completed_at"] is None, "CORPUS_INVALID")


def validate_corpus(document: object, *, native_required: bool = False) -> list[dict[str, Any]]:
    """Validate the complete safe byte corpus, never falling back to a fixture."""
    doc = _object(document)
    _require(
        set(doc) == {"schema_version", "scope", "contract_version", "provenance", "cases"},
        "CORPUS_INVALID",
    )
    _require(
        doc["schema_version"] == CORPUS_SCHEMA
        and doc["scope"] == SCOPE
        and doc["contract_version"] == CONTRACT_VERSION
        and not _forbidden_keys(doc),
        "CORPUS_INVALID",
    )
    provenance = _object(doc["provenance"])
    native = provenance.get("kind") == "native_tcp_capture"
    if native:
        _require(
            set(provenance) == {"kind", "source", "command", "tested_commit", "tested_tree"}
            and provenance.get("source") == "owned_loopback_uvicorn"
            and provenance.get("command") == COMMAND,
            "CORPUS_INVALID",
        )
        for key in ("tested_commit", "tested_tree"):
            value = provenance.get(key)
            _require(
                isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value)), "CORPUS_INVALID"
            )
    else:
        _require(
            not native_required
            and provenance
            == {
                "kind": "synthetic_fixture",
                "source": "handcrafted",
                "command": "handcrafted local S1 contract fixture",
            },
            "CORPUS_INVALID",
        )
    _require(
        isinstance(doc["cases"], list) and len(doc["cases"]) == len(CASE_IDS), "CORPUS_INVALID"
    )
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    decoded: dict[str, dict[str, Any]] = {}
    for raw_case in doc["cases"]:
        case = _object(raw_case)
        _require(
            set(case)
            == {"id", "operation", "request", "status", "content_type", "body_utf8", "expected"},
            "CORPUS_INVALID",
        )
        identifier = case["id"]
        _require(
            isinstance(identifier, str) and identifier in CASE_IDS and identifier not in seen,
            "CORPUS_INVALID",
        )
        seen.add(identifier)
        expected = _object(case["expected"])
        if identifier in ERROR_CASES:
            operation, status, code = ERROR_CASES[identifier]
            _require(expected == {"outcome": "error", "error_code": code}, "CORPUS_INVALID")
        else:
            operation, status = SUCCESS_OPERATIONS[identifier], 200
            _require(expected == {"outcome": "success"}, "CORPUS_INVALID")
        _require(
            case["operation"] == operation
            and type(case["status"]) is int
            and case["status"] == status
            and case["content_type"] == "application/json",
            "CORPUS_INVALID",
        )
        payload = case["request"]
        if operation in {"state", "me", "logout"}:
            _require(payload is None, "CORPUS_INVALID")
        else:
            request = _object(payload)
            keys = {
                "draft": {"profile_schema_version", "display_name", "experience_level"},
                "consent": {"consent_version", "consent_given"},
                "complete": {"consent_version", "profile_schema_version"},
            }[operation]
            if identifier == "validation_error":
                keys = keys | {"owner_id"}
            _require(set(request) == keys, "CORPUS_INVALID")
            for version in keys & {"consent_version", "profile_schema_version"}:
                _require(
                    isinstance(request[version], str) and len(request[version]) <= 64,
                    "CORPUS_INVALID",
                )
                supported = "consent.v1" if version == "consent_version" else "profile.v1"
                mismatch = (
                    identifier == "consent_version_mismatch" and version == "consent_version"
                ) or (
                    identifier == "profile_version_mismatch" and version == "profile_schema_version"
                )
                _require(
                    request[version] != supported if mismatch else request[version] == supported,
                    "CORPUS_INVALID",
                )
            if operation == "draft":
                _require(
                    request["display_name"] is None
                    or (
                        isinstance(request["display_name"], str)
                        and len(request["display_name"]) <= 80
                    ),
                    "CORPUS_INVALID",
                )
                _require(
                    request["experience_level"] in (None, "beginner", "intermediate", "advanced"),
                    "CORPUS_INVALID",
                )
            if operation == "consent":
                _require(type(request["consent_given"]) is bool, "CORPUS_INVALID")
            if identifier == "validation_error":
                _require(
                    isinstance(request["owner_id"], str) and 0 < len(request["owner_id"]) <= 128,
                    "CORPUS_INVALID",
                )
        raw = case["body_utf8"]
        _require(isinstance(raw, str) and len(raw.encode("utf-8")) <= MAX_BODY, "CORPUS_INVALID")
        try:
            envelope = _object(json.loads(raw))
        except (ValueError, TypeError, UnicodeError):
            raise AcceptanceFailure("CORPUS_INVALID") from None
        _require(not _forbidden_keys(envelope), "CORPUS_INVALID")
        _require(isinstance(envelope.get("message"), str), "CORPUS_INVALID")
        if status == 200:
            _require(envelope.get("success") is True, "CORPUS_INVALID")
            metadata = _object(envelope.get("meta"))
            _require(
                metadata.get("apiVersion") == "v1"
                and metadata.get("dataStatus") == "CACHED"
                and "dataAsOf" in metadata
                and metadata["dataAsOf"] is None
                and isinstance(metadata.get("correlationId"), str)
                and bool(CID_PATTERN.fullmatch(metadata["correlationId"])),
                "CORPUS_INVALID",
            )
            data = _object(envelope.get("data"))
            decoded[identifier] = data
            _require(
                data.get("scope") == SCOPE and data.get("contract_version") == CONTRACT_VERSION,
                "CORPUS_INVALID",
            )
            if operation == "me":
                user = _object(data.get("user"))
                _require(
                    user.get("alias") == "learner-a"
                    and isinstance(user.get("id"), str)
                    and 0 < len(user["id"]) <= 128,
                    "CORPUS_INVALID",
                )
            elif operation == "logout":
                _require(data.get("signed_out") is True, "CORPUS_INVALID")
            else:
                _validate_state(data)
                if operation == "draft":
                    _require(
                        data["draft"]["updated_at"] is not None
                        and data["draft"]["display_name"] == payload["display_name"]
                        and data["draft"]["experience_level"] == payload["experience_level"],
                        "CORPUS_INVALID",
                    )
                if operation == "consent":
                    _require(
                        isinstance(data["consent"], dict)
                        and data["consent"]["accepted"] == payload["consent_given"],
                        "CORPUS_INVALID",
                    )
                if operation == "complete":
                    _require(data["onboarding_completed"] is True, "CORPUS_INVALID")
        else:
            _require(
                envelope.get("success") is False
                and envelope.get("error_code") == code
                and "data" not in envelope,
                "CORPUS_INVALID",
            )
            error = _object(envelope.get("error"))
            _require(
                error.get("code") == code
                and isinstance(error.get("message"), str)
                and isinstance(error.get("fieldErrors"), list)
                and isinstance(error.get("correlationId"), str)
                and bool(CID_PATTERN.fullmatch(error["correlationId"])),
                "CORPUS_INVALID",
            )
        cases.append(case)
    _require(seen == set(CASE_IDS), "CORPUS_INVALID")
    initial = decoded["initial"]
    _require(
        initial["draft"] == {"display_name": None, "experience_level": None, "updated_at": None}
        and initial["consent"] is None
        and initial["onboarding_completed"] is False,
        "CORPUS_INVALID",
    )
    partial = decoded["partial_draft"]
    _require(
        partial["onboarding_completed"] is False
        and (
            partial["draft"]["display_name"] is None or partial["draft"]["experience_level"] is None
        ),
        "CORPUS_INVALID",
    )
    for identifier in (
        "saved_profile",
        "consent_accepted",
        "changed_profile",
        "withdrawn",
        "reaccepted",
    ):
        _require(
            decoded[identifier]["onboarding_completed"] is False
            and decoded[identifier]["completed_at"] is None,
            "CORPUS_INVALID",
        )
    _require(
        decoded["completed"] == decoded["repeated_complete"] == decoded["identical_draft"],
        "CORPUS_INVALID",
    )
    _require(decoded["changed_profile"]["draft"] != decoded["completed"]["draft"], "CORPUS_INVALID")
    return cases


def validate_handshake(raw: bytes, *, expected_pid: int, expected_nonce: str) -> int:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError):
        raise AcceptanceFailure("HANDSHAKE_INVALID") from None
    _require(
        isinstance(value, dict) and set(value) == {"kind", "pid", "port", "nonce"},
        "HANDSHAKE_INVALID",
    )
    _require(
        value["kind"] == HANDSHAKE_KIND
        and type(value["pid"]) is int
        and value["pid"] == expected_pid
        and value["nonce"] == expected_nonce
        and type(value["port"]) is int
        and 1 <= value["port"] <= 65535,
        "HANDSHAKE_INVALID",
    )
    return int(value["port"])


def child_environment(database: Path, *, mode: str = "enabled") -> dict[str, str]:
    _require(mode in {"enabled", "disabled", "remote"}, "CONFIGURATION_INVALID")
    # Do not pass Git credentials, provider settings, proxy variables, dotenv
    # choices, browser cookies, or a developer database to the native child.
    env = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "LOCALAPPDATA"}
    }
    env.update(
        {
            "PYTHONPATH": os.pathsep.join(
                (str(ROOT / "backend"), str(ROOT), sysconfig.get_path("purelib"))
            ),
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONWARNINGS": "ignore::DeprecationWarning",
            "APP_ENV": "local",
            "DEBUG": "false",
            "HOST": "0.0.0.0" if mode == "remote" else "127.0.0.1",
            "PORT": "0",
            "APP_NAME": "FinEx Backend",
            "APP_VERSION": "0.1.0",
            "LOCAL_APP_ENABLED": "false" if mode == "disabled" else "true",
            "LOCAL_DB_PATH": str(database),
            "LOCAL_SESSION_TTL_MINUTES": "1",
            "API_BASE_URL": "http://127.0.0.1:8000",
            "ALLOWED_ORIGINS": '["http://127.0.0.1:3000"]',
            "ALLOW_CREDENTIALS": "false",
            "LLM_PROVIDER": "none",
            "OPENAI_API_KEY": "",
            "MARKET_DATA_PROVIDER": "mock",
            "MARKET_DATA_API_KEY": "",
            "DATABRICKS_HOST": "",
            "DATABRICKS_TOKEN": "",
            "DATABRICKS_WAREHOUSE_ID": "",
            "SECRET_KEY": "",
            "FIXTURE_MODE": "s2_dat_01",
            "LOG_LEVEL": "CRITICAL",
        }
    )
    return env


def _git(arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *arguments], capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        raise AcceptanceFailure("PROVENANCE_UNAVAILABLE") from None
    _require(result.returncode == 0, "PROVENANCE_UNAVAILABLE")
    try:
        return result.stdout.decode("utf-8").strip()
    except UnicodeError:
        raise AcceptanceFailure("PROVENANCE_UNAVAILABLE") from None


def source_hashes() -> list[dict[str, str]]:
    paths = list((ROOT / "backend/app").rglob("*.py")) + [
        Path(__file__).resolve(),
        ROOT / "data/fixtures/local_s1/contract_cases.v1.json",
    ]
    try:
        return [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix())
        ]
    except (OSError, ValueError):
        raise AcceptanceFailure("PROVENANCE_UNAVAILABLE") from None


def repository_provenance(tested_sha: str | None, tested_tree: str | None) -> dict[str, Any]:
    for supplied in (tested_sha, tested_tree):
        _require(
            supplied is None
            or (isinstance(supplied, str) and bool(SHA_PATTERN.fullmatch(supplied))),
            "PROVENANCE_INVALID",
        )
    actual_sha, actual_tree = _git(["rev-parse", "HEAD"]), _git(["rev-parse", "HEAD^{tree}"])
    _require(
        bool(SHA_PATTERN.fullmatch(actual_sha)) and bool(SHA_PATTERN.fullmatch(actual_tree)),
        "PROVENANCE_UNAVAILABLE",
    )
    _require(
        (tested_sha is None or tested_sha == actual_sha)
        and (tested_tree is None or tested_tree == actual_tree),
        "PROVENANCE_MISMATCH",
    )
    return {
        "tested_commit": actual_sha,
        "tested_tree": actual_tree,
        "working_tree_dirty": bool(_git(["status", "--porcelain", "--untracked-files=normal"])),
        "tracked_dirty": bool(_git(["diff", "--name-only", "HEAD", "--"])),
        "source_hashes": source_hashes(),
    }


def allocate_loopback_socket() -> tuple[socket.socket, int]:
    """The child binds port zero itself; there is no reserve/close/rebind race."""
    sock: socket.socket | None = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        return sock, int(sock.getsockname()[1])
    except OSError:
        if sock is not None:
            sock.close()
        raise AcceptanceFailure("SOCKET_BIND_FAILED") from None


class _PipeCapture:
    def __init__(self, stream: BinaryIO, *, handshake: bool = False) -> None:
        self.stream = stream
        self.first: queue.Queue[bytes] = queue.Queue(maxsize=1)
        self.data = bytearray()
        self.overflow = False
        self.handshake = handshake
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        first = True
        try:
            while True:
                chunk = self.stream.readline(MAX_DIAGNOSTICS + 1)
                if not chunk:
                    break
                if len(self.data) + len(chunk) > MAX_DIAGNOSTICS:
                    self.overflow = True
                else:
                    self.data.extend(chunk)
                if first and self.handshake:
                    self.first.put_nowait(chunk)
                first = False
        except (OSError, ValueError):
            self.overflow = True


class OwnedServer:
    """Only this Popen child may be stopped, and only its handshake port used."""

    def __init__(
        self, database: Path, *, mode: str = "enabled", startup_timeout: float = 20
    ) -> None:
        self.database = database
        self.mode = mode
        self.startup_timeout = startup_timeout
        self.process: subprocess.Popen[bytes] | None = None
        self.stdout: _PipeCapture | None = None
        self.stderr: _PipeCapture | None = None
        self.client: httpx.Client | None = None
        self.port: int | None = None
        self.reaped = False

    def start(self, *, expect_configuration_failure: bool = False) -> None:
        nonce = secrets.token_hex(32)
        # Windows virtualenv python.exe can be a redirector with a different PID.
        # Spawn the actual interpreter, with only the existing venv packages on
        # explicit PYTHONPATH, so Popen.pid must equal the actual server PID.
        interpreter = getattr(sys, "_base_executable", sys.executable)
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NO_WINDOW
        try:
            self.process = subprocess.Popen(
                [interpreter, "-u", str(Path(__file__).resolve()), "--owned-child"],
                cwd=ROOT / "backend",
                env=child_environment(self.database, mode=self.mode),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )
            stdin, stdout, stderr = self.process.stdin, self.process.stdout, self.process.stderr
            if stdin is None or stdout is None or stderr is None:
                raise AcceptanceFailure("CHILD_START_FAILED")
            self.stdout = _PipeCapture(cast(BinaryIO, stdout), handshake=True)
            self.stderr = _PipeCapture(cast(BinaryIO, stderr))
            control = {
                "database": str(self.database),
                "nonce": nonce,
                "parent_pid": os.getpid(),
                "mode": self.mode,
            }
            stdin.write((json.dumps(control) + "\n").encode("utf-8"))
            stdin.close()
            try:
                raw = self.stdout.first.get(timeout=self.startup_timeout)
            except queue.Empty:
                code = (
                    "CHILD_START_FAILED"
                    if self.process.poll() is not None
                    else "CHILD_START_TIMEOUT"
                )
                raise AcceptanceFailure(code) from None
            self.port = validate_handshake(raw, expected_pid=self.process.pid, expected_nonce=nonce)
            if expect_configuration_failure:
                try:
                    result = self.process.wait(timeout=self.startup_timeout)
                except subprocess.TimeoutExpired:
                    raise AcceptanceFailure("CHILD_START_TIMEOUT") from None
                _require(result == 2 and not self.database.exists(), "PROBE_FAILED")
                return
            self.client = httpx.Client(
                base_url=f"http://127.0.0.1:{self.port}",
                trust_env=False,
                follow_redirects=False,
                timeout=httpx.Timeout(2),
                headers={"X-Correlation-ID": "s1-native-acceptance"},
            )
            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                _require(self.process.poll() is None, "CHILD_START_FAILED")
                try:
                    response = self.client.get("/api/v1/health")
                    body = response.json()
                    if (
                        response.status_code == 200
                        and body.get("data", {}).get("status") == "healthy"
                    ):
                        _require(body["data"]["environment"] == "local", "CONFIGURATION_INVALID")
                        return
                except (httpx.HTTPError, ValueError, TypeError):
                    pass
                time.sleep(0.05)
            raise AcceptanceFailure("CHILD_START_TIMEOUT")
        except AcceptanceFailure:
            self.stop()
            raise
        except Exception:
            self.stop()
            raise AcceptanceFailure("CHILD_START_FAILED") from None

    def stop(self) -> None:
        failure: str | None = None
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                failure = "CHILD_CLEANUP_FAILED"
            self.client = None
        if self.process is None:
            self.reaped = True
            return
        try:
            if self.process.poll() is None:
                self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
            self.reaped = self.process.poll() is not None
            _require(self.reaped, "CHILD_CLEANUP_FAILED")
            for capture in (self.stdout, self.stderr):
                if capture is not None:
                    capture.thread.join(timeout=2)
                    if capture.thread.is_alive():
                        failure = "CHILD_CLEANUP_FAILED"
                    else:
                        capture.stream.close()
                    if capture.overflow:
                        failure = "DIAGNOSTICS_UNSAFE"
        except (OSError, subprocess.TimeoutExpired):
            raise AcceptanceFailure("CHILD_CLEANUP_FAILED") from None
        if failure:
            raise AcceptanceFailure(failure)

    def diagnostics(self) -> bytes:
        return b"".join(
            bytes(capture.data) for capture in (self.stdout, self.stderr) if capture is not None
        )


def _temp_base() -> Path:
    base = (
        Path(os.environ["LOCALAPPDATA"]) / "Temp"
        if os.name == "nt" and os.environ.get("LOCALAPPDATA")
        else Path(tempfile.gettempdir())
    )
    resolved = base.resolve()
    _require(
        resolved.is_dir()
        and not resolved.is_relative_to(ROOT.resolve())
        and all("onedrive" not in part.lower() for part in resolved.parts),
        "TEMPORARY_DIRECTORY_UNSAFE",
    )
    return resolved


def _owned_child() -> int:
    sock: socket.socket | None = None
    try:
        control = json.loads(sys.stdin.buffer.readline(4096))
        _require(
            isinstance(control, dict)
            and set(control) == {"database", "nonce", "parent_pid", "mode"},
            "CONFIGURATION_INVALID",
        )
        _require(
            type(control["parent_pid"]) is int
            and control["parent_pid"] == os.getppid()
            and isinstance(control["nonce"], str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", control["nonce"]))
            and control["mode"] in {"enabled", "disabled", "remote"},
            "CONFIGURATION_INVALID",
        )
        database = Path(control["database"])
        _require(
            database.name == "state.sqlite3"
            and database.is_absolute()
            and database.parent.parent.resolve() == _temp_base()
            and database.parent.name.startswith("finex-s1-acceptance-")
            and database.parent.is_dir()
            and not database.parent.is_symlink(),
            "CONFIGURATION_INVALID",
        )
        _require(os.environ.get("LOCAL_DB_PATH") == str(database), "CONFIGURATION_INVALID")
        sock, port = allocate_loopback_socket()
        print(
            json.dumps(
                {
                    "kind": HANDSHAKE_KIND,
                    "pid": os.getpid(),
                    "port": port,
                    "nonce": control["nonce"],
                }
            ),
            flush=True,
        )
        logging.disable(logging.CRITICAL)
        # Do not load the repository's developer .env; the child is completely
        # configured by the parent's isolated environment.
        from app.config.settings import Settings

        Settings.model_config["env_file"] = None
        import uvicorn

        config = uvicorn.Config(
            "app.main:app",
            host="127.0.0.1",
            port=port,
            proxy_headers=False,
            access_log=False,
            reload=False,
            workers=1,
            log_config=None,
            log_level="critical",
        )
        uvicorn.Server(config).run(sockets=[sock])
        return 0
    except BaseException:
        # Never relay a settings repr, traceback, database path or child output.
        return 2
    finally:
        if sock is not None:
            sock.close()


class NativeProof:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.servers: list[OwnedServer] = []
        self.server: OwnedServer | None = None
        self.tokens: set[str] = set()
        self.cases: dict[str, dict[str, Any]] = {}
        self.checks: list[dict[str, Any]] = []
        self.ttl_elapsed: float | None = None

    def mark(self, identifier: str) -> None:
        _require(
            identifier in REQUIRED_CHECKS and identifier not in {item["id"] for item in self.checks}
        )
        self.checks.append({"id": identifier, "passed": True})

    def start(self, mode: str = "enabled") -> OwnedServer:
        server = OwnedServer(self.database, mode=mode)
        self.servers.append(server)
        server.start(expect_configuration_failure=mode == "remote")
        self.server = server
        return server

    def current_server(self) -> OwnedServer:
        if self.server is None:
            raise AcceptanceFailure("PROBE_FAILED")
        return self.server

    def current_client(self) -> httpx.Client:
        client = self.current_server().client
        if client is None:
            raise AcceptanceFailure("PROBE_FAILED")
        return client

    def request(
        self,
        operation: str,
        token: str | None,
        payload: dict[str, Any] | None = None,
        *,
        status: int = 200,
        code: str | None = None,
        case_id: str | None = None,
        query: dict[str, str] | None = None,
        extra_headers: dict[str, str] | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, Any]:
        client = self.current_client()
        method, path = ROUTES[operation]
        headers = {"Authorization": "Bearer " + token} if token else {}
        headers.update(extra_headers or {})
        try:
            response = client.request(
                method,
                path,
                json=payload if raw_body is None else None,
                content=raw_body,
                params=query,
                headers=headers,
            )
            raw = response.content
            _require(
                len(raw) <= MAX_BODY
                and not response.history
                and "set-cookie" not in response.headers
                and response.headers.get("content-type", "").split(";")[0] == "application/json",
                "WIRE_INVALID",
            )
            _require(
                all(value.encode("ascii") not in raw for value in self.tokens), "TOKEN_REFLECTION"
            )
            body = response.json()
            _require(isinstance(body, dict) and response.status_code == status, "WIRE_INVALID")
            if code:
                _require(
                    body.get("success") is False
                    and body.get("error_code") == code
                    and body.get("error", {}).get("code") == code
                    and "data" not in body,
                    "WIRE_INVALID",
                )
            else:
                _require(
                    body.get("success") is True and isinstance(body.get("data"), dict),
                    "WIRE_INVALID",
                )
            if case_id:
                _require(case_id in CASE_IDS and case_id not in self.cases)
                self.cases[case_id] = {
                    "id": case_id,
                    "operation": operation,
                    "request": payload,
                    "status": status,
                    "content_type": "application/json",
                    "body_utf8": raw.decode("utf-8"),
                    "expected": {"outcome": "error", "error_code": code}
                    if code
                    else {"outcome": "success"},
                }
            return body.get("data", body)
        except (httpx.HTTPError, ValueError, TypeError, UnicodeError):
            raise AcceptanceFailure("WIRE_INVALID") from None

    def login(self, alias: str) -> tuple[str, str, datetime]:
        client = self.current_client()
        try:
            response = client.post("/api/v1/local-auth/mock-login", json={"alias": alias})
            _require(
                response.status_code == 200
                and len(response.content) <= MAX_BODY
                and "set-cookie" not in response.headers
                and not response.history,
                "WIRE_INVALID",
            )
            data = response.json()["data"]
            token = data["access_token"]
            _require(
                isinstance(token, str) and bool(TOKEN_PATTERN.fullmatch(token)), "WIRE_INVALID"
            )
            self.tokens.add(token)
            _require(
                data["scope"] == SCOPE
                and data["contract_version"] == CONTRACT_VERSION
                and data["token_type"] == "Bearer"
                and data["user"]["alias"] == alias,
                "WIRE_INVALID",
            )
            return token, data["user"]["id"], _utc(data["expires_at"])
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            raise AcceptanceFailure("WIRE_INVALID") from None

    def unchanged_error(
        self,
        operation: str,
        token: str,
        payload: dict[str, Any],
        *,
        status: int,
        code: str,
        case_id: str | None = None,
    ) -> None:
        before = self.request("state", token)
        self.request(operation, token, payload, status=status, code=code, case_id=case_id)
        _require(self.request("state", token) == before)

    def run(self) -> None:
        disabled = self.start("disabled")
        response = self.current_client().post(
            "/api/v1/local-auth/mock-login",
            content=b"{malformed",
            headers={"Content-Type": "application/json"},
        )
        _require(
            response.status_code == 403
            and response.json().get("error_code") == "LOCAL_APPLICATION_ONLY"
            and not self.database.exists()
        )
        self.request("me", None, status=403, code="LOCAL_APPLICATION_ONLY")
        _require(not self.database.exists())
        disabled.stop()
        self.mark("disabled_prebody_no_database")
        remote = self.start("remote")
        remote.stop()
        _require(not self.database.exists())
        self.mark("remote_configuration_no_database")

        self.start()
        a, a_id, _ = self.login("learner-a")
        b, b_id, _ = self.login("learner-b")
        a_other, other_id, _ = self.login("learner-a")
        _require(a_id == other_id and a_id != b_id and a != a_other)
        initial = self.request("state", a, case_id="initial")
        _require(
            initial["draft"] == {"display_name": None, "experience_level": None, "updated_at": None}
            and initial["consent"] is None
            and initial["onboarding_completed"] is False
        )
        b_initial = self.request("state", b)
        identity = self.request("me", a, case_id="me")
        _require(identity["user"]["id"] == a_id)
        self.mark("two_persona_ownership")
        self.request(
            "state",
            None,
            status=401,
            code="SESSION_INVALID",
            query={"access_token": "not-a-credential"},
        )
        self.mark("query_not_authentication")
        selected = self.request(
            "me",
            a,
            query={"owner_id": b_id, "user_id": b_id},
            extra_headers={"X-User-ID": b_id, "X-Owner-ID": b_id, "X-Forwarded-For": "203.0.113.1"},
        )
        _require(selected["user"]["id"] == a_id)
        self.mark("header_query_not_owner")
        self.unchanged_error(
            "draft",
            b,
            {**PROFILE_REQUEST, "owner_id": a_id},
            status=422,
            code="VALIDATION_ERROR",
            case_id="validation_error",
        )
        _require(self.request("state", a) == initial and self.request("state", b) == b_initial)
        self.mark("extra_owner_rejected_unchanged")
        partial = self.request("draft", a, PARTIAL_REQUEST, case_id="partial_draft")
        _require(
            partial["draft"]["display_name"] is None
            and partial["draft"]["experience_level"] == "beginner"
            and partial["draft"]["updated_at"] is not None
            and partial["onboarding_completed"] is False
        )
        self.mark("partial_draft")
        self.unchanged_error(
            "complete",
            a,
            COMPLETE_REQUEST,
            status=409,
            code="CONSENT_REQUIRED",
            case_id="consent_required",
        )
        accepted = self.request("consent", a, CONSENT_REQUEST, case_id="consent_accepted")
        _require(
            accepted["consent"]["accepted"] is True and accepted["onboarding_completed"] is False
        )
        self.unchanged_error(
            "complete",
            a,
            COMPLETE_REQUEST,
            status=409,
            code="PROFILE_INCOMPLETE",
            case_id="profile_incomplete",
        )
        self.mark("prerequisite_rejections_unchanged")
        self.unchanged_error(
            "draft",
            a,
            {**PROFILE_REQUEST, "profile_schema_version": "profile.future"},
            status=409,
            code="PROFILE_VERSION_MISMATCH",
            case_id="profile_version_mismatch",
        )
        self.unchanged_error(
            "consent",
            a,
            {**CONSENT_REQUEST, "consent_version": "consent.future"},
            status=409,
            code="CONSENT_VERSION_MISMATCH",
            case_id="consent_version_mismatch",
        )
        self.unchanged_error(
            "complete",
            a,
            {**COMPLETE_REQUEST, "consent_version": "consent.future"},
            status=409,
            code="CONSENT_VERSION_MISMATCH",
        )
        self.unchanged_error(
            "complete",
            a,
            {**COMPLETE_REQUEST, "profile_schema_version": "profile.future"},
            status=409,
            code="PROFILE_VERSION_MISMATCH",
        )
        self.mark("version_rejections_unchanged")
        for operation, payload in (
            ("draft", {"profile_schema_version": "profile.v1"}),
            ("draft", {**PROFILE_REQUEST, "experience_level": "invalid"}),
            ("consent", {**CONSENT_REQUEST, "consent_given": "true"}),
        ):
            self.unchanged_error(operation, a, payload, status=422, code="VALIDATION_ERROR")
        before_malformed = self.request("state", a)
        self.request(
            "draft",
            a,
            status=422,
            code="VALIDATION_ERROR",
            raw_body=b"{malformed",
            extra_headers={"Content-Type": "application/json"},
        )
        _require(self.request("state", a) == before_malformed)
        self.mark("malformed_validation_unchanged")

        self.current_server().stop()
        self.start()
        self.mark("first_process_restart")
        _require(
            self.request("state", a_other) == accepted
            and self.request("me", a_other)["user"]["id"] == a_id
            and self.request("state", b) == b_initial
        )
        resumed, resumed_id, _ = self.login("learner-a")
        _require(resumed_id == a_id and self.request("state", resumed) == accepted)
        self.mark("persisted_partial_and_sessions")
        saved = self.request("draft", a, PROFILE_REQUEST, case_id="saved_profile")
        _require(saved["onboarding_completed"] is False)
        completed = self.request("complete", a, COMPLETE_REQUEST, case_id="completed")
        _require(
            completed["onboarding_completed"] is True and completed["completed_at"] is not None
        )
        self.mark("explicit_completion")
        repeated = self.request("complete", a, COMPLETE_REQUEST, case_id="repeated_complete")
        identical = self.request("draft", a, PROFILE_REQUEST, case_id="identical_draft")
        _require(repeated == completed and identical == completed)
        self.mark("repeat_and_identical_preserve_time")
        changed = self.request("draft", a, CHANGED_REQUEST, case_id="changed_profile")
        _require(
            changed["onboarding_completed"] is False
            and changed["completed_at"] is None
            and changed["draft"]["display_name"] == CHANGED_REQUEST["display_name"]
            and changed["draft"]["updated_at"] != completed["draft"]["updated_at"]
        )
        self.mark("profile_change_invalidates")
        self.request("complete", a, COMPLETE_REQUEST)
        withdrawn = self.request(
            "consent", a, {**CONSENT_REQUEST, "consent_given": False}, case_id="withdrawn"
        )
        _require(
            withdrawn["consent"]["accepted"] is False
            and withdrawn["onboarding_completed"] is False
            and withdrawn["completed_at"] is None
        )
        self.unchanged_error("complete", a, COMPLETE_REQUEST, status=409, code="CONSENT_REQUIRED")
        reaccepted = self.request("consent", a, CONSENT_REQUEST, case_id="reaccepted")
        _require(
            reaccepted["consent"]["accepted"] is True
            and reaccepted["onboarding_completed"] is False
            and reaccepted["completed_at"] is None
        )
        self.mark("withdrawal_and_reacceptance_gate")
        self.request("logout", a, case_id="logged_out")
        self.request("state", a, status=401, code="SESSION_INVALID", case_id="session_invalid")
        _require(
            self.request("state", a_other) == reaccepted and self.request("state", b) == b_initial
        )
        self.mark("durable_per_session_logout")

        self.current_server().stop()
        self.start()
        self.mark("second_process_restart")
        self.request("me", a, status=401, code="SESSION_INVALID")
        _require(
            self.request("state", a_other) == reaccepted
            and self.request("me", a_other)["user"]["id"] == a_id
            and self.request("state", b) == b_initial
        )
        final, final_id, _ = self.login("learner-a")
        _require(final_id == a_id and self.request("state", final) == reaccepted)
        self.mark("persisted_data_and_revocation")
        self.mark("owned_child_handshakes")
        started = time.monotonic()
        before_login = datetime.now(timezone.utc)
        expiring, _, expiry = self.login("learner-b")
        after_login = datetime.now(timezone.utc)
        _require(
            before_login + timedelta(seconds=60) <= expiry <= after_login + timedelta(seconds=60),
            "TTL_FAILED",
        )
        deadline = started + 75
        valid_seen = False
        while time.monotonic() < deadline:
            try:
                response = self.current_client().get(
                    "/api/v1/local-auth/me", headers={"Authorization": "Bearer " + expiring}
                )
                _require(
                    all(token.encode("ascii") not in response.content for token in self.tokens),
                    "TOKEN_REFLECTION",
                )
                if response.status_code == 401:
                    _require(
                        response.json().get("error_code") == "SESSION_INVALID"
                        and valid_seen
                        and time.monotonic() - started >= 59,
                        "TTL_FAILED",
                    )
                    self.ttl_elapsed = round(time.monotonic() - started, 3)
                    break
                _require(response.status_code == 200, "TTL_FAILED")
                valid_seen = True
            except (httpx.HTTPError, ValueError, TypeError):
                raise AcceptanceFailure("TTL_FAILED") from None
            time.sleep(0.5)
        _require(self.ttl_elapsed is not None, "TTL_FAILED")
        self.mark("real_one_minute_expiry")
        for server in self.servers:
            server.stop()
            _require(
                all(token.encode("ascii") not in server.diagnostics() for token in self.tokens),
                "TOKEN_REFLECTION",
            )
        self.verify_storage()

    def verify_storage(self) -> None:
        """Read only this proof's database; release it before directory cleanup."""
        with closing(sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)) as connection:
            stored = connection.execute("SELECT digest FROM local_sessions").fetchall()
            _require(
                {row[0] for row in stored}
                == {hashlib.sha256(token.encode("ascii")).hexdigest() for token in self.tokens}
            )
        for path in self.database.parent.iterdir():
            if path.is_file():
                _require(
                    all(token.encode("ascii") not in path.read_bytes() for token in self.tokens),
                    "TOKEN_REFLECTION",
                )
        self.mark("digest_only_storage_no_reflection")


def _failure_report(code: str, provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "finex.local_s1.acceptance.v1",
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "success": False,
        "mode": "owned_native_tcp",
        **(provenance or {}),
        "checks": [],
        "required_checks": list(REQUIRED_CHECKS),
        "failures": [{"code": AcceptanceFailure(code).code}],
    }


def evaluate_acceptance(
    *, tested_sha: str | None = None, tested_tree: str | None = None
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Mandatory native proof; every failure including cleanup makes it nonzero."""
    provenance: dict[str, Any] = {}
    proof: NativeProof | None = None
    workspace: Path | None = None
    failure: str | None = None
    corpus: dict[str, Any] | None = None
    removed = False
    try:
        provenance = repository_provenance(tested_sha, tested_tree)
        base = _temp_base()
        workspace = Path(tempfile.mkdtemp(prefix="finex-s1-acceptance-", dir=base))
        proof = NativeProof(workspace / "state.sqlite3")
        proof.run()
        corpus = {
            "schema_version": CORPUS_SCHEMA,
            "scope": SCOPE,
            "contract_version": CONTRACT_VERSION,
            "provenance": {
                "kind": "native_tcp_capture",
                "source": "owned_loopback_uvicorn",
                "command": COMMAND,
                "tested_commit": provenance["tested_commit"],
                "tested_tree": provenance["tested_tree"],
            },
            "cases": [proof.cases[identifier] for identifier in CASE_IDS],
        }
        validate_corpus(corpus, native_required=True)
        proof.mark("complete_wire_corpus")
        _require(source_hashes() == provenance["source_hashes"], "SOURCE_CHANGED")
        _require(
            _git(["rev-parse", "HEAD"]) == provenance["tested_commit"]
            and _git(["rev-parse", "HEAD^{tree}"]) == provenance["tested_tree"],
            "SOURCE_CHANGED",
        )
    except AcceptanceFailure as error:
        failure = error.code
    except Exception:
        failure = "INTERNAL_FAILURE"
    finally:
        if proof is not None:
            for server in proof.servers:
                try:
                    server.stop()
                except AcceptanceFailure as error:
                    failure = error.code
        if workspace is not None:
            try:
                _require(
                    proof is not None and all(server.reaped for server in proof.servers),
                    "CHILD_CLEANUP_FAILED",
                )
                _require(
                    workspace.parent.resolve() == _temp_base()
                    and workspace.name.startswith("finex-s1-acceptance-")
                    and not workspace.is_symlink(),
                    "TEMPORARY_DIRECTORY_UNSAFE",
                )
                shutil.rmtree(workspace)
                removed = not workspace.exists()
                _require(removed, "TEMPORARY_CLEANUP_FAILED")
            except AcceptanceFailure as error:
                failure = error.code
            except OSError:
                failure = "TEMPORARY_CLEANUP_FAILED"
    if failure or proof is None or corpus is None or not removed:
        report = _failure_report(failure or "INTERNAL_FAILURE", provenance)
        if proof is not None:
            report["checks"] = proof.checks
        return report, None
    proof.mark("owned_cleanup")
    _require({item["id"] for item in proof.checks} == set(REQUIRED_CHECKS))
    return {
        "schema_version": "finex.local_s1.acceptance.v1",
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "success": True,
        "mode": "owned_native_tcp",
        **provenance,
        "checks": proof.checks,
        "required_checks": list(REQUIRED_CHECKS),
        "failures": [],
        "native_process": {
            "starts": len(proof.servers),
            "application_restarts": 2,
            "loopback": True,
            "proxy_headers": False,
            "access_log": False,
            "session_ttl_minutes": 1,
            "ttl_elapsed_seconds": proof.ttl_elapsed,
            "child_reaped": True,
            "temporary_directory_removed": True,
            "shutdown": "owned_terminate_and_reap",
        },
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "limitations": [
            "Synthetic trusted personas are not verified real identities.",
            "TCP API process proof is not native-device, human-pair or release acceptance.",
            "Error wire replay does not claim typed clients emitted illegal requests.",
            "No real brokerage, live provider, paid service or cloud deployment.",
        ],
    }, corpus


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AcceptanceFailure("CLI_ARGUMENTS_INVALID")


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
    except FileExistsError:
        raise AcceptanceFailure("OUTPUT_EXISTS") from None
    except OSError:
        raise AcceptanceFailure("OUTPUT_WRITE_FAILED") from None


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments == ["--owned-child"]:
        return _owned_child()
    parser = _SafeParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="New safe JSON report file; never overwrite.")
    parser.add_argument("--corpus", type=Path, help="New safe wire capture file; never commit it.")
    parser.add_argument("--tested-sha", required=True, help="Exact lowercase checkout commit SHA.")
    parser.add_argument(
        "--tested-tree", required=True, help="Exact lowercase checkout HEAD tree SHA."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    try:
        options = parser.parse_args(arguments)
        targets = [path.resolve() for path in (options.report, options.corpus) if path is not None]
        _require(len(targets) == len(set(targets)), "OUTPUT_INVALID")
        for target in targets:
            _require(not target.exists() and not target.is_symlink(), "OUTPUT_EXISTS")
            _require(target.parent.is_dir(), "OUTPUT_INVALID")
        report, corpus = evaluate_acceptance(
            tested_sha=options.tested_sha, tested_tree=options.tested_tree
        )
        if report.get("success") is True:
            if corpus is None:
                raise AcceptanceFailure("CORPUS_INVALID")
            validate_corpus(corpus, native_required=True)
            if options.corpus is not None:
                _write_new_json(options.corpus, corpus)
        if options.report is not None:
            _write_new_json(options.report, report)
        if options.format == "json":
            print(json.dumps(report, sort_keys=True))
        else:
            print(
                "S1 owned native acceptance: "
                + ("PASS" if report.get("success") is True else "FAIL")
            )
        return 0 if report.get("success") is True else 1
    except AcceptanceFailure as error:
        print(json.dumps(_failure_report(error.code), sort_keys=True))
        return 1
    except Exception:
        print(json.dumps(_failure_report("INTERNAL_FAILURE"), sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
