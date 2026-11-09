"""Offline #194 acceptance-tool tests; all corpus/lifecycle data here is handcrafted.

Native-looking revision/provenance fields below are validator unit inputs, NOT
actual TCP capture or release evidence. No child process or native database is
started. Assertions never format a bearer, raw body or parser exception.
"""

import copy
import hashlib
import json
import secrets
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from ai.risk.contract import (
    LIMITATION_CODE,
    LIMITATION_MESSAGE,
    educational_explanation,
    evaluate_risk_contract,
)
from ai.risk.scoring import RiskScoringEngine

import verify_s2_manual_portfolio as portfolio
import verify_s2_saved_risk as verifier
from app.core.responses import APIResponse
from app.schemas.local_risk import LocalRiskDraft, LocalRiskQuestionnaire, LocalSavedRiskAssessment
from verify_s1_application import CONTRACT_VERSION, ROOT, SCOPE, AcceptanceFailure

SHA, TREE = "a" * 40, "b" * 40
TIME = "2026-10-11T12:00:00+00:00"
SOURCE = [{"path": "backend/app/main.py", "sha256": "c" * 64}]
REQUIRED_CHECKS = (
    "disabled_prebody_no_database",
    "missing_bearer_no_database",
    "current_s1_prerequisites",
    "ordered_ten_question_contract",
    "owned_partial_draft",
    "saved_numeric_rules_snapshot",
    "original_equivalent_replay",
    "conflict_unchanged_history",
    "owner_scoped_history_detail",
    "empty_draft_preserves_history",
    "first_native_restart",
    "bounded_stable_cursor",
    "withdrawal_reacceptance_gate",
    "durable_session_logout",
    "second_native_restart",
    "safe_wire_without_credentials",
    "complete_safe_wire_corpus",
    "owned_cleanup",
)
CASE_SPECS = (
    ("questionnaire", "questionnaire", 200, None),
    ("draft_initial", "draft_get", 200, None),
    ("draft_partial_saved", "draft_put", 200, None),
    ("draft_partial_resumed", "draft_get", 200, None),
    ("history_initial", "history", 200, None),
    ("assessment_created", "assessment_create", 200, None),
    ("assessment_equivalent_replay", "assessment_create", 200, None),
    ("assessment_detail", "assessment_detail", 200, None),
    ("history_single", "history", 200, None),
    ("other_owner_history_empty", "history", 200, None),
    ("draft_cleared", "draft_put", 200, None),
    ("draft_after_restart", "draft_get", 200, None),
    ("assessment_after_restart", "assessment_detail", 200, None),
    ("assessment_aggressive", "assessment_create", 200, None),
    ("assessment_conservative", "assessment_create", 200, None),
    ("history_page_first", "history", 200, None),
    ("assessment_inserted_between_pages", "assessment_create", 200, None),
    ("history_page_next", "history", 200, None),
    ("history_after_relogin", "history", 200, None),
    ("idempotency_conflict", "assessment_create", 409, "IDEMPOTENCY_CONFLICT"),
    ("assessment_other_owner", "assessment_detail", 404, "RISK_ASSESSMENT_NOT_FOUND"),
    ("assessment_missing", "assessment_detail", 404, "RISK_ASSESSMENT_NOT_FOUND"),
    ("onboarding_withdrawn", "history", 409, "ONBOARDING_REQUIRED"),
    ("onboarding_reaccepted", "history", 409, "ONBOARDING_REQUIRED"),
    ("session_invalid", "draft_get", 401, "SESSION_INVALID"),
    ("session_restart_invalid", "history", 401, "SESSION_INVALID"),
    ("unsupported_version", "draft_put", 400, "UNSUPPORTED_QUESTIONNAIRE_VERSION"),
    ("missing_required_question", "assessment_create", 400, "MISSING_REQUIRED_QUESTION"),
    ("validation_error", "assessment_create", 422, "VALIDATION_ERROR"),
)
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


def success_body(data: dict, *, identifier: str = "unit-control") -> dict:
    asof = data.get("created_at", data.get("updated_at"))
    return {
        "success": True,
        "message": "Unit-only synthetic — response",
        "data": data,
        "meta": {
            "apiVersion": "v1",
            "dataStatus": "CACHED",
            "dataAsOf": asof,
            "correlationId": identifier,
        },
    }


def draft(answers: list | None = None, updated: str | None = None) -> dict:
    return LocalRiskDraft(answers=answers or [], updated_at=updated).model_dump(mode="json")


def error_bytes(status: int, code: str) -> bytes:
    return APIResponse.error(
        "Unit-only synthetic failure", code, status_code=status, correlation_id="unit-error"
    ).body


def install_wire(proof: verifier.SavedRiskProof, raw: bytes, status: int = 200) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=raw, headers={"Content-Type": "application/json"})

    client = httpx.Client(transport=httpx.MockTransport(respond), base_url="http://127.0.0.1")
    # A mock client only; NativeProof.start/login are never invoked.
    proof.native = SimpleNamespace(current_client=lambda: client, tokens=set(), servers=[])


def saved_records() -> tuple[dict, dict[str, dict]]:
    snapshot = json.loads(
        (ROOT / "backend/data/questionnaire/risk_questionnaire_v1.json").read_text("utf-8")
    )
    engine = RiskScoringEngine.from_config(snapshot)
    rules_hash = hashlib.sha256(
        json.dumps(
            snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()
    records = {}
    for index, letter in enumerate(("C", "E", "A", "D")):
        calculated = f"2026-10-11T12:00:0{index}+00:00"
        result = evaluate_risk_contract(
            verifier.risk_input(letter), engine=engine, calculated_at=calculated
        )
        result.setdefault("informational_tension", None)
        record = LocalSavedRiskAssessment.model_validate(
            {
                "assessment_id": f"00000000-0000-4000-8000-{190 + index:012d}",
                "created_at": calculated,
                "input": verifier.risk_input(letter),
                "assessment": result,
                "explanation": educational_explanation(result),
                "rules_sha256": rules_hash,
                "rules_snapshot": snapshot,
            },
            strict=True,
        )
        records[letter] = record.model_dump(mode="json")
    questionnaire = LocalRiskQuestionnaire.model_validate(
        {
            "questions": [
                {
                    "question_id": question["question_id"],
                    "dimension": question["dimension"],
                    "text": question["text"],
                    "options": [
                        {"code": option["code"], "label": option["label"]}
                        for option in question["answers"]
                    ],
                }
                for question in snapshot["questions"]
            ],
            "rules_sha256": rules_hash,
            "limitation": {"code": LIMITATION_CODE, "message": LIMITATION_MESSAGE},
        },
        strict=True,
    ).model_dump(mode="json")
    return questionnaire, records


def corpus_fixture() -> dict:
    """Handcrafted validator input with fake revisions; never a native capture."""
    questionnaire, saved = saved_records()
    partial = verifier.risk_input(partial=True)
    empty = {**verifier.risk_input(), "answers": []}
    cleared = draft([], "2026-10-11T12:00:00.500000+00:00")
    key = "00000000-0000-4000-8000-000000000194"
    cases = []
    for identifier, operation, status, code in CASE_SPECS:
        target, request = None, None
        if operation == "history":
            target = {"limit": 2, "before": "2" if identifier == "history_page_next" else None}
        elif operation == "assessment_detail":
            target = {
                "assessment_id": (
                    "00000000-0000-4000-8000-000000000999"
                    if identifier == "assessment_missing"
                    else saved["C"]["assessment_id"]
                )
            }
        if code is not None:
            raw = error_bytes(status, code).decode("utf-8")
            expected = {"outcome": "error", "error_code": code}
        else:
            if operation == "questionnaire":
                data = questionnaire
            elif operation in {"draft_get", "draft_put"}:
                data = (
                    draft()
                    if identifier == "draft_initial"
                    else cleared
                    if identifier in {"draft_cleared", "draft_after_restart"}
                    else draft(partial["answers"], TIME)
                )
                if operation == "draft_put":
                    request = empty if identifier == "draft_cleared" else partial
            elif operation == "history":
                items = (
                    []
                    if identifier in {"history_initial", "other_owner_history_empty"}
                    else [saved["A"], saved["E"]]
                    if identifier == "history_page_first"
                    else [saved["D"], saved["A"]]
                    if identifier == "history_after_relogin"
                    else [saved["C"]]
                )
                data = {
                    "scope": SCOPE,
                    "contract_version": CONTRACT_VERSION,
                    "items": items,
                    "next_cursor": "2"
                    if identifier == "history_page_first"
                    else "3"
                    if identifier == "history_after_relogin"
                    else None,
                }
            else:
                letter = {
                    "assessment_aggressive": "E",
                    "assessment_conservative": "A",
                    "assessment_inserted_between_pages": "D",
                }.get(identifier, "C")
                data = saved[letter]
                if operation == "assessment_create":
                    request = {
                        **verifier.risk_input(letter),
                        "idempotency_key": key
                        if letter == "C"
                        else f"00000000-0000-4000-8000-{195 + ('E', 'A', 'D').index(letter):012d}",
                    }
                    if identifier == "assessment_equivalent_replay":
                        request["answers"] = list(reversed(request["answers"]))
            raw = json.dumps(success_body(data, identifier=identifier), ensure_ascii=False)
            expected = {"outcome": "success"}
        cases.append(
            {
                "id": identifier,
                "operation": operation,
                "target": target,
                "request": copy.deepcopy(request),
                "status": status,
                "content_type": "application/json",
                "body_utf8": raw,
                "expected": expected,
            }
        )
    return {
        "schema_version": "finex.local_s2.saved_risk_corpus.v1",
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "provenance": {
            "kind": "native_tcp_capture",
            "source": "owned_loopback_uvicorn",
            "command": "python verify_s2_saved_risk.py",
            "tested_commit": SHA,
            "tested_tree": TREE,
        },
        "source_hashes": copy.deepcopy(SOURCE),
        "source_manifest_sha256": portfolio.manifest_sha256(SOURCE),
        "cases": cases,
    }


def test_complete_handcrafted_29_case_validator_input_is_accepted_without_mutation() -> None:
    corpus = corpus_fixture()
    before = copy.deepcopy(corpus)
    verifier.validate_corpus(corpus)
    assert len(corpus["cases"]) == 29 and corpus == before


def test_required_checks_preserve_all_legacy_checks_and_add_complete_corpus() -> None:
    assert tuple(verifier.REQUIRED_CHECKS) == REQUIRED_CHECKS


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_case",
        "duplicate_case",
        "extra_case",
        "wrong_operation",
        "wrong_status",
        "mislabelled_error",
        "missing_target",
        "bad_cursor",
        "wrong_cursor",
        "limit1",
        "unbounded_history",
        "wrong_scope",
        "wrong_meta",
        "missing_nullable",
        "naive_time",
        "owner_field",
        "credential_field",
        "private_path",
        "manifest",
        "source_path",
        "raw_duplicate_key",
        "error_missing_detail",
        "replay_changed_document",
    ],
)
def test_handcrafted_corpus_drift_is_rejected_safely(mutation: str) -> None:
    corpus = corpus_fixture()
    item = next(case for case in corpus["cases"] if case["id"] == "draft_partial_saved")
    body = json.loads(item["body_utf8"])
    if mutation == "missing_case":
        corpus["cases"].pop()
    elif mutation == "duplicate_case":
        corpus["cases"][-1] = copy.deepcopy(corpus["cases"][0])
    elif mutation == "extra_case":
        corpus["cases"].append({**corpus["cases"][0], "id": "unapproved"})
    elif mutation == "wrong_operation":
        item["operation"] = "history"
    elif mutation == "wrong_status":
        item["status"] = 201
    elif mutation == "mislabelled_error":
        corpus["cases"][-1]["expected"]["error_code"] = "IDEMPOTENCY_CONFLICT"
    elif mutation == "missing_target":
        del corpus["cases"][0]["target"]
    elif mutation in {"bad_cursor", "wrong_cursor", "limit1"}:
        page = next(case for case in corpus["cases"] if case["id"] == "history_page_next")
        if mutation == "limit1":
            page["target"]["limit"] = 1
        else:
            page["target"]["before"] = "9223372036854775808" if mutation == "bad_cursor" else "9"
    elif mutation == "unbounded_history":
        page = next(case for case in corpus["cases"] if case["id"] == "history_page_first")
        page_body = json.loads(page["body_utf8"])
        page_body["data"]["items"].append(copy.deepcopy(page_body["data"]["items"][0]))
        page["body_utf8"] = json.dumps(page_body)
    elif mutation == "manifest":
        corpus["source_manifest_sha256"] = "d" * 64
    elif mutation == "source_path":
        corpus["source_hashes"][0]["path"] = "../private"
    elif mutation == "raw_duplicate_key":
        item["body_utf8"] = item["body_utf8"].replace(
            '"success": true', '"success": false, "success": true'
        )
    elif mutation == "error_missing_detail":
        error = corpus["cases"][-1]
        content = json.loads(error["body_utf8"])
        del content["detail"]
        error["body_utf8"] = json.dumps(content)
    elif mutation == "replay_changed_document":
        replay = next(
            case for case in corpus["cases"] if case["id"] == "assessment_equivalent_replay"
        )
        content = json.loads(replay["body_utf8"])
        content["data"]["created_at"] = "2026-10-11T12:00:01+00:00"
        replay["body_utf8"] = json.dumps(content)
    else:
        if mutation == "wrong_scope":
            body["data"]["scope"] = "local_educational_pilot"
        elif mutation == "wrong_meta":
            body["meta"]["apiVersion"] = "v0"
        elif mutation == "missing_nullable":
            del body["data"]["updated_at"]
        elif mutation == "naive_time":
            body["data"]["updated_at"] = "2026-10-11T12:00:00"
        elif mutation == "owner_field":
            body["data"]["user_id"] = "synthetic-unit-private-owner"
        elif mutation == "credential_field":
            body["data"]["authorization"] = "synthetic-unit-private-credential"
        elif mutation == "private_path":
            body["data"]["database"] = "synthetic-unit-private-path"
        item["body_utf8"] = json.dumps(body)
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus)


@pytest.mark.parametrize(
    "mutation",
    [
        "api_version",
        "missing_correlation",
        "unsafe_correlation",
        "extra_meta",
        "extra_root",
        "missing_nullable",
        "naive_time",
        "private_owner",
        "private_path",
        "duplicate_json_key",
    ],
)
def test_existing_wire_requires_strict_public_dto_and_metadata(
    tmp_path: Path, mutation: str
) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    body = success_body(draft())
    if mutation == "api_version":
        body["meta"]["apiVersion"] = "v0"
    elif mutation == "missing_correlation":
        del body["meta"]["correlationId"]
    elif mutation == "unsafe_correlation":
        body["meta"]["correlationId"] = "unit unsafe correlation"
    elif mutation == "extra_meta":
        body["meta"]["unapproved"] = True
    elif mutation == "extra_root":
        body["unapproved"] = True
    elif mutation == "missing_nullable":
        del body["data"]["updated_at"]
    elif mutation == "naive_time":
        body["data"]["updated_at"] = "2026-10-11T12:00:00"
        body["meta"]["dataAsOf"] = body["data"]["updated_at"]
    elif mutation == "private_owner":
        body["data"]["user_id"] = "synthetic-private-owner"
    elif mutation == "private_path":
        body["data"]["database"] = "synthetic-private-path"
    raw = json.dumps(body, ensure_ascii=False).encode()
    if mutation == "duplicate_json_key":
        raw = raw.replace(b'"success": true', b'"success": false, "success": true')
    install_wire(proof, raw)
    with pytest.raises(AcceptanceFailure, match="WIRE_INVALID"):
        proof.request("GET", "/draft", None)


@pytest.mark.parametrize(
    "mutation",
    ["missing_detail", "divergent_detail", "extra_error", "wrong_operation", "wrong_status"],
)
def test_existing_wire_rejects_contradictory_actual_error_envelopes(
    tmp_path: Path, mutation: str
) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    status, code = (
        (409, "HOLDING_ALREADY_EXISTS")
        if mutation == "wrong_operation"
        else (401, "SESSION_INVALID")
    )
    body = json.loads(error_bytes(status, code))
    if mutation == "missing_detail":
        del body["detail"]
    elif mutation == "divergent_detail":
        body["detail"] = "different safe unit message"
    elif mutation == "extra_error":
        body["error"]["unexpected"] = True
    elif mutation == "wrong_status":
        status = 409
    install_wire(proof, json.dumps(body).encode(), status)
    with pytest.raises(AcceptanceFailure, match="WIRE_INVALID"):
        proof.request("GET", "/draft", None, status=status, code=code)


@pytest.mark.parametrize("padding,allowed", [(200000, True), (270000, False)])
def test_wire_client_byte_cap_is_enforced_without_trimming(
    tmp_path: Path, padding: int, allowed: bool
) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    body = success_body(draft())
    # Padding is legal JSON whitespace, not an oversized DTO field.
    raw = json.dumps(body).encode() + b" " * padding
    install_wire(proof, raw)
    if allowed:
        assert proof.request("GET", "/draft", None) == body["data"]
    else:
        with pytest.raises(AcceptanceFailure, match="WIRE_INVALID"):
            proof.request("GET", "/draft", None)


def test_capture_keeps_exact_original_utf8_and_no_request_headers(tmp_path: Path) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    raw = (json.dumps(success_body(draft()), ensure_ascii=False, indent=1) + "\n").encode()
    install_wire(proof, raw)
    token = secrets.token_urlsafe(32)
    proof.native.tokens.add(token)
    proof.request("GET", "/draft", token, case_id="draft_initial")
    captured = proof.cases.get("draft_initial")
    matches = captured is not None and captured == {
        "id": "draft_initial",
        "operation": "draft_get",
        "target": None,
        "request": None,
        "status": 200,
        "content_type": "application/json",
        "body_utf8": raw.decode(),
        "expected": {"outcome": "success"},
    }
    assert matches


def escaped_reflection(body: dict, value: str, *, nested: bool) -> bytes:
    """Synthetic values are deliberately escaped; no diagnostic prints their bytes."""
    marker = "unit-private-reflection-marker"
    if nested:
        body["error"]["fieldErrors"] = [{"field": marker, "code": "unit-only"}]
    else:
        body["message"] = marker
    escaped = "".join(f"\\u{ord(character):04x}" for character in value)
    return (
        json.dumps(body, ensure_ascii=False)
        .encode("utf-8")
        .replace(marker.encode("ascii"), escaped.encode("ascii"))
    )


@pytest.mark.parametrize("kind", ["token", "owner", "database"])
@pytest.mark.parametrize("nested", [False, True], ids=["message", "nested-error"])
def test_capture_rejects_json_escaped_known_private_values(
    tmp_path: Path, kind: str, nested: bool
) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    value = (
        secrets.token_urlsafe(32)
        if kind == "token"
        else "00000000-0000-4000-8000-000000000999"
        if kind == "owner"
        else str(proof.database)
    )
    body = json.loads(error_bytes(401, "SESSION_INVALID")) if nested else success_body(draft())
    raw = escaped_reflection(body, value, nested=nested)
    install_wire(proof, raw, status=401 if nested else 200)
    if kind == "token":
        proof.native.tokens.add(value)
    elif kind == "owner":
        proof.private_identities.add(value)
    try:
        proof.request(
            "GET",
            "/draft",
            value if kind == "token" else None,
            status=401 if nested else 200,
            code="SESSION_INVALID" if nested else None,
            case_id="session_invalid" if nested else "draft_initial",
        )
    except AcceptanceFailure as error:
        safely_rejected = error.code in {"WIRE_INVALID", "TOKEN_REFLECTION"}
    else:
        safely_rejected = False
    assert safely_rejected
    assert proof.cases == {} and proof.responses_checked == 0


@pytest.mark.parametrize("kind", ["token", "owner", "database"])
@pytest.mark.parametrize("nested", [False, True], ids=["message", "nested-error"])
def test_corpus_rejects_json_escaped_known_private_values(kind: str, nested: bool) -> None:
    value = (
        secrets.token_urlsafe(32)
        if kind == "token"
        else "00000000-0000-4000-8000-000000000998"
        if kind == "owner"
        else "C:/unit-only/private-database.sqlite3"
    )
    corpus = corpus_fixture()
    item = next(
        row
        for row in corpus["cases"]
        if row["id"] == ("session_invalid" if nested else "draft_initial")
    )
    body = json.loads(item["body_utf8"])
    item["body_utf8"] = escaped_reflection(body, value, nested=nested).decode("utf-8")
    try:
        verifier.validate_corpus(corpus, forbidden=(value,))
    except AcceptanceFailure as error:
        safely_rejected = error.code == "CORPUS_INVALID"
    else:
        safely_rejected = False
    assert safely_rejected


def test_nonsecret_escaped_unicode_keeps_original_capture_bytes(tmp_path: Path) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    body = success_body(draft())
    body["message"] = "Synthetic — π / 1–3 years"
    raw = json.dumps(body, ensure_ascii=True).encode("utf-8")
    install_wire(proof, raw)
    proof.request("GET", "/draft", None, case_id="draft_initial")
    matches = proof.cases["draft_initial"]["body_utf8"].encode("utf-8") == raw
    assert matches


def test_capture_snapshots_the_requested_draft_before_caller_mutation(tmp_path: Path) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    payload = verifier.risk_input(partial=True)
    original = copy.deepcopy(payload)
    raw = json.dumps(success_body(draft(payload["answers"], TIME))).encode()
    install_wire(proof, raw)
    proof.request("PUT", "/draft", None, payload, case_id="draft_partial_saved")
    payload["answers"].clear()
    captured = proof.cases.get("draft_partial_saved")
    matches = captured is not None and captured["request"] == original
    assert matches


def test_capture_drops_illegal_error_request_instead_of_claiming_typed_emission(
    tmp_path: Path,
) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    raw = error_bytes(422, "VALIDATION_ERROR")
    install_wire(proof, raw, 422)
    illegal = {**verifier.risk_input(), "idempotency_key": "synthetic-invalid-key"}
    proof.request(
        "POST",
        "/assessments",
        None,
        illegal,
        status=422,
        code="VALIDATION_ERROR",
        case_id="validation_error",
    )
    captured = proof.cases.get("validation_error")
    matches = (
        captured is not None
        and captured["request"] is None
        and captured["body_utf8"] == raw.decode()
    )
    assert matches


@pytest.mark.parametrize(
    "suffix", ["/assessments", "/assessments?limit=1", "/assessments?limit=20"]
)
def test_history_capture_cannot_certify_a_different_public_method_query(
    tmp_path: Path, suffix: str
) -> None:
    proof = verifier.SavedRiskProof(tmp_path / "unused-unit-database.sqlite3")
    data = {"scope": SCOPE, "contract_version": CONTRACT_VERSION, "items": [], "next_cursor": None}
    install_wire(proof, json.dumps(success_body(data)).encode())
    with pytest.raises(AcceptanceFailure):
        proof.request("GET", suffix, None, case_id="history_initial")


def fake_completed_lifecycle(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, drift: str | None = None
) -> None:
    """Mock lifecycle guard proof only; never starts processes or a real DB."""
    stopped = []
    monkeypatch.setattr(verifier, "_temp_base", lambda: tmp_path.resolve())
    monkeypatch.setattr(
        verifier,
        "repository_provenance",
        lambda *_: {
            "tested_commit": SHA,
            "tested_tree": TREE,
            "working_tree_dirty": False,
            "tracked_dirty": False,
            "source_hashes": copy.deepcopy(SOURCE),
        },
    )
    monkeypatch.setattr(
        verifier,
        "runtime_hashes",
        lambda: (
            [{"path": "backend/app/main.py", "sha256": "d" * 64}]
            if drift == "source" and stopped
            else copy.deepcopy(SOURCE)
        ),
    )

    def git(arguments: list[str]) -> str:
        if arguments == ["rev-parse", "HEAD"]:
            return "e" * 40 if drift == "head" and stopped else SHA
        if arguments == ["rev-parse", "HEAD^{tree}"]:
            return "f" * 40 if drift == "tree" and stopped else TREE
        return "unit dirty source" if drift == "dirty" and stopped else ""

    monkeypatch.setattr(verifier, "_git", git)

    class Server:
        def __init__(self, pid: int) -> None:
            self.process = SimpleNamespace(pid=pid)
            self.reaped = False

        def stop(self) -> None:
            self.reaped = True
            stopped.append(self.process.pid)

    class Proof:
        def __init__(self, database: Path) -> None:
            self.database = database
            self.native = SimpleNamespace(
                servers=[Server(pid) for pid in range(1, 5)], tokens=set()
            )
            self.responses_checked = 100
            self.private_identities: set[str] = set()
            self.checks = [
                {"id": identifier, "passed": True}
                for identifier in verifier.REQUIRED_CHECKS
                if identifier != "owned_cleanup"
            ]
            self.cases = {case["id"]: case for case in corpus_fixture()["cases"]}
            database.write_bytes(b"unit-only disposable data")
            database.with_name("state.sqlite3-wal").write_bytes(b"unit-only sidecar")

        def run(self) -> None:
            pass

        def mark(self, identifier: str) -> None:
            self.checks.append({"id": identifier, "passed": True})

    monkeypatch.setattr(verifier, "SavedRiskProof", Proof)


def report_from(result: object) -> dict:
    # Supports legacy report-only API while the test-first new corpus API is absent.
    return result[0] if isinstance(result, tuple) else result


def test_completed_mock_report_contains_the_frozen_digest_and_cleanup_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_completed_lifecycle(monkeypatch, tmp_path)
    report = report_from(verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE))
    assert report["success"] is True
    assert set(report) == REPORT_FIELDS
    assert report["source_manifest_sha256"] == portfolio.manifest_sha256(SOURCE)
    assert report["corpus_case_ids"] == [item[0] for item in CASE_SPECS]
    assert report["native_process"] == {
        "starts": 4,
        "application_restarts": 2,
        "owned_pids": [1, 2, 3, 4],
        "child_reaped": True,
        "temporary_directory_removed": True,
        "session_ttl_minutes": 1,
        "real_expiry_elapsed_seconds": None,
        "shutdown": "owned_terminate_and_reap",
    }
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("drift", ["source", "head", "tree", "dirty"])
def test_change_during_owned_cleanup_cannot_certify_earlier_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    fake_completed_lifecycle(monkeypatch, tmp_path, drift=drift)
    report = report_from(verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE))
    assert report["success"] is False
    assert report["failures"] == [{"code": "SOURCE_CHANGED"}]
    assert report.get("corpus_sha256") is None and report.get("corpus_case_ids", []) == []
    assert list(tmp_path.iterdir()) == []


def test_cli_rejects_inside_checkout_output_before_evaluating(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    # Isolated synthetic source directory, not a write into the user's checkout.
    checkout = tmp_path / "synthetic-checkout"
    checkout.mkdir()
    monkeypatch.setattr(verifier, "ROOT", checkout)
    evaluated = []
    monkeypatch.setattr(
        verifier, "evaluate_acceptance", lambda **_: evaluated.append(True) or {"success": True}
    )
    result = verifier.main(
        ["--tested-sha", SHA, "--tested-tree", TREE, "--report", str(checkout / "proof.json")]
    )
    capsys.readouterr()
    assert result == 1 and not evaluated and not (checkout / "proof.json").exists()


def test_cli_does_not_certify_success_without_requested_corpus_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    fake_completed_lifecycle(monkeypatch, tmp_path)
    destination = tmp_path / "unit-only-corpus.json"
    result = verifier.main(
        ["--tested-sha", SHA, "--tested-tree", TREE, "--corpus", str(destination)]
    )
    capsys.readouterr()
    assert result == 0 and destination.is_file()
    value = json.loads(destination.read_bytes())
    assert value["schema_version"] == "finex.local_s2.saved_risk_corpus.v1"
