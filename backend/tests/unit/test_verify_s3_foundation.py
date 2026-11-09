"""Synthetic S3 acceptance-tool controls, not native or release evidence.

All revision fields, PIDs, original wire strings and lifecycle objects here are
unit inputs. No API child, credential lookup, native service or user DB is used.
Assertions never format a raw response, bearer, request or parser diagnostic.
"""

from __future__ import annotations

import copy
import hashlib
import json
import secrets
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import verify_s3_evidence as passive
import verify_s3_foundation as producer
from app.core.responses import APIResponse
from local_s2_evidence import json_bytes, manifest_sha256
from verify_s1_application import AcceptanceFailure

SHA, TREE = "a" * 40, "b" * 40
API_CHECKOUT = producer.ROOT.resolve()
TIME = "2026-10-11T12:00:00+00:00"
RENAMED = "2026-10-11T12:00:01+00:00"
ADDED = "2026-10-11T12:00:02+00:00"
RESTARTED = "2026-10-11T12:00:03+00:00"
FIXTURE_TIME = "2026-01-01T00:00:00Z"
WL = "00000000-0000-4000-8000-000000000195"
PEER_WL = "00000000-0000-4000-8000-000000000196"
ACCOUNT = "00000000-0000-4000-8000-000000000197"
LEDGER = "00000000-0000-4000-8000-000000000198"
SCOPE = {
    "scope": "local_educational_application",
    "contract_version": "local.v1",
    "foundation_version": "market_foundation.v1",
}
INSTRUMENTS = [
    {
        "instrument_id": "SYN:AAPL",
        "display_name": "Synthetic Apple example",
        "asset_class": "EQUITY",
        "sector": "TECHNOLOGY",
        "currency": "USD",
    },
    {
        "instrument_id": "SYN:BND",
        "display_name": "Synthetic bond-fund example",
        "asset_class": "BOND",
        "sector": "FIXED_INCOME",
        "currency": "USD",
    },
    {
        "instrument_id": "SYN:MSFT",
        "display_name": "Synthetic Microsoft example",
        "asset_class": "EQUITY",
        "sector": "TECHNOLOGY",
        "currency": "USD",
    },
    {
        "instrument_id": "SYN:UNAVAILABLE",
        "display_name": "Synthetic unavailable-price example",
        "asset_class": "EQUITY",
        "sector": "GENERAL",
        "currency": "USD",
    },
]
# Deliberately independent of the production producer's inventory constants.
CHECK_IDS = (
    "disabled_body_boundary",
    "missing_credential_boundary",
    "current_completed_onboarding",
    "default_search_catalogue",
    "default_quote_states_and_cache_hit",
    "unsupported_instrument",
    "watchlist_crud_and_stable_noops",
    "owner_scoped_non_disclosure",
    "watchlist_capacity_atomic",
    "unopened_read_no_funding",
    "one_explicit_opening",
    "original_opening_ledger",
    "first_real_process_restart",
    "withdrawal_reacceptance_recompletion",
    "watchlist_delete_preserves_other_domains",
    "durable_logout_and_second_restart",
    "real_session_expiry",
    "safe_owned_database_fault",
    "digest_only_storage_no_leak",
    "complete_original_wire_corpus",
    "owned_cleanup",
)
SPECS = (
    ("local_application_only", "search", 403, "LOCAL_APPLICATION_ONLY"),
    ("session_missing", "search", 401, "SESSION_INVALID"),
    ("onboarding_required", "watchlists", 409, "ONBOARDING_REQUIRED"),
    ("search_default", "search", 200, None),
    ("search_filtered", "search", 200, None),
    ("search_empty", "search", 200, None),
    ("quote_aapl", "quote", 200, None),
    ("quote_bond", "quote", 200, None),
    ("quote_msft", "quote", 200, None),
    ("quote_unavailable", "quote", 200, None),
    ("quote_cache_hit", "quote", 200, None),
    ("instrument_not_found", "quote", 404, "INSTRUMENT_NOT_FOUND"),
    ("watchlists_empty", "watchlists", 200, None),
    ("watchlist_created", "watchlist_create", 201, None),
    ("watchlist_renamed", "watchlist_update", 200, None),
    ("watchlist_rename_noop", "watchlist_update", 200, None),
    ("watchlist_item_added", "watchlist_item_put", 200, None),
    ("watchlist_item_duplicate", "watchlist_item_put", 200, None),
    ("watchlist_detail", "watchlist_detail", 200, None),
    ("watchlist_collection", "watchlists", 200, None),
    ("other_owner_empty", "watchlists", 200, None),
    ("watchlist_other_owner", "watchlist_detail", 404, "WATCHLIST_NOT_FOUND"),
    ("watchlist_item_removed", "watchlist_item_delete", 200, None),
    ("watchlist_item_remove_noop", "watchlist_item_delete", 200, None),
    ("unopened_account", "account", 200, None),
    ("unopened_ledger", "ledger", 404, "PAPER_ACCOUNT_NOT_OPEN"),
    ("opened_account", "account_open", 200, None),
    ("repeated_account_open", "account_open", 200, None),
    ("opening_ledger", "ledger", 200, None),
    ("ledger_after_opening", "ledger", 200, None),
    ("other_owner_unopened", "account", 200, None),
    ("account_after_restart", "account", 200, None),
    ("watchlist_after_restart", "watchlist_detail", 200, None),
    ("withdrawal_required", "watchlists", 409, "ONBOARDING_REQUIRED"),
    ("reaccepted_required", "account", 409, "ONBOARDING_REQUIRED"),
    ("account_after_recompletion", "account", 200, None),
    ("watchlist_deleted", "watchlist_delete", 200, None),
    ("deleted_watchlist_not_found", "watchlist_detail", 404, "WATCHLIST_NOT_FOUND"),
    ("account_after_watchlist_delete", "account", 200, None),
    ("session_revoked", "watchlists", 401, "SESSION_INVALID"),
    ("session_after_restart_revoked", "account", 401, "SESSION_INVALID"),
    ("session_expired", "account", 401, "SESSION_INVALID"),
    ("account_after_expiry_relogin", "account", 200, None),
    ("storage_unavailable", "watchlists", 503, "LOCAL_STORE_UNAVAILABLE"),
    ("restored_account", "account", 200, None),
    ("invalid_watchlist_name", "watchlist_create", 422, "VALIDATION_ERROR"),
    ("foundation_version_mismatch", "account_open", 409, "MARKET_FOUNDATION_VERSION_MISMATCH"),
    ("watchlist_limit", "watchlist_create", 409, "WATCHLIST_LIMIT"),
)


def summary(*, second: bool = False, count: int = 0) -> dict:
    return {
        "watchlist_id": PEER_WL if second else WL,
        "name": "Synthetic second list" if second else "Synthetic review list renamed",
        "created_at": ADDED if second else TIME,
        "updated_at": ADDED if second else RENAMED,
        "item_count": count,
    }


def full_list(*, initial: bool = False, restart: bool = False) -> dict:
    record = summary(count=0 if initial else 1)
    if initial:
        record.update(name="Synthetic review list", updated_at=TIME)
    elif restart:
        record["updated_at"] = RESTARTED
    else:
        record["updated_at"] = ADDED
    return {
        **SCOPE,
        "watchlist_version": "watchlist.v1",
        **record,
        "items": []
        if initial
        else [{**INSTRUMENTS[1 if restart else 0], "added_at": RESTARTED if restart else ADDED}],
    }


def account_data(*, unopened: bool = False) -> dict:
    return {
        **SCOPE,
        "paper_account_version": "paper_account.v1",
        "simulation": True,
        "account": None
        if unopened
        else {
            "account_id": ACCOUNT,
            "opening_ledger_id": LEDGER,
            "currency": "USD",
            "opening_cash": "10000.00",
            "cash_balance": "10000.00",
            "created_at": TIME,
        },
    }


def ledger_data(*, empty: bool = False) -> dict:
    return {
        **SCOPE,
        "paper_ledger_version": "paper_ledger.v1",
        "simulation": True,
        "account_id": ACCOUNT,
        "limit": 2,
        "after_sequence": 1 if empty else 0,
        "count": 0 if empty else 1,
        "items": []
        if empty
        else [
            {
                "ledger_id": LEDGER,
                "account_id": ACCOUNT,
                "sequence": 1,
                "entry_type": "OPENING",
                "cash_delta": "10000.00",
                "cash_after": "10000.00",
                "instrument_id": None,
                "quantity_delta": None,
                "position_after": None,
                "order_id": None,
                "trade_id": None,
                "corrects_ledger_id": None,
                "created_at": TIME,
            }
        ],
        "next_cursor": None,
    }


def case_values(identifier: str, operation: str) -> tuple[dict, object, object]:
    if operation == "search":
        query = (
            "apple"
            if identifier == "search_filtered"
            else "no-match"
            if identifier == "search_empty"
            else ""
        )
        limit = 2 if query else 20
        found = [INSTRUMENTS[0]] if query == "apple" else [] if query else INSTRUMENTS
        return (
            {
                **SCOPE,
                "catalog_version": "synthetic_catalog.v1",
                "query": query,
                "limit": limit,
                "count": len(found),
                "items": copy.deepcopy(found),
            },
            {"query": query, "limit": limit},
            None,
        )
    if operation == "quote":
        index = {"quote_bond": 1, "quote_msft": 2, "quote_unavailable": 3}.get(identifier, 0)
        instrument = (
            "SYN:TEST001"
            if identifier == "instrument_not_found"
            else INSTRUMENTS[index]["instrument_id"]
        )
        unavailable = index == 3
        return (
            {
                **SCOPE,
                "catalog_version": "synthetic_catalog.v1",
                "quote_snapshot_version": "synthetic_quotes.v1",
                "source": "finex.synthetic.portfolio",
                "source_type": "SYNTHETIC",
                "fixture_as_of": FIXTURE_TIME,
                "instrument_id": instrument,
                "currency": "USD",
                "status": "UNAVAILABLE" if unavailable else "CACHED",
                "unit_price": None if unavailable else ("200.0000", "80.0000", "400.0000")[index],
                "quote_as_of": None if unavailable else FIXTURE_TIME,
                "fetched_at": TIME,
                "cache_expires_at": "2026-10-11T12:01:00+00:00",
                "reason": "SYNTHETIC_QUOTE_UNAVAILABLE" if unavailable else None,
            },
            {"instrument_id": instrument},
            None,
        )
    if operation == "watchlists":
        items = (
            [{**summary(count=1), "updated_at": ADDED}, summary(second=True)]
            if identifier == "watchlist_collection"
            else []
        )
        return (
            {
                **SCOPE,
                "watchlist_version": "watchlist.v1",
                "limit": 10,
                "count": len(items),
                "items": items,
            },
            None,
            None,
        )
    if operation in {"watchlist_create", "watchlist_update", "watchlist_detail"}:
        initial = operation == "watchlist_create"
        data = full_list(initial=initial, restart=identifier == "watchlist_after_restart")
        if operation == "watchlist_update":
            data = {**SCOPE, "watchlist_version": "watchlist.v1", **summary(), "items": []}
        request = {"name": data["name"]} if operation != "watchlist_detail" else None
        return data, None if initial else {"watchlist_id": WL}, request
    if operation in {"watchlist_item_put", "watchlist_item_delete"}:
        target = {"watchlist_id": WL, "instrument_id": "SYN:AAPL"}
        common = {
            **SCOPE,
            "watchlist_version": "watchlist.v1",
            "watchlist_item_version": "watchlist_item.v1",
            "watchlist_id": WL,
        }
        return (
            {
                **common,
                **(
                    {"item": {**INSTRUMENTS[0], "added_at": ADDED}}
                    if operation == "watchlist_item_put"
                    else {"instrument_id": "SYN:AAPL", "removed": True}
                ),
            },
            target,
            None,
        )
    if operation == "watchlist_delete":
        return (
            {**SCOPE, "watchlist_version": "watchlist.v1", "watchlist_id": WL, "deleted": True},
            {"watchlist_id": WL},
            None,
        )
    if operation in {"account", "account_open"}:
        return (
            account_data(unopened=identifier in {"unopened_account", "other_owner_unopened"}),
            None,
            {"foundation_version": "market_foundation.v1", "currency": "USD"}
            if operation == "account_open"
            else None,
        )
    if operation == "ledger":
        empty = identifier == "ledger_after_opening"
        return ledger_data(empty=empty), {"limit": 2, "after_sequence": 1 if empty else 0}, None
    raise AssertionError("Unknown safe fixture operation")


def success_body(data: dict, operation: str) -> dict:
    asof = None
    if operation == "search":
        asof = FIXTURE_TIME
    elif operation == "quote":
        asof = data["quote_as_of"]
    elif operation in {"watchlist_create", "watchlist_update", "watchlist_detail"}:
        asof = data["updated_at"]
    elif operation == "watchlist_item_put":
        asof = data["item"]["added_at"]
    elif operation in {"watchlist_item_delete", "watchlist_delete"}:
        asof = RESTARTED
    elif operation in {"account", "account_open"} and data["account"] is not None:
        asof = data["account"]["created_at"]
    elif operation == "ledger" and data["items"]:
        asof = data["items"][-1]["created_at"]
    return {
        "success": True,
        "message": "Unit-only synthetic — response",
        "data": data,
        "meta": {
            "apiVersion": "v1",
            "dataStatus": "UNAVAILABLE"
            if operation == "quote" and data["unit_price"] is None
            else "CACHED",
            "dataAsOf": asof,
            "correlationId": "unit-s3",
        },
    }


def corpus_fixture() -> dict:
    cases = []
    for identifier, operation, status, code in SPECS:
        data, target, request = case_values(identifier, operation)
        raw = (
            APIResponse.error(
                "Unit-only safe failure", code, status_code=status, correlation_id="unit-s3"
            ).body
            if code
            else json_bytes(success_body(data, operation))
        )
        cases.append(
            {
                "id": identifier,
                "operation": operation,
                "target": target,
                "request": None if code else request,
                "status": status,
                "content_type": "application/json",
                "body_utf8": raw.decode("utf-8"),
                "expected": {"outcome": "error", "error_code": code}
                if code
                else {"outcome": "success"},
            }
        )
    sources = [
        {"path": name, "sha256": "c" * 64}
        for name in sorted(producer.SOURCE_PATHS | {"backend/app/main.py"})
    ]
    return {
        "schema_version": "finex.local_s3.foundation_corpus.v1",
        **SCOPE,
        "provenance": {
            "kind": "native_tcp_capture",
            "source": "owned_loopback_uvicorn",
            "command": "python verify_s3_foundation.py",
            "tested_commit": SHA,
            "tested_tree": TREE,
        },
        "source_hashes": sources,
        "source_manifest_sha256": manifest_sha256(sources),
        "cases": cases,
    }


def case(corpus: dict, identifier: str) -> dict:
    return next(value for value in corpus["cases"] if value["id"] == identifier)


def mutate_body(corpus: dict, identifier: str, mutation) -> None:
    value = case(corpus, identifier)
    body = json.loads(value["body_utf8"])
    mutation(body)
    value["body_utf8"] = json_bytes(body).decode("utf-8")


def report_fixture(corpus: dict) -> dict:
    return {
        "schema_version": "finex.local_s3.foundation.acceptance.v1",
        **SCOPE,
        "success": True,
        "mode": "owned_native_tcp",
        "tested_commit": SHA,
        "tested_tree": TREE,
        "working_tree_dirty": False,
        "tracked_dirty": False,
        "source_hashes": copy.deepcopy(corpus["source_hashes"]),
        "source_manifest_sha256": corpus["source_manifest_sha256"],
        "checks": [{"id": identifier, "passed": True} for identifier in CHECK_IDS],
        "required_checks": list(CHECK_IDS),
        "failures": [],
        "responses_checked": 170,
        "corpus_sha256": hashlib.sha256(json_bytes(corpus)).hexdigest(),
        "corpus_case_ids": [row[0] for row in SPECS],
        "native_process": {
            "starts": 6,
            "application_restarts": 4,
            "durable_restarts": 2,
            "storage_fault_restarts": 2,
            "owned_pids": [101, 102, 103, 104, 105, 106],
            "child_reaped": True,
            "temporary_directory_removed": True,
            "session_ttl_minutes": 1,
            "real_expiry_elapsed_seconds": 60.125,
            "shutdown": "owned_terminate_and_reap",
        },
        "python_version": "3.12.14",
        "limitations": [
            "Default four-instrument synthetic TCP proof, not full S3 acceptance.",
            "Injected STALE provider, expanded capacity and physical migrations "
            "are separate in-process tests.",
        ],
    }


def test_frozen_inventories_and_success_fixture() -> None:
    assert producer.CASE_SPECS == SPECS
    assert producer.REQUIRED_CHECKS == CHECK_IDS
    producer.validate_corpus(corpus_fixture())


@pytest.mark.parametrize("identifier", [row[0] for row in SPECS])
def test_each_valid_original_response_is_consumed(identifier: str) -> None:
    entry = case(corpus_fixture(), identifier)
    code = entry["expected"].get("error_code")
    decoded = producer.wire_body(
        entry["body_utf8"].encode("utf-8"),
        entry["operation"],
        entry["status"],
        code,
        target=entry["target"],
        request=entry["request"],
    )
    assert isinstance(decoded, dict)


@pytest.mark.parametrize(
    "name",
    [
        "schema",
        "scope",
        "contract",
        "foundation",
        "provenance",
        "missing",
        "duplicate",
        "reorder",
        "extra_case",
        "float_status",
        "wrong_status",
        "wrong_operation",
        "content_type",
        "expected",
        "invalid_target",
        "missing_target",
        "private_request",
        "body_bound",
        "total_bound",
        "source_digest",
        "source_order",
        "source_duplicate",
        "source_traversal",
        "source_manifest",
    ],
)
def test_corpus_envelope_fail_closed(name: str) -> None:
    corpus = corpus_fixture()
    entry = case(corpus, "watchlist_created")
    if name == "schema":
        corpus["schema_version"] = "other.v1"
    elif name == "scope":
        corpus["scope"] = "production"
    elif name == "contract":
        corpus["contract_version"] = "local.v0"
    elif name == "foundation":
        corpus["foundation_version"] = "market_foundation.v0"
    elif name == "provenance":
        corpus["provenance"]["kind"] = "synthetic_fixture"
    elif name == "missing":
        corpus["cases"].pop()
    elif name == "duplicate":
        corpus["cases"][-1] = copy.deepcopy(corpus["cases"][0])
    elif name == "reorder":
        corpus["cases"].reverse()
    elif name == "extra_case":
        corpus["cases"].append(copy.deepcopy(entry))
    elif name == "float_status":
        entry["status"] = 201.0
    elif name == "wrong_status":
        entry["status"] = 200
    elif name == "wrong_operation":
        entry["operation"] = "account"
    elif name == "content_type":
        entry["content_type"] = "text/html"
    elif name == "expected":
        entry["expected"]["outcome"] = "error"
    elif name == "invalid_target":
        case(corpus, "watchlist_detail")["target"]["watchlist_id"] = "not-a-uuid"
    elif name == "missing_target":
        case(corpus, "quote_aapl")["target"] = None
    elif name == "private_request":
        entry["request"]["owner_id"] = "Synthetic owner"
    elif name == "body_bound":
        entry["body_utf8"] = " " * (producer.MAX_BODY + 1)
    elif name == "total_bound":
        for item in corpus["cases"]:
            item["body_utf8"] += " " * 60000
    elif name == "source_digest":
        corpus["source_hashes"][0]["sha256"] = "0"
    elif name == "source_order":
        corpus["source_hashes"].reverse()
    elif name == "source_duplicate":
        corpus["source_hashes"].append(copy.deepcopy(corpus["source_hashes"][0]))
    elif name == "source_traversal":
        corpus["source_hashes"][0]["path"] = "../outside"
    elif name == "source_manifest":
        corpus["source_manifest_sha256"] = "d" * 64
    with pytest.raises(AcceptanceFailure):
        producer.validate_corpus(corpus)


@pytest.mark.parametrize(
    "identifier,mutator",
    [
        ("search_default", lambda b: b.update(message=7)),
        ("search_default", lambda b: b["data"].update(count=True)),
        ("search_default", lambda b: b["data"].update(foundation_version="market_foundation.v0")),
        ("search_default", lambda b: b["data"]["items"].reverse()),
        ("search_default", lambda b: b["meta"].update(dataAsOf=None)),
        ("search_empty", lambda b: b["data"].update(items=[INSTRUMENTS[0]], count=1)),
        ("quote_aapl", lambda b: b["data"].update(unit_price="0.0000")),
        ("quote_aapl", lambda b: b["data"].update(unit_price="1000000.0001")),
        ("quote_aapl", lambda b: b["data"].update(source_type="LIVE")),
        ("quote_aapl", lambda b: b["data"].update(cache_expires_at=TIME)),
        ("quote_aapl", lambda b: b["data"].update(quote_as_of=None)),
        ("quote_unavailable", lambda b: b["data"].update(unit_price="0.0000")),
        ("quote_unavailable", lambda b: b["data"].update(fetched_at=None)),
        ("quote_unavailable", lambda b: b["meta"].update(dataStatus="CACHED")),
        ("watchlist_detail", lambda b: b["data"].update(item_count=True)),
        (
            "watchlist_detail",
            lambda b: b["data"]["items"].append(copy.deepcopy(b["data"]["items"][0])),
        ),
        ("watchlist_detail", lambda b: b["data"].update(created_at="2026-02-30T00:00:00Z")),
        ("watchlist_collection", lambda b: b["data"]["items"].reverse()),
        ("watchlist_collection", lambda b: b["data"].update(count=True)),
        ("watchlist_item_added", lambda b: b["data"].update(watchlist_id=PEER_WL)),
        ("watchlist_item_added", lambda b: b["data"]["item"].update(instrument_id="SYN:MSFT")),
        ("watchlist_deleted", lambda b: b["data"].update(deleted=1)),
        ("opened_account", lambda b: b["data"].update(simulation=1)),
        ("opened_account", lambda b: b["data"]["account"].update(cash_balance="20000.00")),
        ("opening_ledger", lambda b: b["data"]["items"][0].update(sequence=True)),
        ("opening_ledger", lambda b: b["data"]["items"][0].update(account_id=WL)),
        ("opening_ledger", lambda b: b["data"]["items"][0].update(instrument_id="SYN:AAPL")),
        ("opening_ledger", lambda b: b["data"].update(next_cursor=1)),
        ("ledger_after_opening", lambda b: b["meta"].update(dataAsOf=TIME)),
        ("session_missing", lambda b: b.pop("detail")),
        ("session_missing", lambda b: b.update(detail=3)),
        ("session_missing", lambda b: b.update(detail="Different safe text")),
        ("session_missing", lambda b: b["error"].update(fieldErrors={})),
        ("storage_unavailable", lambda b: b.update(error_code="SESSION_INVALID")),
    ],
)
def test_wire_and_case_semantic_negatives(identifier: str, mutator) -> None:
    corpus = corpus_fixture()
    mutate_body(corpus, identifier, mutator)
    with pytest.raises(AcceptanceFailure):
        producer.validate_corpus(corpus)


@pytest.mark.parametrize(
    "identifier",
    [
        "watchlist_rename_noop",
        "watchlist_item_duplicate",
        "repeated_account_open",
        "account_after_restart",
        "account_after_recompletion",
        "account_after_watchlist_delete",
        "account_after_expiry_relogin",
        "restored_account",
    ],
)
def test_replay_and_persistence_original_identity_is_bound(identifier: str) -> None:
    corpus = corpus_fixture()

    def mutate(body):
        if identifier == "watchlist_rename_noop":
            body["data"]["updated_at"] = ADDED
            body["meta"]["dataAsOf"] = ADDED
        elif identifier == "watchlist_item_duplicate":
            body["data"]["item"]["added_at"] = RESTARTED
            body["meta"]["dataAsOf"] = RESTARTED
        else:
            body["data"]["account"]["account_id"] = PEER_WL

    mutate_body(corpus, identifier, mutate)
    with pytest.raises(AcceptanceFailure):
        producer.validate_corpus(corpus)


@pytest.mark.parametrize(
    "field",
    [
        "user_id",
        "OWNER-ID",
        "sessionId",
        "Access_Token",
        "dbPath",
        "Authorization",
        "headers",
        "path",
        "logs",
        "diagnostics",
        "password",
        "nonce",
        "cookie",
        "expires_at",
    ],
)
def test_recursive_private_keys_are_rejected_without_raw_diagnostics(field: str) -> None:
    corpus = corpus_fixture()
    marker = secrets.token_urlsafe(32)
    mutate_body(
        corpus, "watchlist_detail", lambda body: body["data"].update({"extra": {field: marker}})
    )
    with pytest.raises(AcceptanceFailure) as caught:
        producer.validate_corpus(corpus)
    assert marker not in str(caught.value)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"success":true,"success":true}',
        b'{"message":"safe","messa\\u0067e":"safe"}',
        b'{"data":{"x":1,"x":2}}',
        b'{"x":NaN}',
        b'{"x":"\xff"}',
        b'{"x":',
    ],
)
def test_original_json_invalid_or_duplicate_members_fail_safely(raw: bytes) -> None:
    with pytest.raises(AcceptanceFailure):
        producer.wire_body(raw, "account", 200, None, target=None)


def fixture_path(tmp_path: Path, *components: str) -> Path:
    """All mutable fixtures stay in pytest's own temporary tree, never ROOT."""
    base = tmp_path.resolve(strict=True)
    target = tmp_path.joinpath(*components)
    resolved = target.resolve()
    assert API_CHECKOUT != base and API_CHECKOUT not in base.parents
    assert base in resolved.parents
    return target


def install_artifacts(tmp_path: Path, monkeypatch) -> tuple[Path, Path, dict, dict]:
    root = fixture_path(tmp_path, "source")
    root.mkdir()
    corpus = corpus_fixture()
    for entry in corpus["source_hashes"]:
        path = fixture_path(tmp_path, "source", entry["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = b"Synthetic unit source\n"
        path.write_bytes(raw)
        entry["sha256"] = hashlib.sha256(raw).hexdigest()
    corpus["source_manifest_sha256"] = manifest_sha256(corpus["source_hashes"])
    report = report_fixture(corpus)
    report_path = fixture_path(tmp_path, "report.json")
    corpus_path = fixture_path(tmp_path, "corpus.json")
    report_path.write_bytes(json_bytes(report))
    corpus_path.write_bytes(json_bytes(corpus))
    monkeypatch.setattr(passive, "ROOT", root)
    monkeypatch.setattr(
        passive,
        "repository_snapshot",
        lambda: {
            "tested_commit": SHA,
            "tested_tree": TREE,
            "working_tree_dirty": False,
            "tracked_dirty": False,
        },
        raising=False,
    )
    return report_path, corpus_path, report, corpus


def validate_files(report_path: Path, corpus_path: Path) -> None:
    passive.validate_artifacts(
        report=report_path, corpus=corpus_path, tested_sha=SHA, tested_tree=TREE
    )


def test_passive_valid_files_and_noncanonical_original_serialization(
    tmp_path: Path, monkeypatch
) -> None:
    report_path, corpus_path, report, corpus = install_artifacts(tmp_path, monkeypatch)
    raw = (json.dumps(corpus, ensure_ascii=False, separators=(",", ":")) + "\n\n").encode("utf-8")
    report["corpus_sha256"] = hashlib.sha256(raw).hexdigest()
    corpus_path.write_bytes(raw)
    report_path.write_bytes(json_bytes(report))
    validate_files(report_path, corpus_path)


def test_producer_hashes_actual_regular_sources_and_collects_new_runtime_files(
    tmp_path: Path, monkeypatch
) -> None:
    _, _, _, corpus = install_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(producer, "ROOT", fixture_path(tmp_path, "source"))
    assert producer.runtime_hashes() == corpus["source_hashes"]
    extra = fixture_path(tmp_path, "source", "backend/app/new_unit_source.py")
    extra.write_bytes(b"Synthetic additional runtime source\n")
    rows = producer.runtime_hashes()
    assert len(rows) == len(corpus["source_hashes"]) + 1
    assert any(row["path"] == "backend/app/new_unit_source.py" for row in rows)


@pytest.mark.parametrize("name", ["missing", "linked", "oversized"])
def test_producer_source_hashing_is_fail_closed(tmp_path: Path, monkeypatch, name: str) -> None:
    _, _, _, corpus = install_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(producer, "ROOT", fixture_path(tmp_path, "source"))
    path = fixture_path(tmp_path, "source", corpus["source_hashes"][0]["path"])
    if name == "missing":
        path.unlink()
    elif name == "oversized":
        path.write_bytes(b" " * (passive.MAX_SOURCE + 1))
    else:
        original = passive._linked
        monkeypatch.setattr(passive, "_linked", lambda value: value == path or original(value))
    with pytest.raises(AcceptanceFailure):
        producer.runtime_hashes()


@pytest.mark.parametrize(
    "name",
    [
        "missing",
        "empty",
        "same_path",
        "malformed",
        "duplicate",
        "schema",
        "revision",
        "tree",
        "dirty",
        "tracked",
        "failed",
        "false_success",
        "missing_check",
        "check_false",
        "wrong_order",
        "required",
        "case_ids",
        "responses_bool",
        "responses_low",
        "digest",
        "start_bool",
        "starts",
        "pid_duplicate",
        "unreaped",
        "temp_retained",
        "restart",
        "durable_restart",
        "fault_restart",
        "ttl",
        "expiry",
        "expiry_bool",
        "source_tamper",
        "source_missing",
        "source_inventory",
        "source_digest",
        "source_manifest",
        "private_limitation",
    ],
)
def test_passive_report_source_and_cleanup_fail_closed(
    tmp_path: Path, monkeypatch, name: str
) -> None:
    report_path, corpus_path, report, corpus = install_artifacts(tmp_path, monkeypatch)
    native = report["native_process"]
    if name == "missing":
        report_path.unlink()
    elif name == "empty":
        report_path.write_bytes(b"")
    elif name == "same_path":
        report_path = corpus_path
    elif name == "malformed":
        report_path.write_bytes(b"{")
    elif name == "duplicate":
        report_path.write_bytes(
            json_bytes(report).replace(b'"success": true', b'"success": false,"success": true')
        )
    elif name == "schema":
        report["schema_version"] = "wrong.v1"
    elif name == "revision":
        report["tested_commit"] = "c" * 40
    elif name == "tree":
        report["tested_tree"] = "d" * 40
    elif name == "dirty":
        report["working_tree_dirty"] = True
    elif name == "tracked":
        report["tracked_dirty"] = True
    elif name == "failed":
        report["failures"] = [{"code": "PROBE_FAILED"}]
    elif name == "false_success":
        report["success"] = 1
    elif name == "missing_check":
        report["checks"].pop()
    elif name == "check_false":
        report["checks"][0]["passed"] = False
    elif name == "wrong_order":
        report["checks"].reverse()
    elif name == "required":
        report["required_checks"].pop()
    elif name == "case_ids":
        report["corpus_case_ids"].pop()
    elif name == "responses_bool":
        report["responses_checked"] = True
    elif name == "responses_low":
        report["responses_checked"] = 47
    elif name == "digest":
        report["corpus_sha256"] = "f" * 64
    elif name == "start_bool":
        native["starts"] = True
    elif name == "starts":
        native["starts"] = 5
    elif name == "pid_duplicate":
        native["owned_pids"][-1] = native["owned_pids"][0]
    elif name == "unreaped":
        native["child_reaped"] = False
    elif name == "temp_retained":
        native["temporary_directory_removed"] = False
    elif name == "restart":
        native["application_restarts"] = 3
    elif name == "durable_restart":
        native["durable_restarts"] = 1
    elif name == "fault_restart":
        native["storage_fault_restarts"] = 1
    elif name == "ttl":
        native["session_ttl_minutes"] = 2
    elif name == "expiry":
        native["real_expiry_elapsed_seconds"] = 58.999
    elif name == "expiry_bool":
        native["real_expiry_elapsed_seconds"] = True
    elif name == "source_tamper":
        fixture_path(tmp_path, "source", corpus["source_hashes"][0]["path"]).write_bytes(
            b"Changed\n"
        )
    elif name == "source_missing":
        fixture_path(tmp_path, "source", corpus["source_hashes"][0]["path"]).unlink()
    elif name == "source_inventory":
        corpus["source_hashes"] = [
            row for row in corpus["source_hashes"] if row["path"] != "backend/verify_s3_evidence.py"
        ]
        corpus["source_manifest_sha256"] = manifest_sha256(corpus["source_hashes"])
        report["source_hashes"] = copy.deepcopy(corpus["source_hashes"])
        report["source_manifest_sha256"] = corpus["source_manifest_sha256"]
        corpus_path.write_bytes(json_bytes(corpus))
        report["corpus_sha256"] = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    elif name == "source_digest":
        report["source_hashes"][0]["sha256"] = "e" * 64
    elif name == "source_manifest":
        report["source_manifest_sha256"] = "e" * 64
    elif name == "private_limitation":
        report["limitations"][0] = "C:/Users/unit/state.sqlite3"
    if name not in {"missing", "empty", "same_path", "malformed", "duplicate"}:
        report_path.write_bytes(json_bytes(report))
    with pytest.raises(AcceptanceFailure):
        validate_files(report_path, corpus_path)


def test_passive_rechecks_revision_after_full_inventory(tmp_path: Path, monkeypatch) -> None:
    report_path, corpus_path, _, _ = install_artifacts(tmp_path, monkeypatch)
    count = 0

    def snapshot():
        nonlocal count
        count += 1
        return {
            "tested_commit": SHA if count == 1 else "c" * 40,
            "tested_tree": TREE,
            "working_tree_dirty": False,
            "tracked_dirty": False,
        }

    monkeypatch.setattr(passive, "repository_snapshot", snapshot, raising=False)
    with pytest.raises(AcceptanceFailure):
        validate_files(report_path, corpus_path)


def test_request_consumes_original_bytes_and_snapshots_safe_input(tmp_path: Path) -> None:
    proof = producer.FoundationProof(tmp_path / "state.sqlite3")
    entry = case(corpus_fixture(), "watchlist_created")
    captured = []

    def respond(request):
        captured.append((request.method, request.url.path, json.loads(request.content)))
        body = json.loads(entry["body_utf8"])
        body["meta"]["correlationId"] = request.headers["X-Correlation-ID"]
        entry["body_utf8"] = json_bytes(body).decode("utf-8")
        return httpx.Response(
            201,
            content=entry["body_utf8"].encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    client = httpx.Client(transport=httpx.MockTransport(respond), base_url="http://127.0.0.1")
    proof.native = SimpleNamespace(current_client=lambda: client, tokens=set(), servers=[])
    payload = {"name": "Synthetic review list"}
    try:
        decoded = proof.request(
            "watchlist_create", None, payload=payload, status=201, case_id="watchlist_created"
        )
        payload["name"] = "Later caller change"
        assert decoded.get("watchlist_id") == WL
        assert captured == [("POST", "/api/v1/local-watchlists", {"name": "Synthetic review list"})]
        assert proof.cases["watchlist_created"]["request"] == {"name": "Synthetic review list"}
        assert proof.cases["watchlist_created"]["body_utf8"] == entry["body_utf8"]
    finally:
        client.close()


def test_successful_mocked_evaluation_reaps_before_owned_cleanup(
    tmp_path: Path, monkeypatch
) -> None:
    events = []
    original = corpus_fixture()

    class FakeServer:
        def __init__(self, pid):
            self.process = SimpleNamespace(pid=pid)
            self.reaped = False

        def stop(self):
            events.append("stop")
            self.reaped = True

    class FakeProof:
        def __init__(self, database):
            self.database = database
            self.private_identities = set()
            self.responses_checked = 170
            self.cases = {item["id"]: copy.deepcopy(item) for item in original["cases"]}
            self.checks = [{"id": item, "passed": True} for item in CHECK_IDS[:-1]]
            self.native = SimpleNamespace(
                servers=[FakeServer(pid) for pid in range(101, 107)],
                tokens=set(),
                ttl_elapsed=60.125,
            )
            self.durable_restarts = 2
            self.storage_fault_restarts = 2

        def run(self):
            events.append("run")
            fixture_path(tmp_path, self.database.relative_to(tmp_path).as_posix()).touch()

        def mark(self, identifier):
            self.checks.append({"id": identifier, "passed": True})
            events.append(identifier)

    monkeypatch.setattr(producer, "FoundationProof", FakeProof)
    monkeypatch.setattr(producer, "ROOT", tmp_path / "checkout")
    monkeypatch.setattr(producer, "_temp_base", lambda: tmp_path, raising=False)
    monkeypatch.setattr(
        producer,
        "repository_provenance",
        lambda sha, tree: {
            "tested_commit": sha,
            "tested_tree": tree,
            "working_tree_dirty": False,
            "tracked_dirty": False,
        },
        raising=False,
    )
    monkeypatch.setattr(
        producer, "runtime_hashes", lambda: copy.deepcopy(original["source_hashes"])
    )
    monkeypatch.setattr(
        producer,
        "_git",
        lambda args: TREE if "HEAD^{tree}" in args else SHA if args[:1] == ["rev-parse"] else "",
        raising=False,
    )
    report, corpus = producer.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report.get("success") is True
    assert corpus is not None
    assert events == ["run", *(["stop"] * 6), "owned_cleanup"]
    assert report["native_process"]["temporary_directory_removed"] is True
    assert not list(tmp_path.glob("finex-s1-acceptance-*"))


@pytest.mark.parametrize("scope", ["body", "corpus", "report"])
@pytest.mark.parametrize("member", ["plain", "escaped", "nested"])
def test_duplicate_overwritten_private_json_cannot_be_hidden(
    tmp_path: Path, monkeypatch, scope: str, member: str
) -> None:
    marker = secrets.token_urlsafe(32)
    unsafe = json.dumps("Bearer " + marker).encode("utf-8")
    if scope == "body":
        entry = case(corpus_fixture(), "search_default")
        raw = entry["body_utf8"].encode("utf-8")
        key = b'"message"' if member != "nested" else b'"correlationId"'
        equivalent = b'"messa\\u0067e"' if member == "escaped" else key
        raw = raw.replace(key + b":", equivalent + b":" + unsafe + b"," + key + b":", 1)
        with pytest.raises(AcceptanceFailure) as caught:
            producer.wire_body(raw, "search", 200, None, target=entry["target"])
    else:
        report_path, corpus_path, report, _ = install_artifacts(tmp_path, monkeypatch)
        path = corpus_path if scope == "corpus" else report_path
        raw = path.read_bytes()
        key = b'"schema_version"' if member != "nested" else b'"tested_commit"'
        equivalent = b'"schema_versi\\u006fn"' if member == "escaped" else key
        raw = raw.replace(key + b":", equivalent + b":" + unsafe + b"," + key + b":", 1)
        path.write_bytes(raw)
        if scope == "corpus":
            report["corpus_sha256"] = hashlib.sha256(raw).hexdigest()
            report_path.write_bytes(json_bytes(report))
        with pytest.raises(AcceptanceFailure) as caught:
            validate_files(report_path, corpus_path)
    assert marker not in str(caught.value)


@pytest.mark.parametrize("changed", ["report", "corpus", "source"])
def test_passive_detects_artifact_and_source_changes_during_validation(
    tmp_path: Path, monkeypatch, changed: str
) -> None:
    report_path, corpus_path, _, corpus = install_artifacts(tmp_path, monkeypatch)
    calls = 0

    def snapshot():
        nonlocal calls
        calls += 1
        if calls == 2:
            path = (
                report_path
                if changed == "report"
                else corpus_path
                if changed == "corpus"
                else fixture_path(tmp_path, "source", corpus["source_hashes"][0]["path"])
            )
            path.write_bytes(path.read_bytes() + b"\n")
        return {
            "tested_commit": SHA,
            "tested_tree": TREE,
            "working_tree_dirty": False,
            "tracked_dirty": False,
        }

    monkeypatch.setattr(passive, "repository_snapshot", snapshot)
    with pytest.raises(AcceptanceFailure):
        validate_files(report_path, corpus_path)


@pytest.mark.parametrize("name", ["linked", "directory", "oversized", "inside_checkout"])
def test_passive_artifact_file_capability_is_bounded_and_regular(
    tmp_path: Path, monkeypatch, name: str
) -> None:
    report_path, corpus_path, _, _ = install_artifacts(tmp_path, monkeypatch)
    if name == "linked":
        original = passive._linked
        monkeypatch.setattr(passive, "_linked", lambda path: path == report_path or original(path))
    elif name == "directory":
        report_path = report_path.parent
    elif name == "oversized":
        report_path.write_bytes(b" " * (producer.MAX_ARTIFACT + 1))
    elif name == "inside_checkout":
        moved = fixture_path(tmp_path, "source", "inside.json")
        moved.write_bytes(report_path.read_bytes())
        report_path = moved
    with pytest.raises(AcceptanceFailure):
        validate_files(report_path, corpus_path)


@pytest.mark.parametrize(
    "name",
    [
        "unfinished_checks",
        "failed_check",
        "missing_case",
        "duplicate_pid",
        "insufficient_starts",
        "wrong_restart",
        "expiry_below",
        "run_failure",
        "stop_failure",
        "not_reaped",
        "source_change",
        "revision_change",
        "dirty",
        "unsafe_base",
    ],
)
def test_evaluation_failure_never_returns_corpus_or_claims_cleanup(
    tmp_path: Path, monkeypatch, name: str
) -> None:
    original = corpus_fixture()
    runs = []

    class FakeServer:
        def __init__(self, pid):
            self.process = SimpleNamespace(pid=pid)
            self.reaped = False

        def stop(self):
            self.reaped = name != "not_reaped"
            if name == "stop_failure":
                raise AcceptanceFailure("CHILD_CLEANUP_FAILED")

    class FakeProof:
        def __init__(self, database):
            self.database = database
            self.private_identities = set()
            self.responses_checked = 170
            self.cases = {item["id"]: copy.deepcopy(item) for item in original["cases"]}
            self.checks = [{"id": item, "passed": True} for item in CHECK_IDS[:-1]]
            servers = [FakeServer(pid) for pid in range(101, 107)]
            if name == "duplicate_pid":
                servers[-1].process.pid = servers[0].process.pid
            if name == "insufficient_starts":
                servers.pop()
            self.native = SimpleNamespace(
                servers=servers,
                tokens=set(),
                ttl_elapsed=58.999 if name == "expiry_below" else 60.125,
            )
            self.durable_restarts = 1 if name == "wrong_restart" else 2
            self.storage_fault_restarts = 2
            if name == "unfinished_checks":
                self.checks.pop()
            if name == "failed_check":
                self.checks[0]["passed"] = False
            if name == "missing_case":
                self.cases.pop("search_default")

        def run(self):
            runs.append(True)
            fixture_path(tmp_path, self.database.relative_to(tmp_path).as_posix()).touch()
            if name == "run_failure":
                raise AcceptanceFailure("PROBE_FAILED")

        def mark(self, identifier):
            self.checks.append({"id": identifier, "passed": True})

    monkeypatch.setattr(producer, "FoundationProof", FakeProof)
    checkout = fixture_path(tmp_path, "checkout")
    monkeypatch.setattr(producer, "ROOT", checkout)
    monkeypatch.setattr(
        producer, "_temp_base", lambda: checkout if name == "unsafe_base" else tmp_path
    )
    if name == "unsafe_base":
        checkout.mkdir()
    monkeypatch.setattr(
        producer,
        "repository_provenance",
        lambda sha, tree: {
            "tested_commit": sha,
            "tested_tree": tree,
            "working_tree_dirty": name == "dirty",
            "tracked_dirty": False,
        },
    )
    reads = 0

    def hashes():
        nonlocal reads
        reads += 1
        rows = copy.deepcopy(original["source_hashes"])
        if name == "source_change" and reads > 1:
            rows[0]["sha256"] = "e" * 64
        return rows

    monkeypatch.setattr(producer, "runtime_hashes", hashes)
    monkeypatch.setattr(
        producer,
        "_git",
        lambda args: (
            TREE
            if "HEAD^{tree}" in args
            else ("c" * 40 if name == "revision_change" else SHA)
            if args[:1] == ["rev-parse"]
            else ""
        ),
    )
    report, corpus = producer.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False
    assert corpus is None
    assert report["corpus_sha256"] is None
    assert report["corpus_case_ids"] == []
    assert not any(row["id"] == "owned_cleanup" for row in report["checks"])
    if name in {"dirty", "unsafe_base"}:
        assert runs == []
    if name == "not_reaped":
        assert report["native_process"]["temporary_directory_removed"] is False


@pytest.mark.parametrize(
    "name", ["report_exists", "corpus_exists", "same_paths", "output_inside_checkout", "bad_cli"]
)
def test_cli_preflight_never_runs_or_overwrites_existing_output(
    tmp_path: Path, monkeypatch, capsys, name: str
) -> None:
    calls = []
    marker = b"Existing synthetic output\n"
    report_path = fixture_path(tmp_path, "report.json")
    corpus_path = fixture_path(tmp_path, "corpus.json")
    if name == "report_exists":
        report_path.write_bytes(marker)
    elif name == "corpus_exists":
        corpus_path.write_bytes(marker)
    elif name == "same_paths":
        corpus_path = report_path
    elif name == "output_inside_checkout":
        checkout = fixture_path(tmp_path, "checkout")
        checkout.mkdir()
        monkeypatch.setattr(producer, "ROOT", checkout)
        report_path = fixture_path(tmp_path, "checkout", "output.json")
    monkeypatch.setattr(producer, "evaluate_acceptance", lambda **kwargs: calls.append(kwargs))
    args = [
        "--tested-sha",
        SHA,
        "--tested-tree",
        TREE,
        "--report",
        str(report_path),
        "--corpus",
        str(corpus_path),
    ]
    if name == "bad_cli":
        args += ["--secret", secrets.token_urlsafe(32)]
    assert producer.main(args) == 1
    assert calls == []
    capsys.readouterr()
    if name == "report_exists":
        assert report_path.read_bytes() == marker
    if name == "corpus_exists":
        assert corpus_path.read_bytes() == marker


def test_current_metadata_owner_and_foreign_markers_are_independently_observed(
    tmp_path: Path,
) -> None:
    import sqlite3

    database = fixture_path(tmp_path, "state.sqlite3")
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_metadata(version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_metadata(version) VALUES(4)")
    proof = producer.FoundationProof(database)
    proof.verify_schema()
    for statement in (
        "UPDATE schema_metadata SET version=3",
        "PRAGMA user_version=4",
        "PRAGMA application_id=195",
    ):
        with sqlite3.connect(database) as connection:
            connection.execute("UPDATE schema_metadata SET version=4")
            connection.execute("PRAGMA user_version=0")
            connection.execute("PRAGMA application_id=0")
            connection.execute(statement)
        before = database.read_bytes()
        with pytest.raises(AcceptanceFailure):
            proof.verify_schema()
        assert database.read_bytes() == before


def test_owned_fault_guard_rejects_arbitrary_or_live_database(tmp_path: Path, monkeypatch) -> None:
    database = fixture_path(tmp_path, "state.sqlite3")
    database.touch()
    proof = producer.FoundationProof(database)
    monkeypatch.setattr(producer, "_temp_base", lambda: tmp_path)
    with pytest.raises(AcceptanceFailure):
        proof.owned_database()
    parent = fixture_path(tmp_path, "finex-s1-acceptance-owned-unit")
    parent.mkdir()
    owned = fixture_path(tmp_path, "finex-s1-acceptance-owned-unit", "state.sqlite3")
    owned.touch()
    proof = producer.FoundationProof(owned)
    proof.native = SimpleNamespace(servers=[SimpleNamespace(reaped=False)])
    with pytest.raises(AcceptanceFailure):
        proof.owned_database()
    proof.native.servers[0].reaped = True
    proof.owned_database()


def install_path_signal(monkeypatch, state: dict) -> None:
    """Simulate OS path metadata only; never create an actual junction/link."""
    original_lstat = Path.lstat
    original_junction = getattr(Path, "is_junction", lambda path: False)

    class StatProxy:
        def __init__(self, original):
            self.original = original
            self.st_file_attributes = getattr(original, "st_file_attributes", 0) | 1024

        def __getattr__(self, name):
            return getattr(self.original, name)

    def lstat(path):
        result = original_lstat(path)
        return (
            StatProxy(result)
            if state.get("signal") == "reparse" and path == state.get("target")
            else result
        )

    def is_junction(path):
        return (
            state.get("signal") == "junction" and path == state.get("target")
        ) or original_junction(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "is_junction", is_junction, raising=False)


@pytest.mark.parametrize("signal", ["reparse", "junction"])
@pytest.mark.parametrize("component", ["database", "workspace", "base", "ancestor"])
def test_fault_mutation_rejects_every_reparse_capability_before_sql(
    tmp_path: Path, monkeypatch, signal: str, component: str
) -> None:
    """Real temp paths, simulated metadata and SQL spy; zero real mutation."""
    base = fixture_path(tmp_path, "temporary-base")
    base.mkdir()
    workspace = fixture_path(tmp_path, "temporary-base", "finex-s1-acceptance-fault-control")
    workspace.mkdir()
    database = fixture_path(
        tmp_path, "temporary-base", "finex-s1-acceptance-fault-control", "state.sqlite3"
    )
    database.touch()
    proof = producer.FoundationProof(database)
    targets = {"database": database, "workspace": workspace, "base": base, "ancestor": tmp_path}
    state = {"signal": signal, "target": targets[component]}
    install_path_signal(monkeypatch, state)
    monkeypatch.setattr(producer, "_temp_base", lambda: base)
    calls = []
    marker = 0

    class FakeConnection:
        def execute(self, statement):
            nonlocal marker
            calls.append("sql")
            if statement == "PRAGMA application_id=195":
                marker = 195
            elif statement == "PRAGMA application_id=0":
                marker = 0
            self.statement = statement
            return self

        def fetchone(self):
            return (marker,) if self.statement == "PRAGMA application_id" else (0,)

        def fetchall(self):
            return [(4,)]

        def close(self):
            pass

    def connect(*args, **kwargs):
        calls.append("connect")
        return FakeConnection()

    class FakeServer:
        reaped = False

        def stop(self):
            self.reaped = True

    servers = [FakeServer()]

    def start():
        replacement = FakeServer()
        servers.append(replacement)
        return replacement

    proof.native = SimpleNamespace(servers=servers, current_server=lambda: servers[-1], start=start)
    monkeypatch.setattr(producer, "sqlite3", SimpleNamespace(connect=connect))
    monkeypatch.setattr(proof, "request", lambda *args, **kwargs: {})
    with pytest.raises(AcceptanceFailure):
        proof.database_fault("memory-only-unit-input", {})
    assert calls == []


@pytest.mark.parametrize("signal", ["reparse", "junction"])
@pytest.mark.parametrize("component", ["database", "workspace", "base", "ancestor"])
def test_owned_cleanup_rejects_every_reparse_capability_without_recursive_delete(
    tmp_path: Path, monkeypatch, signal: str, component: str
) -> None:
    """No rmtree is executed; spy proves rejected metadata cannot reach it."""
    corpus = corpus_fixture()
    base = fixture_path(tmp_path, "temporary-base")
    base.mkdir()
    state = {"signal": signal, "target": None}
    install_path_signal(monkeypatch, state)
    deletions = []

    class FakeServer:
        def __init__(self, pid):
            self.process = SimpleNamespace(pid=pid)
            self.reaped = False

        def stop(self):
            self.reaped = True

    class FakeProof:
        def __init__(self, database):
            self.database = fixture_path(tmp_path, database.relative_to(tmp_path).as_posix())
            self.private_identities = set()
            self.responses_checked = 170
            self.cases = {item["id"]: copy.deepcopy(item) for item in corpus["cases"]}
            self.checks = [{"id": identifier, "passed": True} for identifier in CHECK_IDS[:-1]]
            self.native = SimpleNamespace(
                servers=[FakeServer(pid) for pid in range(101, 107)],
                tokens=set(),
                ttl_elapsed=60.125,
            )
            self.durable_restarts = self.storage_fault_restarts = 2

        def run(self):
            self.database.touch()
            state["target"] = {
                "database": self.database,
                "workspace": self.database.parent,
                "base": base,
                "ancestor": tmp_path,
            }[component]

        def mark(self, identifier):
            self.checks.append({"id": identifier, "passed": True})

    monkeypatch.setattr(producer, "FoundationProof", FakeProof)
    monkeypatch.setattr(producer, "ROOT", fixture_path(tmp_path, "checkout"))
    monkeypatch.setattr(producer, "_temp_base", lambda: base)
    monkeypatch.setattr(
        producer,
        "repository_provenance",
        lambda sha, tree: {
            "tested_commit": sha,
            "tested_tree": tree,
            "working_tree_dirty": False,
            "tracked_dirty": False,
        },
    )
    monkeypatch.setattr(producer, "runtime_hashes", lambda: copy.deepcopy(corpus["source_hashes"]))
    monkeypatch.setattr(
        producer,
        "_git",
        lambda args: TREE if "HEAD^{tree}" in args else SHA if args[:1] == ["rev-parse"] else "",
    )
    monkeypatch.setattr(
        producer, "shutil", SimpleNamespace(rmtree=lambda path: deletions.append(True))
    )
    report, returned = producer.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert deletions == []
    assert report["success"] is False
    assert returned is None
    assert report["failures"] == [{"code": "TEMPORARY_DIRECTORY_UNSAFE"}]
    assert report["native_process"]["temporary_directory_removed"] is False


def test_exact_driver_flow_with_inprocess_api_and_mock_children_is_not_native_evidence(
    tmp_path: Path, monkeypatch
) -> None:
    """Exercise real serializers/SQL; time and child restarts remain unit mocks."""
    import tempfile
    from datetime import datetime, timedelta, timezone

    from fastapi.testclient import TestClient

    from tests.support.local_s3_client import Clock, application
    from verify_s1_application import NativeProof

    clock = Clock()
    simulated = 0.0
    events = []

    class FakeTime:
        @staticmethod
        def monotonic():
            return simulated

        @staticmethod
        def sleep(seconds):
            nonlocal simulated
            simulated += seconds
            clock.now += timedelta(seconds=seconds)

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now.astimezone(tz or timezone.utc)

    class FakeServer:
        def __init__(self, database, mode, pid):
            database = fixture_path(tmp_path, database.relative_to(tmp_path).as_posix())
            self.process = SimpleNamespace(pid=pid)
            self.client = TestClient(
                application(database, clock, enabled=mode != "disabled", ttl=1)
            )
            self.client.headers["X-Correlation-ID"] = "unit-s3-driver"
            self.reaped = False
            events.append("start_" + mode)

        def stop(self):
            if self.client is not None:
                self.client.close()
                self.client = None
            self.reaped = True
            events.append("stop")

    class MockNativeProof(NativeProof):
        def start(self, mode="enabled"):
            server = FakeServer(self.database, mode, 100 + len(self.servers))
            self.servers.append(server)
            self.server = server
            return server

    monkeypatch.setattr(producer, "NativeProof", MockNativeProof)
    monkeypatch.setattr(producer, "_temp_base", lambda: tmp_path)
    monkeypatch.setattr(producer, "time", FakeTime)
    monkeypatch.setattr(producer, "datetime", FakeDateTime)
    with tempfile.TemporaryDirectory(prefix="finex-s1-acceptance-", dir=tmp_path) as owned:
        proof = producer.FoundationProof(Path(owned) / "state.sqlite3")
        try:
            proof.run()
            assert proof.checks == [
                {"id": identifier, "passed": True} for identifier in CHECK_IDS[:-1]
            ]
            assert len(proof.native.servers) == 6
            assert proof.durable_restarts == proof.storage_fault_restarts == 2
            assert proof.native.ttl_elapsed == 60.0
            assert set(proof.cases) == {row[0] for row in SPECS}
            corpus = corpus_fixture()
            corpus["cases"] = [proof.cases[identifier] for identifier, _, _, _ in SPECS]
            producer.validate_corpus(corpus)
            assert sum(event.startswith("start_") for event in events) == 6
        finally:
            for server in proof.native.servers:
                server.stop()
