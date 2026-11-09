"""Pure failure/ownership checks; these do not pretend to prove a TCP restart."""

import io
import json
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

import verify_s1_application as harness

FIXTURE = harness.ROOT / "data/fixtures/local_s1/contract_cases.v1.json"
SHA = "a" * 40
TREE = "b" * 40
NONCE = "n" * 64


def synthetic_corpus() -> dict[str, Any]:
    assert FIXTURE.is_file(), "The explicitly synthetic checked-in wire corpus is required."
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_handcrafted_corpus_has_all_required_cases_and_no_login_or_credentials() -> None:
    document = synthetic_corpus()
    assert document["provenance"] == {
        "kind": "synthetic_fixture",
        "source": "handcrafted",
        "command": "handcrafted local S1 contract fixture",
    }
    cases = harness.validate_corpus(document)
    assert {case["id"] for case in cases} == set(harness.CASE_IDS)
    raw = json.dumps(document).lower()
    assert all(
        word not in raw for word in ("access_token", "authorization", "cookie", "expires_at")
    )
    assert all(case["operation"] != "login" for case in cases)


@pytest.mark.parametrize(
    "mutation",
    ["wrong_scope", "wrong_version", "missing_case", "duplicate_case", "wrong_status", "bad_body"],
)
def test_invalid_or_incomplete_corpus_is_not_silently_accepted(mutation: str) -> None:
    document = synthetic_corpus()
    if mutation == "wrong_scope":
        document["scope"] = "local_educational_pilot"
    elif mutation == "wrong_version":
        document["contract_version"] = "local.future"
    elif mutation == "missing_case":
        document["cases"].pop()
    elif mutation == "duplicate_case":
        document["cases"].append(deepcopy(document["cases"][0]))
    elif mutation == "wrong_status":
        document["cases"][0]["status"] = 500
    else:
        document["cases"][0]["body_utf8"] = "not-json"
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.validate_corpus(document)
    assert caught.value.code == "CORPUS_INVALID"


def test_required_native_provenance_rejects_synthetic_or_malformed_claims() -> None:
    document = synthetic_corpus()
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.validate_corpus(document, native_required=True)
    assert caught.value.code == "CORPUS_INVALID"
    document["provenance"] = {
        "kind": "native_tcp_capture",
        "source": "owned_loopback_uvicorn",
        "command": harness.COMMAND,
        "tested_commit": SHA,
        "tested_tree": TREE,
    }
    assert len(harness.validate_corpus(document, native_required=True)) == 18
    document["provenance"]["tested_commit"] = "not-an-exact-sha"
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.validate_corpus(document, native_required=True)
    assert caught.value.code == "CORPUS_INVALID"


def handshake(**changes: Any) -> bytes:
    return json.dumps(
        {"kind": "finex.local_s1.child.v1", "pid": 123, "port": 23456, "nonce": NONCE, **changes}
    ).encode("utf-8")


def test_narrow_handshake_proves_nonce_and_popen_pid_before_port_use() -> None:
    assert harness.validate_handshake(handshake(), expected_pid=123, expected_nonce=NONCE) == 23456


@pytest.mark.parametrize(
    "changes",
    [
        {"pid": 124},
        {"nonce": "wrong"},
        {"kind": "wrong"},
        {"port": 0},
        {"port": True},
        {"port": 65536},
        {"port": "23456"},
        {"unexpected": "value"},
    ],
)
def test_forged_or_malformed_handshake_is_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.validate_handshake(handshake(**changes), expected_pid=123, expected_nonce=NONCE)
    assert caught.value.code == "HANDSHAKE_INVALID"


def test_child_configuration_cannot_inherit_real_services_or_developer_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for key, value in {
        "APP_ENV": "prod",
        "HOST": "0.0.0.0",
        "PORT": "8081",
        "LOCAL_APP_ENABLED": "false",
        "LOCAL_DB_PATH": "developer.sqlite3",
        "LOCAL_SESSION_TTL_MINUTES": "60",
        "LLM_PROVIDER": "openai",
        "OPENAI_API_KEY": "synthetic-environment-canary",
        "MARKET_DATA_PROVIDER": "polygon",
        "MARKET_DATA_API_KEY": "synthetic-market-canary",
        "DATABRICKS_TOKEN": "synthetic-databricks-canary",
        "HTTPS_PROXY": "http://127.0.0.1:9",
        "GITHUB_MCP_TOKEN": "synthetic-credential-canary",
    }.items():
        monkeypatch.setenv(key, value)
    env = harness.child_environment(tmp_path / "owned.sqlite3")
    assert env["APP_ENV"] == "local"
    assert env["HOST"] == "127.0.0.1"
    assert env["LOCAL_APP_ENABLED"] == "true"
    assert env["LOCAL_DB_PATH"] == str(tmp_path / "owned.sqlite3")
    assert env["LOCAL_SESSION_TTL_MINUTES"] == "1"
    assert env["FIXTURE_MODE"] == "s2_dat_01"
    assert env["LLM_PROVIDER"] == "none"
    assert env["MARKET_DATA_PROVIDER"] == "mock"
    assert env["ALLOW_CREDENTIALS"] == "false"
    assert json.loads(env["ALLOWED_ORIGINS"]) == ["http://127.0.0.1:3000"]
    assert env["OPENAI_API_KEY"] == env["MARKET_DATA_API_KEY"] == env["DATABRICKS_TOKEN"] == ""
    assert "GITHUB_MCP_TOKEN" not in env
    assert "HTTPS_PROXY" not in env
    assert env.get("PORT") != "8081"


@pytest.mark.parametrize("sha,tree", [("bad", TREE), (SHA, "bad"), ("A" * 40, TREE)])
def test_invalid_sha_or_tree_is_a_safe_failure_not_an_unverified_label(sha: str, tree: str) -> None:
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.repository_provenance(sha, tree)
    assert caught.value.code == "PROVENANCE_INVALID"


def test_failed_probe_means_nonzero_cli_and_no_success_corpus(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        harness,
        "evaluate_acceptance",
        lambda **_kwargs: ({"success": False, "failures": [{"code": "PROBE_FAILED"}]}, None),
    )
    report = tmp_path / "report.json"
    corpus = tmp_path / "corpus.json"
    result = harness.main(
        [
            "--report",
            str(report),
            "--corpus",
            str(corpus),
            "--tested-sha",
            SHA,
            "--tested-tree",
            TREE,
            "--format",
            "json",
        ]
    )
    assert result == 1
    assert json.loads(report.read_text(encoding="utf-8"))["success"] is False
    assert not corpus.exists()
    assert "PROBE_FAILED" in capsys.readouterr().out


@pytest.mark.parametrize("mutation", ["request_version", "initial", "reaccepted", "repeat_time"])
def test_semantic_case_labels_cannot_lie_about_their_captured_state(mutation: str) -> None:
    document = synthetic_corpus()
    cases = {case["id"]: case for case in document["cases"]}
    if mutation == "request_version":
        cases["consent_accepted"]["request"]["consent_version"] = "consent.future"
    elif mutation == "initial":
        cases["initial"]["body_utf8"] = cases["completed"]["body_utf8"]
    elif mutation == "reaccepted":
        cases["reaccepted"]["body_utf8"] = cases["completed"]["body_utf8"]
    else:
        body = json.loads(cases["repeated_complete"]["body_utf8"])
        body["data"]["completed_at"] = "2026-10-11T12:00:01+00:00"
        cases["repeated_complete"]["body_utf8"] = json.dumps(body)
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.validate_corpus(document)
    assert caught.value.code == "CORPUS_INVALID"


class FakeProcess:
    """No actual subprocess; ownership, timeout, and reaping are unit invariants."""

    pid = 123

    def __init__(self, output: bytes = b"") -> None:
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(output)
        self.stderr = io.BytesIO()
        self.returncode: int | None = None
        self.terminated = 0
        self.killed = 0
        self.waited = 0

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated += 1
        self.returncode = 0

    def kill(self) -> None:
        self.killed += 1
        self.returncode = 0

    def wait(self, timeout: float) -> int:
        self.waited += 1
        if self.returncode is None:
            raise subprocess.TimeoutExpired("synthetic-owned-child", timeout)
        return self.returncode


@pytest.mark.parametrize(
    "output,code", [(handshake(pid=999), "HANDSHAKE_INVALID"), (b"", "CHILD_START_TIMEOUT")]
)
def test_bad_handshake_or_start_timeout_reaps_only_the_owned_process_before_raising(
    output: bytes, code: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    process = FakeProcess(output)
    monkeypatch.setattr(harness.subprocess, "Popen", lambda *_args, **_kwargs: process)
    clients: list[bool] = []
    monkeypatch.setattr(harness.httpx, "Client", lambda **_kwargs: clients.append(True))
    server = harness.OwnedServer(tmp_path / "state.sqlite3", startup_timeout=0.01)
    with pytest.raises(harness.AcceptanceFailure) as caught:
        server.start()
    assert caught.value.code == code
    assert not clients, "Health must not use an unproven child's claimed port."
    assert process.terminated == 1 and process.waited >= 1 and server.reaped
    assert process.stdout.closed and process.stderr.closed


def test_diagnostic_overflow_still_reaps_and_closes_all_owned_pipes(tmp_path: Path) -> None:
    process = FakeProcess()
    process.returncode = 0
    thread = SimpleNamespace(join=lambda **_kwargs: None, is_alive=lambda: False)
    first = SimpleNamespace(stream=io.BytesIO(), thread=thread, overflow=True)
    second = SimpleNamespace(stream=io.BytesIO(), thread=thread, overflow=False)
    server = harness.OwnedServer(tmp_path / "state.sqlite3")
    server.process, server.stdout, server.stderr = process, first, second
    with pytest.raises(harness.AcceptanceFailure) as caught:
        server.stop()
    assert caught.value.code == "DIAGNOSTICS_UNSAFE"
    assert server.reaped and first.stream.closed and second.stream.closed


def test_socket_creation_failure_is_sanitized_without_an_os_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_socket(*_args, **_kwargs):
        raise OSError("synthetic-private-os-diagnostic")

    monkeypatch.setattr(harness.socket, "socket", fail_socket)
    try:
        harness.allocate_loopback_socket()
        caught: Exception | None = None
    except Exception as error:
        caught = error
    assert isinstance(caught, harness.AcceptanceFailure)
    assert caught.code == "SOCKET_BIND_FAILED"
    assert "private" not in str(caught)


def test_bind_collision_closes_only_the_allocated_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    class CollidingSocket:
        closed = False

        def setsockopt(self, *_args):
            pass

        def bind(self, _address):
            raise OSError("synthetic-address-in-use")

        def close(self):
            self.closed = True

    sock = CollidingSocket()
    monkeypatch.setattr(harness.socket, "socket", lambda *_args: sock)
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.allocate_loopback_socket()
    assert caught.value.code == "SOCKET_BIND_FAILED"
    assert sock.closed


def test_capture_rejects_cookie_side_effects_instead_of_silently_using_a_jar(
    tmp_path: Path,
) -> None:
    initial = next(case for case in synthetic_corpus()["cases"] if case["id"] == "initial")
    response = httpx.Response(
        200,
        content=initial["body_utf8"].encode("utf-8"),
        headers={"content-type": "application/json", "set-cookie": "x=synthetic"},
    )
    client = SimpleNamespace(request=lambda *_args, **_kwargs: response)
    proof = harness.NativeProof(tmp_path / "state.sqlite3")
    proof.server = SimpleNamespace(client=client)
    with pytest.raises(harness.AcceptanceFailure) as caught:
        proof.request("state", None)
    assert caught.value.code == "WIRE_INVALID"


def test_existing_output_is_never_overwritten_or_probed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "existing.json"
    report.write_text("synthetic-existing-data", encoding="utf-8")
    calls: list[bool] = []
    monkeypatch.setattr(harness, "evaluate_acceptance", lambda **_kwargs: calls.append(True))
    assert harness.main(["--report", str(report), "--tested-sha", SHA, "--tested-tree", TREE]) == 1
    assert not calls
    assert report.read_text(encoding="utf-8") == "synthetic-existing-data"
    assert "OUTPUT_EXISTS" in capsys.readouterr().out


def test_unknown_cli_arguments_are_redacted(capsys: pytest.CaptureFixture[str]) -> None:
    assert harness.main(["--unknown", "synthetic-private-argument"]) == 1
    output = capsys.readouterr()
    assert "CLI_ARGUMENTS_INVALID" in output.out
    assert "private-argument" not in output.out + output.err


def test_provenance_must_match_actual_revision_and_dirty_state_is_honest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def read_git(arguments):
        if arguments == ["rev-parse", "HEAD"]:
            return SHA
        if arguments == ["rev-parse", "HEAD^{tree}"]:
            return TREE
        return "synthetic-dirty-status"

    monkeypatch.setattr(harness, "_git", read_git)
    monkeypatch.setattr(
        harness, "source_hashes", lambda: [{"path": "synthetic.py", "sha256": "c" * 64}]
    )
    provenance = harness.repository_provenance(SHA, TREE)
    assert provenance["tested_commit"] == SHA and provenance["tested_tree"] == TREE
    assert provenance["working_tree_dirty"] is True and provenance["tracked_dirty"] is True
    with pytest.raises(harness.AcceptanceFailure) as caught:
        harness.repository_provenance("d" * 40, TREE)
    assert caught.value.code == "PROVENANCE_MISMATCH"


@pytest.mark.parametrize("query_fails", [False, True])
def test_storage_probe_closes_read_only_connection_on_success_and_failure(
    query_fails: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class ReadOnlyConnection:
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            # sqlite3.Connection's transaction context does not close it.
            pass

        def execute(self, _query):
            if query_fails:
                raise RuntimeError("synthetic-query-failure")
            return SimpleNamespace(fetchall=lambda: [])

        def close(self):
            self.closed = True

    connection = ReadOnlyConnection()
    monkeypatch.setattr(harness.sqlite3, "connect", lambda *_args, **_kwargs: connection)
    proof = harness.NativeProof(tmp_path / "state.sqlite3")
    if query_fails:
        with pytest.raises(RuntimeError):
            proof.verify_storage()
    else:
        proof.verify_storage()
    assert connection.closed, (
        "The proof must release the actual file handle, not only a transaction."
    )
