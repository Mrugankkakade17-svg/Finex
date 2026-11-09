"""Offline control-flow probes of the actual portfolio expiry-phase AST.

Only the existing expiry-phase statements are executed, with all native/API
effects replaced by bounded unit fakes. This is NOT a real clock/TCP proof.
The source extraction avoids hand-copying the flow that these assertions guard.
Trace entries are role labels only, never private IDs, bodies or bearer values.
"""

import ast
import inspect
import json
import secrets
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

import verify_s2_manual_portfolio as verifier


def expiry_phase_trace(monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    source = ast.parse(textwrap.dedent(inspect.getsource(verifier.PortfolioProof.run)))
    original = source.body[0]
    assert isinstance(original, ast.FunctionDef)
    start = next(
        index
        for index, node in enumerate(original.body)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "started" for target in node.targets)
    )
    stop = next(
        index
        for index, node in enumerate(original.body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Attribute)
        and node.value.func.attr == "mark"
        and node.value.args
        and isinstance(node.value.args[0], ast.Constant)
        and node.value.args[0].value == "records_preserved_after_expiry"
    )
    # The compiled statements are the real owned source, not a mirrored flow.
    fragment = ast.FunctionDef(
        name="unit_only_actual_expiry_phase",
        args=original.args,
        body=original.body[start : stop + 1],
        decorator_list=[],
        returns=None,
        type_comment=None,
        type_params=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[fragment], type_ignores=[]))
    trace: list[tuple] = []
    roles = {role: secrets.token_urlsafe(32) for role in ("expired", "fresh-a", "fresh-b")}
    private_ids = {
        "fresh-a": "unit-private-a",
        "fresh-b": "unit-private-b",
        "expired": "unit-private-b",
    }
    kept = "00000000-0000-4000-8000-000000000191"
    other = {"portfolio_id": "00000000-0000-4000-8000-000000000192"}
    held_b = {"holding_id": "00000000-0000-4000-8000-000000000193"}
    saved_a = {"items": [{"portfolio_id": kept}]}
    held_a = {"portfolio_id": kept, "items": []}
    risk_a = {"assessment_id": "00000000-0000-4000-8000-000000000194"}
    risk_b = {"assessment_id": "00000000-0000-4000-8000-000000000195"}
    draft_a = {"answers": [{"question_id": "W1", "answer_code": "W1_C"}]}
    state_a, state_b = {"unit": "completed-a"}, {"unit": "completed-b"}

    def role_for(token: str) -> str:
        return next(role for role, value in roles.items() if value == token)

    class Native:
        ttl_elapsed = None

        def __init__(self) -> None:
            self.login_count = 0

        def login(self, alias: str) -> tuple:
            role = ("expired", "fresh-a", "fresh-b")[self.login_count]
            self.login_count += 1
            trace.append(("login", role))
            return (
                roles[role],
                private_ids[role],
                datetime.now(verifier.timezone.utc) + timedelta(seconds=60),
            )

        def request(self, operation: str, token: str, **_: object) -> dict:
            role = role_for(token)
            trace.append(("s1", operation, role))
            return state_a if role == "fresh-a" else state_b

    class Risk:
        def request(self, method: str, suffix: str, token: str, **options: object) -> dict:
            role = role_for(token)
            trace.append(
                ("risk", method, suffix, role, options.get("status", 200), options.get("code"))
            )
            if role == "expired":
                return {"success": False, "error_code": "SESSION_INVALID"}
            if suffix == "/draft":
                return draft_a if role == "fresh-a" else {"answers": []}
            if suffix.startswith("/assessments/"):
                return risk_a if role == "fresh-a" else risk_b
            return {"items": [risk_a if role == "fresh-a" else risk_b]}

    class Proof:
        def __init__(self) -> None:
            self.native = Native()

        def wait_real_expiry(self, token: str, expires: datetime, **_: object) -> None:
            trace.append(("wait", role_for(token)))
            self.native.ttl_elapsed = 60.125

        def request(self, operation: str, token: str, **_: object) -> dict:
            role = role_for(token)
            trace.append(("portfolio", operation, role))
            if operation == "portfolio_list":
                return saved_a if role == "fresh-a" else {"items": [other]}
            return held_a if role == "fresh-a" else {"items": [held_b]}

        def mark(self, identifier: str) -> None:
            trace.append(("mark", identifier))

    def no_second_wait(seconds: float) -> None:
        pytest.fail("The existing expiry window must not add another sleep.")

    monkeypatch.setattr(verifier.time, "sleep", no_second_wait)
    namespace = {
        **vars(verifier),
        "a_id": private_ids["fresh-a"],
        "b_id": private_ids["fresh-b"],
        "saved_a": saved_a,
        "kept_holdings": held_a,
        "kept": kept,
        "other_b": other,
        "b_holding": held_b,
        "recompleted": state_a,
        "s1_b": state_b,
        "risk": Risk(),
        "risk_draft": draft_a,
        "risk_a": risk_a,
        "risk_b": risk_b,
    }
    exec(compile(module, "<unit-only-real-expiry-phase>", "exec"), namespace)
    namespace["unit_only_actual_expiry_phase"](Proof())
    return trace


def test_same_existing_expiry_window_also_denies_risk_draft_and_current_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = expiry_phase_trace(monkeypatch)
    required = {
        ("risk", "GET", "/draft", "expired", 401, "SESSION_INVALID"),
        ("risk", "GET", "/assessments?limit=2", "expired", 401, "SESSION_INVALID"),
    }
    assert required.issubset(set(trace))


def test_fresh_session_confirms_original_saved_risk_detail_after_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = expiry_phase_trace(monkeypatch)
    required = (
        "risk",
        "GET",
        "/assessments/00000000-0000-4000-8000-000000000195",
        "fresh-b",
        200,
        None,
    )
    assert required in trace


def test_control_flow_retains_one_existing_wait_and_current_draft_preservation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace = expiry_phase_trace(monkeypatch)
    assert [item for item in trace if item[0] == "wait"] == [("wait", "expired")]
    assert ("risk", "GET", "/draft", "fresh-a", 200, None) in trace
    assert ("mark", "real_one_minute_expiry") in trace
    assert ("mark", "records_preserved_after_expiry") in trace


def unit_only_polling_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    *,
    reflected_status: int | None = None,
    private_kind: str | None = None,
) -> tuple[str | None, str | None, int, float | None, int, bool, bool]:
    """Run the real polling method with no TCP, database or real expiry wait.

    The generated private values remain inside this helper. Return only fixed
    diagnostics, scalar counts and booleans so failing assertions cannot print
    a bearer, owner identifier, response body or synthetic database path.
    """
    token = secrets.token_urlsafe(32)
    owner = str(uuid4())
    database = tmp_path / ("unit-private-" + secrets.token_hex(8) + ".sqlite3")
    proof = verifier.PortfolioProof(database)
    proof.native.tokens.add(token)
    proof.private_identities.add(owner)
    private = (token, owner, str(database))
    reflected = {"token": token, "owner": owner, "database": str(database)}

    def body(status: int) -> bytes:
        message = (
            reflected[private_kind]
            if status == reflected_status and private_kind is not None
            else "Synthetic unit-only polling response"
        )
        if status == 200:
            document = {
                "success": True,
                "message": message,
                "data": {
                    "scope": verifier.SCOPE,
                    "contract_version": verifier.CONTRACT_VERSION,
                    "portfolio_version": "portfolio.v1",
                    "items": [],
                    "count": 0,
                },
                "meta": {
                    "apiVersion": "v1",
                    "dataStatus": "CACHED",
                    "dataAsOf": None,
                    "correlationId": "unit-expiry-poll",
                },
            }
        else:
            document = {
                "success": False,
                "message": message,
                "detail": message,
                "error_code": "SESSION_INVALID",
                "error": {
                    "code": "SESSION_INVALID",
                    "message": message,
                    "fieldErrors": [],
                    "correlationId": "unit-expiry-poll",
                },
            }
        raw = json.dumps(document).encode("utf-8")
        if status == reflected_status and private_kind is not None:
            escaped = '"' + "".join(f"\\u{ord(char):04x}" for char in message) + '"'
            raw = raw.replace(json.dumps(message).encode("utf-8"), escaped.encode("ascii"))
        return raw

    responses = (body(200), body(401))
    raw_omits_private = all(
        value.encode("utf-8") not in raw for value in private for raw in responses
    )
    requests_seen = 0

    def respond(_: httpx.Request) -> httpx.Response:
        nonlocal requests_seen
        index = requests_seen
        requests_seen += 1
        # Exactly one valid-phase response and one expired-phase response.
        if index >= len(responses):
            raise verifier.AcceptanceFailure("TTL_FAILED")
        return httpx.Response(
            200 if index == 0 else 401,
            content=responses[index],
            headers={"Content-Type": "application/json"},
        )

    clock = iter((0.0, 60.0, 60.0))
    monkeypatch.setattr(verifier.time, "monotonic", lambda: next(clock, 75.0))
    monkeypatch.setattr(verifier.time, "sleep", lambda _: None)
    before = datetime(2026, 10, 11, 12, 0, tzinfo=verifier.timezone.utc)
    failure_code = diagnostic = None
    with httpx.Client(
        transport=httpx.MockTransport(respond), base_url="http://127.0.0.1"
    ) as client:
        monkeypatch.setattr(proof.native, "current_client", lambda: client)
        try:
            proof.wait_real_expiry(
                token,
                before + timedelta(seconds=60),
                started=0.0,
                before_login=before,
                after_login=before,
            )
        except verifier.AcceptanceFailure as error:
            failure_code = error.code
            diagnostic = str(error)
    captured = capsys.readouterr()
    diagnostics_private_free = all(
        value not in (diagnostic or "") + captured.out + captured.err for value in private
    )
    return (
        failure_code,
        diagnostic,
        proof.responses_checked,
        proof.native.ttl_elapsed,
        requests_seen,
        raw_omits_private,
        diagnostics_private_free,
    )


@pytest.mark.parametrize("reflected_status", [200, 401], ids=["polling200", "final401"])
@pytest.mark.parametrize("private_kind", ["token", "owner", "database"])
def test_actual_expiry_poll_rejects_decoded_private_reflection_without_unsafe_increment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    reflected_status: int,
    private_kind: str,
) -> None:
    code, diagnostic, checked, elapsed, requests, raw_safe, diagnostics_safe = (
        unit_only_polling_result(
            monkeypatch,
            capsys,
            tmp_path,
            reflected_status=reflected_status,
            private_kind=private_kind,
        )
    )
    assert raw_safe and diagnostics_safe
    assert code == "TTL_FAILED"
    assert diagnostic == "TTL_FAILED"
    assert checked == (0 if reflected_status == 200 else 1)
    assert elapsed is None
    assert requests == (1 if reflected_status == 200 else 2)


def test_actual_expiry_poll_safe_200_then_401_control_uses_only_fake_time_and_http(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    code, diagnostic, checked, elapsed, requests, raw_safe, diagnostics_safe = (
        unit_only_polling_result(monkeypatch, capsys, tmp_path)
    )
    assert code is None and diagnostic is None
    assert checked == 2 and requests == 2
    assert elapsed == 60.0
    assert raw_safe and diagnostics_safe
