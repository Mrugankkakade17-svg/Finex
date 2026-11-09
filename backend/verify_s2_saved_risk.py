"""Fail-closed native TCP proof of owned saved risk, not overall S2 acceptance.

Reuse the reviewed S1 child lifecycle: isolated environment, port-zero socket,
PID/nonce handshake, disposable database, bounded diagnostics and owned cleanup.
No external URL, credential, developer database or cloud provider is accepted.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn
from uuid import uuid4

import httpx
from ai.risk.contract import (
    LIMITATION_CODE,
    LIMITATION_MESSAGE,
    educational_explanation,
    evaluate_risk_contract,
)
from ai.risk.scoring import RiskScoringEngine
from pydantic import BaseModel

from app.schemas.local_risk import (
    LocalRiskDraft,
    LocalRiskHistory,
    LocalRiskInput,
    LocalRiskQuestionnaire,
    LocalRiskSubmitRequest,
    LocalSavedRiskAssessment,
)
from local_s2_evidence import (
    json_bytes,
    loads,
    manifest_sha256,
    output_target,
    private,
    reflects_private,
    safe_object,
    write_new_json,
)
from local_s2_evidence import (
    runtime_hashes as s2_runtime_hashes,
)
from verify_s1_application import (
    CID_PATTERN,
    COMPLETE_REQUEST,
    CONSENT_REQUEST,
    CONTRACT_VERSION,
    PROFILE_REQUEST,
    ROOT,
    SCOPE,
    SHA_PATTERN,
    AcceptanceFailure,
    NativeProof,
    _forbidden_keys,
    _git,
    _require,
    _temp_base,
    _utc,
    repository_provenance,
    source_hashes,
)

RISK = "/api/v1/local-risk"
COMMAND = "python verify_s2_saved_risk.py"
CORPUS_SCHEMA = "finex.local_s2.saved_risk_corpus.v1"
REPORT_SCHEMA = "finex.local_s2.saved_risk.acceptance.v1"
MAX_BODY = 262144
MAX_CORPUS = 2097152
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
QUESTION_IDS = [f"{dimension}{number}" for dimension in ("W", "C") for number in range(1, 6)]
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
CASE_IDS = tuple(item[0] for item in CASE_SPECS)
CASE_MAP = {item[0]: item[1:] for item in CASE_SPECS}
INPUT_ERRORS = {
    "MALFORMED_ANSWER",
    "UNSUPPORTED_QUESTIONNAIRE_VERSION",
    "DUPLICATE_QUESTION_ANSWER",
    "UNKNOWN_QUESTION_ID",
    "INVALID_ANSWER_CODE",
    "ANSWER_NOT_PERMITTED_FOR_QUESTION",
}


def _cursor(value: object) -> None:
    _require(
        isinstance(value, str)
        and bool(re.fullmatch(r"[1-9][0-9]{0,18}", value, re.ASCII))
        and int(value) <= 9223372036854775807,
        "WIRE_INVALID",
    )


def _route(method: str, suffix: str, *, capture: bool = False) -> tuple[str, object, int]:
    if (method, suffix) == ("GET", "/questionnaire"):
        return "questionnaire", None, 0
    if suffix == "/draft" and method in ("GET", "PUT"):
        return "draft_get" if method == "GET" else "draft_put", None, 0
    if (method, suffix) == ("POST", "/assessments"):
        return "assessment_create", None, 0
    detail = re.fullmatch(r"/assessments/([^/?#]+)", suffix)
    if method == "GET" and detail is not None:
        identifier = detail[1]
        _require(bool(UUID_PATTERN.fullmatch(identifier)), "WIRE_INVALID")
        return "assessment_detail", {"assessment_id": identifier}, 0
    history = re.fullmatch(
        r"/assessments(?:\?limit=([1-9]|[1-4][0-9]|50)(?:&before=([1-9][0-9]{0,18}))?)?",
        suffix,
    )
    _require(method == "GET" and history is not None, "WIRE_INVALID")
    if history is None:
        raise AcceptanceFailure("WIRE_INVALID")
    limit = int(history[1]) if history[1] is not None else 20
    before = history[2]
    if before is not None:
        _cursor(before)
    _require(not capture or (history[1] == "2" and limit == 2), "WIRE_INVALID")
    return "history", {"limit": limit, "before": before}, limit


def _dto(model: type[BaseModel], value: object) -> dict[str, Any]:
    data = safe_object(value, set(model.model_fields))
    parsed = model.model_validate(data, strict=True)
    # Defaults must never make a missing nullable/nested field appear present.
    _require(parsed.model_dump(mode="json") == data, "WIRE_INVALID")
    return data


def _answers(value: object, *, complete: bool = False) -> dict[str, str]:
    if not isinstance(value, list) or len(value) > 10:
        raise AcceptanceFailure("WIRE_INVALID")
    result: dict[str, str] = {}
    for item in value:
        answer = safe_object(item, {"question_id", "answer_code"})
        qid, code = answer["question_id"], answer["answer_code"]
        _require(
            isinstance(qid, str)
            and qid in QUESTION_IDS
            and qid not in result
            and isinstance(code, str)
            and code in {f"{qid}_{letter}" for letter in "ABCDE"},
            "WIRE_INVALID",
        )
        result[qid] = code
    _require(not complete or set(result) == set(QUESTION_IDS), "WIRE_INVALID")
    return result


def _input(value: object, *, submit: bool = False) -> dict[str, Any]:
    data = _dto(LocalRiskSubmitRequest if submit else LocalRiskInput, value)
    _require(
        data["questionnaire_id"] == "risk_questionnaire_v1"
        and data["questionnaire_version"] == "v1"
        and not private(data),
        "WIRE_INVALID",
    )
    _answers(data["answers"], complete=submit)
    return data


def _assessment(value: object) -> dict[str, Any]:
    data = _dto(LocalSavedRiskAssessment, value)
    _require(type(data["persisted"]) is bool and data["persisted"] is True, "WIRE_INVALID")
    _input(data["input"])
    _answers(data["input"]["answers"], complete=True)
    created = _utc(data["created_at"])
    calculated = data["assessment"]["calculated_at"]
    _require(_utc(calculated) == created, "WIRE_INVALID")
    rules = json.dumps(
        data["rules_snapshot"],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    _require(
        len(rules) <= 65536 and hashlib.sha256(rules).hexdigest() == data["rules_sha256"],
        "WIRE_INVALID",
    )
    engine = RiskScoringEngine.from_config(data["rules_snapshot"])
    expected = evaluate_risk_contract(data["input"], engine=engine, calculated_at=calculated)
    expected.setdefault("informational_tension", None)
    _require(
        data["assessment"] == expected and data["explanation"] == educational_explanation(expected),
        "WIRE_INVALID",
    )
    return data


def _data(operation: str, value: object, *, limit: int = 2) -> dict[str, Any]:
    if operation == "questionnaire":
        data = _dto(LocalRiskQuestionnaire, value)
        _require(
            [item["question_id"] for item in data["questions"]] == QUESTION_IDS
            and data["limitation"] == {"code": LIMITATION_CODE, "message": LIMITATION_MESSAGE},
            "WIRE_INVALID",
        )
        for item in data["questions"]:
            qid = item["question_id"]
            _require(
                item["dimension"] == ("willingness" if qid.startswith("W") else "capacity")
                and isinstance(item["text"], str)
                and bool(item["text"].strip())
                and [option["code"] for option in item["options"]]
                == [f"{qid}_{letter}" for letter in "ABCDE"]
                and all(
                    isinstance(option["label"], str) and bool(option["label"].strip())
                    for option in item["options"]
                ),
                "WIRE_INVALID",
            )
        return data
    if operation in ("draft_get", "draft_put"):
        data = _dto(LocalRiskDraft, value)
        _answers(data["answers"])
        if data["updated_at"] is not None:
            _utc(data["updated_at"])
        _require(not data["answers"] or data["updated_at"] is not None, "WIRE_INVALID")
        return data
    if operation == "history":
        data = _dto(LocalRiskHistory, value)
        _require(len(data["items"]) <= limit, "WIRE_INVALID")
        identifiers: list[str] = []
        for item in data["items"]:
            identifiers.append(_assessment(item)["assessment_id"])
        _require(len(set(identifiers)) == len(identifiers), "WIRE_INVALID")
        if data["next_cursor"] is not None:
            _cursor(data["next_cursor"])
            _require(len(data["items"]) == limit, "WIRE_INVALID")
        return data
    if operation in ("assessment_create", "assessment_detail"):
        return _assessment(value)
    raise AcceptanceFailure("WIRE_INVALID")


def _error_status(operation: str, code: str) -> int | None:
    common = {
        "SESSION_INVALID": 401,
        "LOCAL_APPLICATION_ONLY": 403,
        "ONBOARDING_REQUIRED": 409,
        "VALIDATION_ERROR": 422,
        "LOCAL_STORE_UNAVAILABLE": 503,
        "RISK_ASSESSMENT_UNAVAILABLE": 503,
    }
    if code in common:
        return common[code]
    if operation in ("draft_put", "assessment_create") and code in INPUT_ERRORS:
        return 400
    if operation == "assessment_create":
        return {"MISSING_REQUIRED_QUESTION": 400, "IDEMPOTENCY_CONFLICT": 409}.get(code)
    return 404 if operation == "assessment_detail" and code == "RISK_ASSESSMENT_NOT_FOUND" else None


def _wire_body(
    raw: bytes,
    operation: str,
    status: int,
    code: str | None,
    *,
    limit: int = 2,
    forbidden: tuple[str, ...] = (),
) -> dict[str, Any]:
    _require(len(raw) <= MAX_BODY, "WIRE_INVALID")
    body = loads(raw)
    _require(
        not private(body) and not _forbidden_keys(body) and not reflects_private(body, forbidden),
        "WIRE_INVALID",
    )
    if code is not None:
        safe_object(body, {"success", "message", "detail", "error_code", "error"})
        error = safe_object(body["error"], {"code", "message", "fieldErrors", "correlationId"})
        _require(
            _error_status(operation, code) == status
            and body["success"] is False
            and body["error_code"] == error["code"] == code
            and isinstance(body["message"], str)
            and 1 <= len(body["message"]) <= 2000
            and body["detail"] == error["message"] == body["message"]
            and isinstance(error["correlationId"], str)
            and bool(CID_PATTERN.fullmatch(error["correlationId"]))
            and isinstance(error["fieldErrors"], list)
            and len(error["fieldErrors"]) <= 50,
            "WIRE_INVALID",
        )
        for value in error["fieldErrors"]:
            field = safe_object(value, {"field", "code"})
            _require(
                all(isinstance(item, str) and 1 <= len(item) <= 200 for item in field.values()),
                "WIRE_INVALID",
            )
        return body
    safe_object(body, {"success", "message", "data", "meta"})
    _require(
        body["success"] is True
        and status == 200
        and isinstance(body["message"], str)
        and 1 <= len(body["message"]) <= 2000,
        "WIRE_INVALID",
    )
    data = _data(operation, body["data"], limit=limit)
    meta = safe_object(body["meta"], {"apiVersion", "dataStatus", "dataAsOf", "correlationId"})
    _require(
        meta["apiVersion"] == "v1"
        and meta["dataStatus"] == "CACHED"
        and meta["dataAsOf"] == data.get("created_at", data.get("updated_at"))
        and isinstance(meta["correlationId"], str)
        and bool(CID_PATTERN.fullmatch(meta["correlationId"])),
        "WIRE_INVALID",
    )
    return data


def risk_input(letter: str = "C", *, partial: bool = False) -> dict[str, Any]:
    return {
        "questionnaire_id": "risk_questionnaire_v1",
        "questionnaire_version": "v1",
        "answers": [
            {"question_id": qid, "answer_code": f"{qid}_{letter}"}
            for qid in (QUESTION_IDS[:2] if partial else QUESTION_IDS)
        ],
    }


def runtime_hashes() -> list[dict[str, str]]:
    return s2_runtime_hashes(ROOT, source_hashes())


def _confirmation(operation: str, target: object, payload: object, data: dict[str, Any]) -> None:
    if operation in ("draft_put", "assessment_create"):
        requested = _input(payload, submit=operation == "assessment_create")
        confirmed = data["input"] if operation == "assessment_create" else data
        _require(
            requested["questionnaire_id"] == confirmed["questionnaire_id"]
            and requested["questionnaire_version"] == confirmed["questionnaire_version"]
            and _answers(requested["answers"]) == _answers(confirmed["answers"]),
            "WIRE_INVALID",
        )
        if operation == "draft_put":
            _require(data["updated_at"] is not None, "WIRE_INVALID")
        return
    _require(payload is None, "WIRE_INVALID")
    if operation == "assessment_detail":
        detail = safe_object(target, {"assessment_id"})
        _require(data["assessment_id"] == detail["assessment_id"], "WIRE_INVALID")


def _target(operation: str, target: object) -> None:
    if operation == "history":
        value = safe_object(target, {"limit", "before"})
        _require(type(value["limit"]) is int and value["limit"] == 2, "CORPUS_INVALID")
        if value["before"] is not None:
            _cursor(value["before"])
    elif operation == "assessment_detail":
        value = safe_object(target, {"assessment_id"})
        _require(
            isinstance(value["assessment_id"], str)
            and bool(UUID_PATTERN.fullmatch(value["assessment_id"])),
            "CORPUS_INVALID",
        )
    else:
        _require(target is None, "CORPUS_INVALID")


def _relationships(cases: dict[str, dict[str, Any]], data: dict[str, dict[str, Any]]) -> None:
    original = data["assessment_created"]
    replay = cases["assessment_equivalent_replay"]["request"]
    first_request = cases["assessment_created"]["request"]
    _require(
        original["input"] == risk_input()
        and replay["idempotency_key"] == first_request["idempotency_key"]
        and replay["answers"] == list(reversed(first_request["answers"]))
        and all(
            data[key] == original
            for key in (
                "assessment_equivalent_replay",
                "assessment_detail",
                "assessment_after_restart",
            )
        )
        and original["rules_sha256"] == data["questionnaire"]["rules_sha256"],
        "CORPUS_INVALID",
    )
    snapshot_questions = [
        {
            "question_id": item["question_id"],
            "dimension": item["dimension"],
            "text": item["text"],
            "options": [
                {"code": option["code"], "label": option["label"]} for option in item["answers"]
            ],
        }
        for item in original["rules_snapshot"]["questions"]
    ]
    _require(data["questionnaire"]["questions"] == snapshot_questions, "CORPUS_INVALID")
    initial, partial, cleared = (
        data["draft_initial"],
        data["draft_partial_saved"],
        data["draft_cleared"],
    )
    _require(
        initial["answers"] == []
        and initial["updated_at"] is None
        and partial["answers"] == risk_input(partial=True)["answers"]
        and data["draft_partial_resumed"] == partial
        and cleared["answers"] == []
        and cleared["updated_at"] is not None
        and data["draft_after_restart"] == cleared
        and _utc(cleared["updated_at"]) >= _utc(partial["updated_at"]),
        "CORPUS_INVALID",
    )
    records = [original]
    for key, letter in (
        ("assessment_aggressive", "E"),
        ("assessment_conservative", "A"),
        ("assessment_inserted_between_pages", "D"),
    ):
        record = data[key]
        _require(
            record["input"] == risk_input(letter)
            and record["rules_snapshot"] == original["rules_snapshot"]
            and record["rules_sha256"] == original["rules_sha256"]
            and _utc(record["created_at"]) >= _utc(records[-1]["created_at"]),
            "CORPUS_INVALID",
        )
        records.append(record)
    _require(len({record["assessment_id"] for record in records}) == 4, "CORPUS_INVALID")
    _require(
        len(
            {
                cases[key]["request"]["idempotency_key"]
                for key in (
                    "assessment_created",
                    "assessment_aggressive",
                    "assessment_conservative",
                    "assessment_inserted_between_pages",
                )
            }
        )
        == 4,
        "CORPUS_INVALID",
    )
    expected_pages = {
        "history_initial": [],
        "other_owner_history_empty": [],
        "history_single": [original],
        "history_page_first": [records[2], records[1]],
        "history_page_next": [original],
        "history_after_relogin": [records[3], records[2]],
    }
    for key, expected_items in expected_pages.items():
        _require(data[key]["items"] == expected_items, "CORPUS_INVALID")
        _require(
            (data[key]["next_cursor"] is not None)
            == (key in ("history_page_first", "history_after_relogin")),
            "CORPUS_INVALID",
        )
    first_cursor = data["history_page_first"]["next_cursor"]
    _require(
        cases["history_page_next"]["target"]["before"] == first_cursor
        and int(data["history_after_relogin"]["next_cursor"]) > int(first_cursor),
        "CORPUS_INVALID",
    )
    for case in cases.values():
        if case["operation"] == "history" and case["id"] != "history_page_next":
            _require(case["target"]["before"] is None, "CORPUS_INVALID")
    _require(
        cases["assessment_other_owner"]["target"]["assessment_id"] == original["assessment_id"]
        and cases["assessment_missing"]["target"]["assessment_id"]
        not in {record["assessment_id"] for record in records},
        "CORPUS_INVALID",
    )


class SavedRiskProof:
    def __init__(self, database: Path) -> None:
        self.native = NativeProof(database)
        self.database = database
        self.checks: list[dict[str, Any]] = []
        self.responses_checked = 0
        self.cases: dict[str, dict[str, Any]] = {}
        self.private_identities: set[str] = set()

    def mark(self, identifier: str) -> None:
        _require(
            identifier in REQUIRED_CHECKS and identifier not in {item["id"] for item in self.checks}
        )
        self.checks.append({"id": identifier, "passed": True})

    def request(
        self,
        method: str,
        suffix: str,
        token: str | None,
        payload: dict[str, Any] | None = None,
        *,
        status: int = 200,
        code: str | None = None,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        _require(suffix.startswith("/") and "://" not in suffix, "CONFIGURATION_INVALID")
        try:
            operation, target, limit = _route(method, suffix, capture=case_id is not None)
            snapshot = copy.deepcopy(payload)
            if case_id is not None:
                _require(
                    case_id in CASE_MAP
                    and case_id not in self.cases
                    and CASE_MAP[case_id] == (operation, status, code),
                    "CORPUS_INVALID",
                )
            response = self.native.current_client().request(
                method,
                RISK + suffix,
                json=snapshot,
                headers={"Authorization": "Bearer " + token} if token else {},
            )
            raw = response.content
            _require(
                len(raw) <= MAX_BODY
                and response.status_code == status
                and not response.history
                and "set-cookie" not in response.headers
                and response.headers.get("content-type", "").split(";")[0] == "application/json",
                "WIRE_INVALID",
            )
            forbidden = (*self.native.tokens, *self.private_identities, str(self.database))
            _require(
                all(value.encode("utf-8") not in raw for value in forbidden), "TOKEN_REFLECTION"
            )
            data = _wire_body(raw, operation, status, code, limit=limit, forbidden=forbidden)
            if code is None:
                _confirmation(operation, target, snapshot, data)
            if case_id is not None:
                self.cases[case_id] = {
                    "id": case_id,
                    "operation": operation,
                    "target": target,
                    # Illegal server requests are never claimed as typed-client emission.
                    "request": snapshot if code is None else None,
                    "status": status,
                    "content_type": "application/json",
                    "body_utf8": raw.decode("utf-8"),
                    "expected": {"outcome": "success"}
                    if code is None
                    else {"outcome": "error", "error_code": code},
                }
            self.responses_checked += 1
            return data
        except AcceptanceFailure as error:
            if error.code in ("CONFIGURATION_INVALID", "TOKEN_REFLECTION"):
                raise
            raise AcceptanceFailure("WIRE_INVALID") from None
        except (httpx.HTTPError, ValueError, TypeError, UnicodeError, KeyError, RecursionError):
            raise AcceptanceFailure("WIRE_INVALID") from None

    def complete(self, token: str, *, other: bool = False) -> None:
        profile = (
            {**PROFILE_REQUEST, "display_name": "Synthetic learner B"} if other else PROFILE_REQUEST
        )
        self.native.request("draft", token, profile)
        self.native.request("consent", token, CONSENT_REQUEST)
        state = self.native.request("complete", token, COMPLETE_REQUEST)
        _require(state["onboarding_completed"] is True)

    def run(self) -> None:
        disabled = self.native.start("disabled")
        response = self.native.current_client().post(
            RISK + "/assessments",
            content=b"{malformed",
            headers={"Content-Type": "application/json"},
        )
        _require(
            response.status_code == 403
            and response.json().get("error_code") == "LOCAL_APPLICATION_ONLY"
            and not self.database.exists()
        )
        _wire_body(response.content, "assessment_create", 403, "LOCAL_APPLICATION_ONLY")
        disabled.stop()
        self.mark("disabled_prebody_no_database")
        first = self.native.start()
        self.request("GET", "/draft", None, status=401, code="SESSION_INVALID")
        _require(not self.database.exists())
        self.mark("missing_bearer_no_database")
        owner, owner_id, _ = self.native.login("learner-a")
        self.private_identities.add(owner_id)
        self.request("GET", "/draft", owner, status=409, code="ONBOARDING_REQUIRED")
        self.complete(owner)
        other, other_id, _ = self.native.login("learner-b")
        self.private_identities.add(other_id)
        self.complete(other, other=True)
        self.mark("current_s1_prerequisites")
        questionnaire = self.request("GET", "/questionnaire", owner, case_id="questionnaire")
        _require([item["question_id"] for item in questionnaire["questions"]] == QUESTION_IDS)
        _require(questionnaire["scoring_version"] == "deterministic_v1.0.0")
        self.mark("ordered_ten_question_contract")
        initial = self.request("GET", "/draft", owner, case_id="draft_initial")
        _require(initial["answers"] == [] and initial["updated_at"] is None)
        partial = risk_input(partial=True)
        draft = self.request("PUT", "/draft", owner, partial, case_id="draft_partial_saved")
        _require(draft["answers"] == partial["answers"] and draft["updated_at"] is not None)
        _require(self.request("GET", "/draft", other)["answers"] == [])
        _require(self.request("GET", "/draft", owner, case_id="draft_partial_resumed") == draft)
        _require(
            self.request("GET", "/assessments?limit=2", owner, case_id="history_initial")["items"]
            == []
        )
        self.mark("owned_partial_draft")
        payload = {**risk_input(), "idempotency_key": str(uuid4())}
        original = self.request(
            "POST", "/assessments", owner, payload, case_id="assessment_created"
        )
        result = original["assessment"]
        rules = json.dumps(
            original["rules_snapshot"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        _require(
            original["persisted"] is True
            and original["input"] == risk_input()
            and all(
                result[field] == 50
                for field in ("willingness_score", "capacity_score", "composite_score")
            )
            and result["risk_category"]["code"] == "MODERATE"
            and result["calculated_at"] == original["created_at"]
            and original["rules_sha256"] == hashlib.sha256(rules).hexdigest()
            and original["rules_sha256"] == questionnaire["rules_sha256"]
            and len(rules) <= 65536
        )
        self.mark("saved_numeric_rules_snapshot")
        reordered = {**payload, "answers": list(reversed(payload["answers"]))}
        _require(
            self.request(
                "POST", "/assessments", owner, reordered, case_id="assessment_equivalent_replay"
            )
            == original
        )
        self.mark("original_equivalent_replay")
        conflict = {**risk_input("D"), "idempotency_key": payload["idempotency_key"]}
        self.request(
            "POST",
            "/assessments",
            owner,
            conflict,
            status=409,
            code="IDEMPOTENCY_CONFLICT",
            case_id="idempotency_conflict",
        )
        _require(
            self.request("GET", "/assessments?limit=2", owner, case_id="history_single")["items"]
            == [original]
        )
        self.mark("conflict_unchanged_history")
        _require(
            self.request("GET", "/assessments?limit=2", other, case_id="other_owner_history_empty")[
                "items"
            ]
            == []
        )
        for identifier, case_id in (
            (original["assessment_id"], "assessment_other_owner"),
            (str(uuid4()), "assessment_missing"),
        ):
            self.request(
                "GET",
                "/assessments/" + identifier,
                other,
                status=404,
                code="RISK_ASSESSMENT_NOT_FOUND",
                case_id=case_id,
            )
        _require(
            self.request(
                "GET",
                "/assessments/" + original["assessment_id"],
                owner,
                case_id="assessment_detail",
            )
            == original
        )
        _require(
            self.request("POST", "/assessments", other, payload)["assessment_id"]
            != original["assessment_id"]
        )
        self.mark("owner_scoped_history_detail")
        _require(self.request("GET", "/draft", owner) == draft)
        empty = self.request(
            "PUT", "/draft", owner, {**risk_input(), "answers": []}, case_id="draft_cleared"
        )
        _require(empty["answers"] == [])
        _require(self.request("GET", "/assessments", owner)["items"] == [original])
        self.mark("empty_draft_preserves_history")
        first.stop()
        second = self.native.start()
        _require(self.request("GET", "/draft", owner, case_id="draft_after_restart") == empty)
        _require(
            self.request(
                "GET",
                "/assessments/" + original["assessment_id"],
                owner,
                case_id="assessment_after_restart",
            )
            == original
        )
        _require(self.request("POST", "/assessments", owner, reordered) == original)
        _require(self.request("GET", "/assessments", owner)["items"] == [original])
        self.mark("first_native_restart")
        later = self.request(
            "POST",
            "/assessments",
            owner,
            {**risk_input("E"), "idempotency_key": str(uuid4())},
            case_id="assessment_aggressive",
        )
        conservative = self.request(
            "POST",
            "/assessments",
            owner,
            {**risk_input("A"), "idempotency_key": str(uuid4())},
            case_id="assessment_conservative",
        )
        page = self.request("GET", "/assessments?limit=2", owner, case_id="history_page_first")
        _require(page["items"] == [conservative, later] and page["next_cursor"] is not None)
        inserted = self.request(
            "POST",
            "/assessments",
            owner,
            {**risk_input("D"), "idempotency_key": str(uuid4())},
            case_id="assessment_inserted_between_pages",
        )
        next_page = self.request(
            "GET",
            "/assessments?limit=2&before=" + page["next_cursor"],
            owner,
            case_id="history_page_next",
        )
        _require(next_page["items"] == [original] and next_page["next_cursor"] is None)
        self.mark("bounded_stable_cursor")
        self.request(
            "PUT",
            "/draft",
            owner,
            {**risk_input(), "questionnaire_version": "v999"},
            status=400,
            code="UNSUPPORTED_QUESTIONNAIRE_VERSION",
            case_id="unsupported_version",
        )
        self.request(
            "POST",
            "/assessments",
            owner,
            {**risk_input(partial=True), "idempotency_key": str(uuid4())},
            status=400,
            code="MISSING_REQUIRED_QUESTION",
            case_id="missing_required_question",
        )
        self.request(
            "POST",
            "/assessments",
            owner,
            {**risk_input(), "idempotency_key": "synthetic-invalid-key"},
            status=422,
            code="VALIDATION_ERROR",
            case_id="validation_error",
        )
        self.native.request("consent", owner, {**CONSENT_REQUEST, "consent_given": False})
        self.request(
            "GET",
            "/assessments?limit=2",
            owner,
            status=409,
            code="ONBOARDING_REQUIRED",
            case_id="onboarding_withdrawn",
        )
        self.native.request("consent", owner, CONSENT_REQUEST)
        self.request(
            "GET",
            "/assessments?limit=2",
            owner,
            status=409,
            code="ONBOARDING_REQUIRED",
            case_id="onboarding_reaccepted",
        )
        self.native.request("complete", owner, COMPLETE_REQUEST)
        _require(
            self.request("GET", "/assessments?limit=2", owner)["items"] == [inserted, conservative]
        )
        self.mark("withdrawal_reacceptance_gate")
        self.native.request("logout", owner, {})
        self.request(
            "GET", "/draft", owner, status=401, code="SESSION_INVALID", case_id="session_invalid"
        )
        self.mark("durable_session_logout")
        second.stop()
        self.native.start()
        self.request(
            "GET",
            "/assessments?limit=2",
            owner,
            status=401,
            code="SESSION_INVALID",
            case_id="session_restart_invalid",
        )
        replacement, replacement_id, _ = self.native.login("learner-a")
        _require(replacement_id == owner_id)
        _require(
            self.request(
                "GET", "/assessments?limit=2", replacement, case_id="history_after_relogin"
            )["items"]
            == [inserted, conservative]
        )
        _require(
            self.request("GET", "/assessments/" + original["assessment_id"], replacement)
            == original
        )
        self.mark("second_native_restart")
        for server in self.native.servers:
            _require(
                all(
                    token.encode("ascii") not in server.diagnostics()
                    for token in self.native.tokens
                ),
                "TOKEN_REFLECTION",
            )
        self.mark("safe_wire_without_credentials")
        _require(set(self.cases) == set(CASE_IDS))
        self.mark("complete_safe_wire_corpus")


def evaluate_acceptance(
    *,
    tested_sha: str,
    tested_tree: str,
    corpus_output: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Keep the historical report-only Python API; CLI privately collects the corpus."""
    provenance: dict[str, Any] = {
        "tested_commit": None,
        "tested_tree": None,
        "working_tree_dirty": None,
        "tracked_dirty": None,
        "source_hashes": [],
        "source_manifest_sha256": None,
    }
    proof: SavedRiskProof | None = None
    workspace: Path | None = None
    base: Path | None = None
    corpus: dict[str, Any] | None = None
    failure: str | None = None
    removed = False
    try:
        _require(
            all(
                isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))
                for value in (tested_sha, tested_tree)
            ),
            "PROVENANCE_INVALID",
        )
        provenance.update(repository_provenance(tested_sha, tested_tree))
        _require(
            provenance["tested_commit"] == tested_sha
            and provenance["tested_tree"] == tested_tree
            and provenance["working_tree_dirty"] is False
            and provenance["tracked_dirty"] is not True,
            "PROVENANCE_MISMATCH",
        )
        provenance["source_hashes"] = runtime_hashes()
        base = _temp_base().resolve()
        _require(
            base.is_dir() and base != ROOT and ROOT not in base.parents,
            "TEMPORARY_DIRECTORY_UNSAFE",
        )
        # The reused child strictly allows only this audited disposable prefix.
        workspace = Path(tempfile.mkdtemp(prefix="finex-s1-acceptance-", dir=base))
        proof = SavedRiskProof(workspace / "state.sqlite3")
        proof.run()
        _require(runtime_hashes() == provenance["source_hashes"], "SOURCE_CHANGED")
        _require(
            _git(["rev-parse", "HEAD"]) == tested_sha
            and _git(["rev-parse", "HEAD^{tree}"]) == tested_tree
            and not _git(["status", "--porcelain", "--untracked-files=normal"]),
            "SOURCE_CHANGED",
        )
        _require(
            proof.checks
            == [{"id": key, "passed": True} for key in REQUIRED_CHECKS if key != "owned_cleanup"],
            "PROBE_FAILED",
        )
        provenance["source_manifest_sha256"] = manifest_sha256(provenance["source_hashes"])
        _require(set(proof.cases) == set(CASE_IDS), "CORPUS_INVALID")
        corpus = {
            "schema_version": CORPUS_SCHEMA,
            "scope": SCOPE,
            "contract_version": CONTRACT_VERSION,
            "provenance": {
                "kind": "native_tcp_capture",
                "source": "owned_loopback_uvicorn",
                "command": COMMAND,
                "tested_commit": tested_sha,
                "tested_tree": tested_tree,
            },
            "source_hashes": provenance["source_hashes"],
            "source_manifest_sha256": provenance["source_manifest_sha256"],
            "cases": [proof.cases[key] for key in CASE_IDS],
        }
        validate_corpus(
            corpus, forbidden=(*proof.native.tokens, *proof.private_identities, str(proof.database))
        )
        pids = [server.process.pid for server in proof.native.servers if server.process is not None]
        _require(
            len(proof.native.servers) == len(pids) == len(set(pids)) == 4
            and all(type(pid) is int and pid > 0 for pid in pids),
            "PROBE_FAILED",
        )
    except AcceptanceFailure as error:
        failure = error.code
    except Exception:
        failure = "INTERNAL_FAILURE"
    finally:
        if proof is not None:
            for server in proof.native.servers:
                try:
                    server.stop()
                except AcceptanceFailure as error:
                    failure = error.code
                except Exception:
                    failure = "CHILD_CLEANUP_FAILED"
        if workspace is not None:
            try:
                _require(
                    proof is not None and all(server.reaped for server in proof.native.servers),
                    "CHILD_CLEANUP_FAILED",
                )
                _require(
                    base is not None
                    and workspace.parent.resolve() == base
                    and workspace.name.startswith("finex-s1-acceptance-")
                    and not workspace.is_symlink()
                    and workspace.resolve().parent == base
                    and workspace.resolve() != ROOT
                    and ROOT not in workspace.resolve().parents,
                    "TEMPORARY_DIRECTORY_UNSAFE",
                )
                shutil.rmtree(workspace)
                removed = not workspace.exists()
                _require(removed, "TEMPORARY_CLEANUP_FAILED")
            except AcceptanceFailure as error:
                failure = error.code
            except OSError:
                failure = "TEMPORARY_CLEANUP_FAILED"
    if failure is None and proof is not None and removed:
        try:
            _require(
                runtime_hashes() == provenance["source_hashes"]
                and _git(["rev-parse", "HEAD"]) == tested_sha
                and _git(["rev-parse", "HEAD^{tree}"]) == tested_tree
                and not _git(["status", "--porcelain", "--untracked-files=normal"]),
                "SOURCE_CHANGED",
            )
            proof.mark("owned_cleanup")
            _require(
                proof.checks == [{"id": key, "passed": True} for key in REQUIRED_CHECKS],
                "PROBE_FAILED",
            )
        except AcceptanceFailure as error:
            failure = error.code
        except Exception:
            failure = "INTERNAL_FAILURE"
    success = failure is None and proof is not None and removed and corpus is not None
    if not success:
        corpus = None
    elif corpus_output is not None and corpus is not None:
        corpus_output.append(corpus)
    return {
        "schema_version": REPORT_SCHEMA,
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "success": success,
        "mode": "owned_native_tcp",
        **provenance,
        "checks": proof.checks if proof is not None else [],
        "required_checks": list(REQUIRED_CHECKS),
        "failures": [] if success else [{"code": failure or "INTERNAL_FAILURE"}],
        "responses_checked": proof.responses_checked if proof is not None else 0,
        "corpus_sha256": hashlib.sha256(json_bytes(corpus)).hexdigest()
        if corpus is not None
        else None,
        "corpus_case_ids": list(CASE_IDS) if corpus is not None else [],
        "native_process": {
            "starts": len(proof.native.servers) if proof is not None else 0,
            "application_restarts": 2 if success else None,
            "owned_pids": [
                process.pid
                for server in proof.native.servers
                if (process := getattr(server, "process", None)) is not None
            ]
            if proof is not None
            else [],
            "child_reaped": proof is not None
            and all(server.reaped for server in proof.native.servers),
            "temporary_directory_removed": removed,
            "session_ttl_minutes": 1,
            "real_expiry_elapsed_seconds": None,
            "shutdown": "owned_terminate_and_reap",
        },
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "limitations": [
            "Saved-risk API proof is not manual portfolio or full two-client S2 acceptance.",
            "This saved-risk capture does not wait for expiry; combined-domain real expiry "
            "is independently checked within the portfolio native proof's existing window.",
            "No live provider, verified real identity, real money, cloud or human UAT.",
        ],
    }


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AcceptanceFailure("CLI_ARGUMENTS_INVALID")


def validate_corpus(corpus: object, *, forbidden: tuple[str, ...] = ()) -> None:
    """Validate the frozen map and native semantics, never normalize raw responses."""
    try:
        value = safe_object(
            corpus,
            {
                "schema_version",
                "scope",
                "contract_version",
                "provenance",
                "source_hashes",
                "source_manifest_sha256",
                "cases",
            },
        )
        _require(
            value["schema_version"] == CORPUS_SCHEMA
            and value["scope"] == SCOPE
            and value["contract_version"] == CONTRACT_VERSION,
            "CORPUS_INVALID",
        )
        provenance = safe_object(
            value["provenance"], {"kind", "source", "command", "tested_commit", "tested_tree"}
        )
        _require(
            provenance["kind"] == "native_tcp_capture"
            and provenance["command"] == COMMAND
            and provenance["source"] == "owned_loopback_uvicorn"
            and all(
                isinstance(provenance[key], str) and bool(SHA_PATTERN.fullmatch(provenance[key]))
                for key in ("tested_commit", "tested_tree")
            ),
            "CORPUS_INVALID",
        )
        _require(
            manifest_sha256(value["source_hashes"]) == value["source_manifest_sha256"],
            "CORPUS_INVALID",
        )
        items = value["cases"]
        _require(isinstance(items, list) and len(items) == len(CASE_IDS), "CORPUS_INVALID")
        cases: dict[str, dict[str, Any]] = {}
        data: dict[str, dict[str, Any]] = {}
        for identifier, item in zip(CASE_IDS, items, strict=True):
            case = safe_object(
                item,
                {
                    "id",
                    "operation",
                    "target",
                    "request",
                    "status",
                    "content_type",
                    "body_utf8",
                    "expected",
                },
            )
            operation, status, code = CASE_MAP[identifier]
            _require(
                case["id"] == identifier
                and case["operation"] == operation
                and type(case["status"]) is int
                and case["status"] == status
                and case["content_type"] == "application/json"
                and isinstance(case["body_utf8"], str),
                "CORPUS_INVALID",
            )
            _target(operation, case["target"])
            raw = case["body_utf8"].encode("utf-8")
            _require(
                all(secret.encode("utf-8") not in raw for secret in forbidden)
                and not reflects_private(case["request"], forbidden),
                "CORPUS_INVALID",
            )
            decoded = _wire_body(raw, operation, status, code, forbidden=forbidden)
            if code is None:
                _require(case["expected"] == {"outcome": "success"}, "CORPUS_INVALID")
                _confirmation(operation, case["target"], case["request"], decoded)
                data[identifier] = decoded
            else:
                _require(
                    case["request"] is None
                    and case["expected"] == {"outcome": "error", "error_code": code},
                    "CORPUS_INVALID",
                )
            cases[identifier] = case
        _relationships(cases, data)
        serialized = json_bytes(value)
        _require(
            len(serialized) <= MAX_CORPUS
            and all(secret.encode("utf-8") not in serialized for secret in forbidden),
            "CORPUS_INVALID",
        )
    except (
        AcceptanceFailure,
        ValueError,
        TypeError,
        UnicodeError,
        KeyError,
        AttributeError,
        RecursionError,
    ):
        raise AcceptanceFailure("CORPUS_INVALID") from None


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description=__doc__)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--tested-tree", required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    try:
        options = parser.parse_args(argv)
        report_target, corpus_target = (
            output_target(options.report, ROOT),
            output_target(options.corpus, ROOT),
        )
        _require(
            report_target is None or corpus_target is None or report_target != corpus_target,
            "OUTPUT_INVALID",
        )
        captured: list[dict[str, Any]] = []
        report = evaluate_acceptance(
            tested_sha=options.tested_sha, tested_tree=options.tested_tree, corpus_output=captured
        )
        if corpus_target is not None and report["success"]:
            _require(len(captured) == 1, "CORPUS_INVALID")
            write_new_json(corpus_target, captured[0])
            _require(
                hashlib.sha256(corpus_target.read_bytes()).hexdigest() == report["corpus_sha256"],
                "OUTPUT_WRITE_FAILED",
            )
        if report_target is not None:
            write_new_json(report_target, report)
        if options.format == "json":
            print(json.dumps(report, sort_keys=True))
        else:
            print("S2 saved risk native acceptance: " + ("PASS" if report["success"] else "FAIL"))
        return 0 if report["success"] else 1
    except AcceptanceFailure as error:
        print(json.dumps({"success": False, "failures": [{"code": error.code}]}))
        return 1
    except Exception:
        print(json.dumps({"success": False, "failures": [{"code": "INTERNAL_FAILURE"}]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
