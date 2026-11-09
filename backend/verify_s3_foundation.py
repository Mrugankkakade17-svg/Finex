"""Owned synthetic S3 TCP evidence; never full S3 or real-market acceptance."""

from __future__ import annotations

import argparse
import copy
import hashlib
import math
import os
import re
import shutil
import sqlite3
import stat
import sys
import tempfile
import time
import unicodedata
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NoReturn
from uuid import uuid4

from pydantic import BaseModel

from app.ports.adapters.sqlite_local_schema import SCHEMA_VERSION
from app.schemas.local_foundation import (
    MarketQuoteData,
    MarketSearchData,
    PaperAccountData,
    PaperLedgerData,
    WatchlistCollectionData,
    WatchlistData,
    WatchlistDeletedData,
    WatchlistItemData,
    WatchlistItemRemovedData,
)
from local_s2_evidence import (
    PRIVATE_KEYS,
    json_bytes,
    loads,
    manifest_sha256,
    output_target,
    reflects_private,
    safe_object,
    write_new_json,
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
    _git,
    _require,
    _temp_base,
    _utc,
    repository_provenance,
)
from verify_s2_manual_portfolio import PortfolioProof
from verify_s2_saved_risk import SavedRiskProof, risk_input

FOUNDATION_VERSION = "market_foundation.v1"
COMMAND = "python verify_s3_foundation.py"
CORPUS_SCHEMA = "finex.local_s3.foundation_corpus.v1"
REPORT_SCHEMA = "finex.local_s3.foundation.acceptance.v1"
MAX_BODY = 262144
MAX_ARTIFACT = 2097152
FIXTURE_TIME = "2026-01-01T00:00:00Z"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
INSTRUMENT = re.compile(r"SYN:[A-Z][A-Z0-9_]{0,31}\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
APP_SOURCE = re.compile(r"backend/app/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_-]+\.py\Z")
SCOPE_FIELDS = {
    "scope": SCOPE,
    "contract_version": CONTRACT_VERSION,
    "foundation_version": FOUNDATION_VERSION,
}
DEFAULT_INSTRUMENTS = (
    ("SYN:AAPL", "Synthetic Apple example", "EQUITY", "TECHNOLOGY"),
    ("SYN:BND", "Synthetic bond-fund example", "BOND", "FIXED_INCOME"),
    ("SYN:MSFT", "Synthetic Microsoft example", "EQUITY", "TECHNOLOGY"),
    ("SYN:UNAVAILABLE", "Synthetic unavailable-price example", "EQUITY", "GENERAL"),
)
DEFAULT_PRICES = {
    "SYN:AAPL": "200.0000",
    "SYN:BND": "80.0000",
    "SYN:MSFT": "400.0000",
    "SYN:UNAVAILABLE": None,
}
DATA_MODELS: dict[str, type[BaseModel]] = {
    "search": MarketSearchData,
    "quote": MarketQuoteData,
    "watchlists": WatchlistCollectionData,
    "watchlist_create": WatchlistData,
    "watchlist_update": WatchlistData,
    "watchlist_detail": WatchlistData,
    "watchlist_delete": WatchlistDeletedData,
    "watchlist_item_put": WatchlistItemData,
    "watchlist_item_delete": WatchlistItemRemovedData,
    "account": PaperAccountData,
    "account_open": PaperAccountData,
    "ledger": PaperLedgerData,
}
REQUIRED_CHECKS = (
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
CASE_SPECS = (
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
CASE_IDS = tuple(row[0] for row in CASE_SPECS)
CASE_MAP = {row[0]: row[1:] for row in CASE_SPECS}
SOURCE_PATHS = frozenset(
    {
        "backend/local_s2_evidence.py",
        "backend/verify_s1_application.py",
        "backend/verify_s2_manual_portfolio.py",
        "backend/verify_s2_saved_risk.py",
        "backend/verify_s3_foundation.py",
        "backend/verify_s3_evidence.py",
        "backend/tests/unit/test_verify_s3_foundation.py",
        "backend/tests/support/local_s3_client.py",
        "backend/tests/contract/test_local_s3_foundation_api.py",
        "backend/tests/contract/test_local_s3_foundation_failures.py",
        "backend/tests/contract/test_local_s3_faults.py",
        "backend/tests/contract/test_local_s3_review_controls.py",
        "backend/tests/contract/test_local_s3_openapi.py",
        "backend/tests/unit/test_local_s3_schema.py",
        "backend/tests/integration/test_local_s3_foundation_atomicity.py",
        "data/fixtures/local_s1/contract_cases.v1.json",
        "docs/features/local-application/S3-market-foundation-contract.md",
        "ai/risk/contract.py",
        "ai/risk/scoring.py",
        "backend/data/questionnaire/risk_questionnaire_v1.json",
    }
)


def private(value: object, *, depth: int = 0) -> bool:
    """Inspect body/request values only, not legitimate repository source paths."""
    if depth > 32:
        return True
    if isinstance(value, dict):
        names = {re.sub(r"[^a-z0-9]", "", key.lower()) for key in PRIVATE_KEYS}
        return any(
            not isinstance(key, str)
            or re.sub(r"[^a-z0-9]", "", key.lower()) in names
            or private(child, depth=depth + 1)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(private(child, depth=depth + 1) for child in value)
    return isinstance(value, str) and bool(
        re.search(
            r"Bearer\s|github_pat_|(?:[A-Za-z]:[\\/]|file://|/(?:Users|home|tmp|var)/)",
            value,
            re.IGNORECASE,
        )
        or re.search(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])", value)
    )


def _text(value: object, maximum: int = 2000) -> None:
    _require(
        isinstance(value, str) and 1 <= len(value) <= maximum and not private(value), "WIRE_INVALID"
    )


def _uuid(value: object) -> None:
    _require(isinstance(value, str) and UUID.fullmatch(value) is not None, "WIRE_INVALID")


def _instrument(value: object) -> None:
    _require(isinstance(value, str) and INSTRUMENT.fullmatch(value) is not None, "WIRE_INVALID")


def _target(operation: str, target: object) -> dict[str, Any] | None:
    if operation in {"watchlists", "watchlist_create", "account", "account_open"}:
        _require(target is None, "WIRE_INVALID")
        return None
    if operation == "search":
        value = safe_object(target, {"query", "limit"})
        query, limit = value["query"], value["limit"]
        _require(
            isinstance(query, str)
            and query == query.strip()
            and len(query) <= 80
            and not any(unicodedata.category(char) == "Cc" for char in query)
            and type(limit) is int
            and 1 <= limit <= 20,
            "WIRE_INVALID",
        )
        return value
    if operation == "quote":
        value = safe_object(target, {"instrument_id"})
        _instrument(value["instrument_id"])
        return value
    if operation in {"watchlist_detail", "watchlist_update", "watchlist_delete"}:
        value = safe_object(target, {"watchlist_id"})
        _uuid(value["watchlist_id"])
        return value
    if operation in {"watchlist_item_put", "watchlist_item_delete"}:
        value = safe_object(target, {"watchlist_id", "instrument_id"})
        _uuid(value["watchlist_id"])
        _instrument(value["instrument_id"])
        return value
    if operation == "ledger":
        value = safe_object(target, {"limit", "after_sequence"})
        _require(
            type(value["limit"]) is int
            and 1 <= value["limit"] <= 100
            and type(value["after_sequence"]) is int
            and 0 <= value["after_sequence"] <= 9007199254740991,
            "WIRE_INVALID",
        )
        return value
    raise AcceptanceFailure("WIRE_INVALID")


def _input(operation: str, request: object) -> None:
    _require(not private(request), "WIRE_INVALID")
    if operation in {"watchlist_create", "watchlist_update"}:
        value = safe_object(request, {"name"})
        name = value["name"]
        _require(isinstance(name, str) and 1 <= len(name.strip()) <= 100, "WIRE_INVALID")
    elif operation == "account_open":
        value = safe_object(request, {"foundation_version", "currency"})
        _require(
            value == {"foundation_version": FOUNDATION_VERSION, "currency": "USD"}, "WIRE_INVALID"
        )
    else:
        _require(request is None, "WIRE_INVALID")


def _error_status(operation: str, code: str) -> int | None:
    common = {
        "SESSION_INVALID": 401,
        "LOCAL_APPLICATION_ONLY": 403,
        "ONBOARDING_REQUIRED": 409,
        "VALIDATION_ERROR": 422,
        "LOCAL_STORE_UNAVAILABLE": 503,
    }
    if code in common:
        return common[code]
    specific = {
        "search": {"LOCAL_CATALOG_UNAVAILABLE": 503},
        "quote": {
            "LOCAL_CATALOG_UNAVAILABLE": 503,
            "LOCAL_QUOTE_UNAVAILABLE": 503,
            "INSTRUMENT_NOT_FOUND": 404,
        },
        "watchlist_create": {"WATCHLIST_LIMIT": 409},
        "watchlist_detail": {"WATCHLIST_NOT_FOUND": 404, "LOCAL_CATALOG_UNAVAILABLE": 503},
        "watchlist_update": {"WATCHLIST_NOT_FOUND": 404, "LOCAL_CATALOG_UNAVAILABLE": 503},
        "watchlist_delete": {"WATCHLIST_NOT_FOUND": 404},
        "watchlist_item_put": {
            "WATCHLIST_NOT_FOUND": 404,
            "INSTRUMENT_NOT_FOUND": 404,
            "WATCHLIST_ITEM_LIMIT": 409,
            "LOCAL_CATALOG_UNAVAILABLE": 503,
        },
        "watchlist_item_delete": {
            "WATCHLIST_NOT_FOUND": 404,
            "INSTRUMENT_NOT_FOUND": 404,
            "LOCAL_CATALOG_UNAVAILABLE": 503,
        },
        "account_open": {"MARKET_FOUNDATION_VERSION_MISMATCH": 409},
        "ledger": {"PAPER_ACCOUNT_NOT_OPEN": 404},
    }
    return specific.get(operation, {}).get(code)


def _data(
    operation: str, value: object, target: dict[str, Any] | None, request: object
) -> dict[str, Any]:
    try:
        model = DATA_MODELS[operation].model_validate(value)
        data = model.model_dump(mode="json")
    except Exception:
        raise AcceptanceFailure("WIRE_INVALID") from None
    _require(data == value, "WIRE_INVALID")
    if target is not None:
        for key in ("watchlist_id", "instrument_id", "query", "limit", "after_sequence"):
            if key in target:
                if key == "instrument_id" and operation == "watchlist_item_put":
                    _require(data["item"][key] == target[key], "WIRE_INVALID")
                else:
                    _require(data[key] == target[key], "WIRE_INVALID")
    if operation in {"watchlist_create", "watchlist_update"}:
        payload = safe_object(request, {"name"})
        _require(data["name"] == payload["name"].strip(), "WIRE_INVALID")
        if operation == "watchlist_create":
            _require(
                data["items"] == []
                and data["item_count"] == 0
                and _utc(data["created_at"]) == _utc(data["updated_at"]),
                "WIRE_INVALID",
            )
    if operation in {"account", "account_open"}:
        account = data["account"]
        if account is not None:
            _require(account["cash_balance"] == "10000.00", "WIRE_INVALID")
        if operation == "account_open":
            _require(account is not None, "WIRE_INVALID")
    if operation == "ledger":
        _require(data["next_cursor"] is None and len(data["items"]) <= 1, "WIRE_INVALID")
        for item in data["items"]:
            _require(item["sequence"] == 1, "WIRE_INVALID")
    return data


def wire_body(
    raw: bytes,
    operation: str,
    status: int,
    code: str | None,
    *,
    target: object,
    request: object = None,
    forbidden: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Consume the original UTF-8 and confirm the exact public operation."""
    try:
        _require(
            type(status) is int and operation in DATA_MODELS and 0 < len(raw) <= MAX_BODY,
            "WIRE_INVALID",
        )
        captured_target = _target(operation, target)
        body = loads(raw)
        _require(not private(body) and not reflects_private(body, forbidden), "WIRE_INVALID")
        if code is not None:
            safe_object(body, {"success", "message", "detail", "error_code", "error"})
            inner = safe_object(body["error"], {"code", "message", "fieldErrors", "correlationId"})
            _text(body["message"])
            _require(
                _error_status(operation, code) == status
                and body["success"] is False
                and body["error_code"] == inner["code"] == code
                and body["message"] == body["detail"] == inner["message"]
                and isinstance(inner["correlationId"], str)
                and CID_PATTERN.fullmatch(inner["correlationId"]) is not None
                and isinstance(inner["fieldErrors"], list)
                and len(inner["fieldErrors"]) <= 50,
                "WIRE_INVALID",
            )
            for field in inner["fieldErrors"]:
                value = safe_object(field, {"field", "code"})
                for text in value.values():
                    _text(text, 200)
            return body
        _require(status == (201 if operation == "watchlist_create" else 200), "WIRE_INVALID")
        _input(operation, request)
        safe_object(body, {"success", "message", "data", "meta"})
        _text(body["message"])
        _require(body["success"] is True, "WIRE_INVALID")
        data = _data(operation, body["data"], captured_target, request)
        meta = safe_object(body["meta"], {"apiVersion", "dataStatus", "dataAsOf", "correlationId"})
        _require(
            meta["apiVersion"] == "v1"
            and isinstance(meta["correlationId"], str)
            and CID_PATTERN.fullmatch(meta["correlationId"]) is not None,
            "WIRE_INVALID",
        )
        expected_status, asof = "CACHED", None
        if operation == "search":
            asof = FIXTURE_TIME
        elif operation == "quote":
            asof = data["quote_as_of"]
            if data["unit_price"] is None:
                expected_status = "UNAVAILABLE"
        elif operation in {"watchlist_create", "watchlist_update", "watchlist_detail"}:
            asof = data["updated_at"]
        elif operation == "watchlist_item_put":
            asof = data["item"]["added_at"]
        elif operation in {"watchlist_delete", "watchlist_item_delete"}:
            _utc(meta["dataAsOf"])
            asof = meta["dataAsOf"]
        elif operation in {"account", "account_open"} and data["account"] is not None:
            asof = data["account"]["created_at"]
        elif operation == "ledger" and data["items"]:
            asof = data["items"][-1]["created_at"]
        _require(
            meta["dataStatus"] == expected_status
            and (
                (meta["dataAsOf"] is None and asof is None)
                or (asof is not None and _utc(meta["dataAsOf"]) == _utc(asof))
            ),
            "WIRE_INVALID",
        )
        return data
    except Exception:
        raise AcceptanceFailure("WIRE_INVALID") from None


def _default_instrument(value: dict[str, Any]) -> None:
    found = next((row for row in DEFAULT_INSTRUMENTS if row[0] == value["instrument_id"]), None)
    _require(found is not None, "CORPUS_INVALID")
    _require(
        tuple(value[key] for key in ("instrument_id", "display_name", "asset_class", "sector"))
        == found
        and value["currency"] == "USD",
        "CORPUS_INVALID",
    )


def _relationships(entries: dict[str, dict[str, Any]], values: dict[str, dict[str, Any]]) -> None:
    initial, filtered, empty = (
        values[key] for key in ("search_default", "search_filtered", "search_empty")
    )
    _require(
        [item["instrument_id"] for item in initial["items"]] == list(DEFAULT_PRICES),
        "CORPUS_INVALID",
    )
    _require(
        initial["query"] == ""
        and initial["limit"] == 20
        and filtered["query"] == "apple"
        and filtered["limit"] == 2
        and [item["instrument_id"] for item in filtered["items"]] == ["SYN:AAPL"]
        and empty["query"] == "no-match"
        and empty["items"] == [],
        "CORPUS_INVALID",
    )
    for item in initial["items"]:
        _default_instrument(item)
    for key, instrument in (
        ("quote_aapl", "SYN:AAPL"),
        ("quote_bond", "SYN:BND"),
        ("quote_msft", "SYN:MSFT"),
        ("quote_unavailable", "SYN:UNAVAILABLE"),
    ):
        quote = values[key]
        price = DEFAULT_PRICES[instrument]
        _require(
            quote["instrument_id"] == instrument
            and quote["unit_price"] == price
            and quote["status"] == ("UNAVAILABLE" if price is None else "CACHED"),
            "CORPUS_INVALID",
        )
    _require(values["quote_cache_hit"] == values["quote_aapl"], "CORPUS_INVALID")
    for key in ("watchlists_empty", "other_owner_empty"):
        _require(values[key]["items"] == [] and values[key]["count"] == 0, "CORPUS_INVALID")
    created = values["watchlist_created"]
    renamed = values["watchlist_renamed"]
    _require(
        created["name"] == "Synthetic review list"
        and renamed["name"] == "Synthetic review list renamed"
        and created["watchlist_id"] == renamed["watchlist_id"]
        and _utc(created["created_at"]) == _utc(renamed["created_at"])
        and _utc(renamed["updated_at"]) >= _utc(created["updated_at"]),
        "CORPUS_INVALID",
    )
    _require(
        values["watchlist_rename_noop"] == renamed
        and values["watchlist_item_added"] == values["watchlist_item_duplicate"],
        "CORPUS_INVALID",
    )
    detail = values["watchlist_detail"]
    added = values["watchlist_item_added"]
    _require(
        detail["watchlist_id"] == created["watchlist_id"] == added["watchlist_id"]
        and detail["items"] == [added["item"]]
        and detail["name"] == renamed["name"]
        and _utc(detail["updated_at"]) == _utc(added["item"]["added_at"]),
        "CORPUS_INVALID",
    )
    collection = values["watchlist_collection"]
    _require(
        collection["count"] == 2
        and any(
            row
            == {
                key: detail[key]
                for key in ("watchlist_id", "name", "created_at", "updated_at", "item_count")
            }
            for row in collection["items"]
        ),
        "CORPUS_INVALID",
    )
    for item in detail["items"]:
        _default_instrument(item)
    _require(
        values["watchlist_item_removed"] == values["watchlist_item_remove_noop"], "CORPUS_INVALID"
    )
    removed = values["watchlist_item_removed"]
    _require(
        removed["watchlist_id"] == created["watchlist_id"]
        and removed["instrument_id"] == "SYN:AAPL",
        "CORPUS_INVALID",
    )
    for key in ("unopened_account", "other_owner_unopened"):
        _require(values[key]["account"] is None, "CORPUS_INVALID")
    opened = values["opened_account"]
    for key in (
        "repeated_account_open",
        "account_after_restart",
        "account_after_recompletion",
        "account_after_watchlist_delete",
        "account_after_expiry_relogin",
        "restored_account",
    ):
        _require(values[key] == opened, "CORPUS_INVALID")
    account = opened["account"]
    ledger = values["opening_ledger"]
    _require(
        ledger["account_id"] == account["account_id"]
        and len(ledger["items"]) == 1
        and ledger["items"][0]["ledger_id"] == account["opening_ledger_id"]
        and _utc(ledger["items"][0]["created_at"]) == _utc(account["created_at"]),
        "CORPUS_INVALID",
    )
    _require(
        values["ledger_after_opening"]["items"] == []
        and values["ledger_after_opening"]["account_id"] == account["account_id"],
        "CORPUS_INVALID",
    )
    restarted = values["watchlist_after_restart"]
    _require(
        restarted["watchlist_id"] == created["watchlist_id"]
        and restarted["name"] == renamed["name"]
        and _utc(restarted["created_at"]) == _utc(created["created_at"])
        and len(restarted["items"]) == 1
        and restarted["items"][0]["instrument_id"] == "SYN:BND",
        "CORPUS_INVALID",
    )
    for item in restarted["items"]:
        _default_instrument(item)
    _require(
        values["watchlist_deleted"]["watchlist_id"] == created["watchlist_id"], "CORPUS_INVALID"
    )
    for identifier in ("watchlist_other_owner", "deleted_watchlist_not_found"):
        _require(
            entries[identifier]["target"]["watchlist_id"] == created["watchlist_id"],
            "CORPUS_INVALID",
        )
    for key in (
        "watchlist_rename_noop",
        "watchlist_item_duplicate",
        "watchlist_item_remove_noop",
        "repeated_account_open",
    ):
        first = {
            "watchlist_rename_noop": "watchlist_renamed",
            "watchlist_item_duplicate": "watchlist_item_added",
            "watchlist_item_remove_noop": "watchlist_item_removed",
            "repeated_account_open": "opened_account",
        }[key]
        _require(
            loads(entries[key]["body_utf8"].encode("utf-8"))["meta"]["dataAsOf"]
            == loads(entries[first]["body_utf8"].encode("utf-8"))["meta"]["dataAsOf"],
            "CORPUS_INVALID",
        )


def validate_corpus(corpus: object, *, forbidden: tuple[str, ...] = ()) -> None:
    """Validate all captured original bodies, dispatch bindings and relationships."""
    try:
        value = safe_object(
            corpus,
            {
                "schema_version",
                *SCOPE_FIELDS,
                "provenance",
                "source_hashes",
                "source_manifest_sha256",
                "cases",
            },
        )
        _require(
            value["schema_version"] == CORPUS_SCHEMA
            and all(value[key] == item for key, item in SCOPE_FIELDS.items())
            and len(json_bytes(value)) <= MAX_ARTIFACT,
            "CORPUS_INVALID",
        )
        provenance = safe_object(
            value["provenance"], {"kind", "source", "command", "tested_commit", "tested_tree"}
        )
        _require(
            provenance["kind"] == "native_tcp_capture"
            and provenance["source"] == "owned_loopback_uvicorn"
            and provenance["command"] == COMMAND
            and all(
                isinstance(provenance[key], str)
                and SHA_PATTERN.fullmatch(provenance[key]) is not None
                for key in ("tested_commit", "tested_tree")
            ),
            "CORPUS_INVALID",
        )
        rows = value["source_hashes"]
        _require(isinstance(rows, list) and 1 <= len(rows) <= 256, "CORPUS_INVALID")
        names = []
        for row in rows:
            item = safe_object(row, {"path", "sha256"})
            name = item["path"]
            _require(
                isinstance(name, str)
                and len(name) <= 256
                and (name in SOURCE_PATHS or APP_SOURCE.fullmatch(name) is not None)
                and isinstance(item["sha256"], str)
                and HASH.fullmatch(item["sha256"]) is not None,
                "CORPUS_INVALID",
            )
            names.append(name)
        _require(
            names == sorted(set(names))
            and SOURCE_PATHS <= set(names)
            and value["source_manifest_sha256"] == manifest_sha256(rows),
            "CORPUS_INVALID",
        )
        _require(
            isinstance(value["cases"], list) and len(value["cases"]) == len(CASE_IDS),
            "CORPUS_INVALID",
        )
        entries, data = {}, {}
        for identifier, supplied in zip(CASE_IDS, value["cases"], strict=True):
            entry = safe_object(
                supplied,
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
                entry["id"] == identifier
                and entry["operation"] == operation
                and type(entry["status"]) is int
                and entry["status"] == status
                and entry["content_type"] == "application/json"
                and isinstance(entry["body_utf8"], str),
                "CORPUS_INVALID",
            )
            expected = (
                {"outcome": "success"} if code is None else {"outcome": "error", "error_code": code}
            )
            _require(
                entry["expected"] == expected
                and not private(entry["request"])
                and not reflects_private(entry["request"], forbidden),
                "CORPUS_INVALID",
            )
            if code is not None:
                _require(entry["request"] is None, "CORPUS_INVALID")
            data[identifier] = wire_body(
                entry["body_utf8"].encode("utf-8"),
                operation,
                status,
                code,
                target=entry["target"],
                request=entry["request"],
                forbidden=forbidden,
            )
            entries[identifier] = entry
        _relationships(entries, data)
    except Exception:
        raise AcceptanceFailure("CORPUS_INVALID") from None


def runtime_hashes() -> list[dict[str, str]]:
    try:
        # The passive reader also rejects links, overlong files and read drift.
        # Import lazily: the passive module shares the frozen domain constants.
        from verify_s3_evidence import MAX_SOURCE, _path, regular_bytes

        names = set(SOURCE_PATHS)
        names.update(
            path.relative_to(ROOT).as_posix() for path in (ROOT / "backend/app").rglob("*.py")
        )
        rows = [
            {
                "path": name,
                "sha256": hashlib.sha256(
                    regular_bytes(_path(ROOT / name, external=False), MAX_SOURCE, source=True)
                ).hexdigest(),
            }
            for name in sorted(names)
        ]
        manifest_sha256(rows)
        return rows
    except Exception:
        raise AcceptanceFailure("PROVENANCE_UNAVAILABLE") from None


def _unlinked_path(path: Path, *, missing_leaf: bool = False) -> Path:
    """Check original path metadata/ancestors before any resolution follows it."""
    from verify_s3_evidence import _linked

    try:
        absolute = path.absolute()
        _require(not str(absolute).startswith(("\\\\", "//")), "TEMPORARY_DIRECTORY_UNSAFE")
        for component in (absolute, *absolute.parents):
            try:
                linked = _linked(component)
            except FileNotFoundError:
                _require(missing_leaf and component == absolute, "TEMPORARY_DIRECTORY_UNSAFE")
                continue
            _require(not linked, "TEMPORARY_DIRECTORY_UNSAFE")
        return absolute.resolve(strict=not missing_leaf)
    except Exception:
        raise AcceptanceFailure("TEMPORARY_DIRECTORY_UNSAFE") from None


def _temporary_base() -> Path:
    """Also inspect the unresolved origin used by the inherited temp selector."""
    origin = (
        Path(os.environ["LOCALAPPDATA"]) / "Temp"
        if os.name == "nt" and os.environ.get("LOCALAPPDATA")
        else Path(tempfile.gettempdir())
    )
    _unlinked_path(origin)
    base = _unlinked_path(_temp_base())
    _require(
        base.is_dir() and base != ROOT.resolve() and ROOT.resolve() not in base.parents,
        "TEMPORARY_DIRECTORY_UNSAFE",
    )
    return base


def _owned_workspace(workspace: Path, base: Path, database: Path) -> None:
    """Exact fresh temp capability; reject every reparse route before removal."""
    safe_base = _unlinked_path(base)
    safe_parent = _unlinked_path(workspace.parent)
    safe_workspace = _unlinked_path(workspace)
    safe_database = _unlinked_path(database, missing_leaf=True)
    root = ROOT.resolve()
    _require(
        safe_base.is_dir()
        and safe_workspace.is_dir()
        and safe_parent == safe_base
        and safe_workspace.parent == safe_base
        and workspace.name.startswith("finex-s1-acceptance-")
        and database.name == "state.sqlite3"
        and safe_database == safe_workspace / "state.sqlite3"
        and safe_workspace != root
        and root not in safe_workspace.parents
        and safe_base != root
        and root not in safe_base.parents,
        "TEMPORARY_DIRECTORY_UNSAFE",
    )
    # The producer creates only its database and SQLite sidecars. Refuse an
    # unexpected directory or redirected child rather than recursively touch it.
    children: list[Path] = []
    with os.scandir(workspace) as entries:
        for entry in entries:
            _require(len(children) < 4, "TEMPORARY_DIRECTORY_UNSAFE")
            children.append(workspace / entry.name)
    for child in children:
        safe_child = _unlinked_path(child)
        _require(
            child.name
            in {"state.sqlite3", "state.sqlite3-wal", "state.sqlite3-shm", "state.sqlite3-journal"}
            and safe_child.parent == safe_workspace
            and stat.S_ISREG(child.lstat().st_mode),
            "TEMPORARY_DIRECTORY_UNSAFE",
        )


class FoundationProof:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.cases: dict[str, dict[str, Any]] = {}
        self.checks: list[dict[str, object]] = []
        self.responses_checked = 0
        self.native = NativeProof(database)
        self.private_identities: set[str] = set()
        self.durable_restarts = 0
        self.storage_fault_restarts = 0

    def mark(self, identifier: str) -> None:
        _require(
            identifier in REQUIRED_CHECKS
            and identifier not in {item["id"] for item in self.checks},
            "PROBE_FAILED",
        )
        self.checks.append({"id": identifier, "passed": True})

    @staticmethod
    def route(operation: str, target: object) -> tuple[str, str, dict[str, str] | None]:
        value = _target(operation, target)
        if operation == "search" and value is not None:
            return (
                "GET",
                "/api/v1/local-market/instruments",
                {"query": value["query"], "limit": str(value["limit"])},
            )
        if operation == "quote" and value is not None:
            return "GET", "/api/v1/local-market/quotes/" + value["instrument_id"], None
        if operation in {"watchlists", "watchlist_create"}:
            return "GET" if operation == "watchlists" else "POST", "/api/v1/local-watchlists", None
        if operation.startswith("watchlist_") and value is not None:
            path = "/api/v1/local-watchlists/" + value["watchlist_id"]
            if operation in {"watchlist_item_put", "watchlist_item_delete"}:
                path += "/items/" + value["instrument_id"]
            methods = {
                "watchlist_detail": "GET",
                "watchlist_update": "PUT",
                "watchlist_delete": "DELETE",
                "watchlist_item_put": "PUT",
                "watchlist_item_delete": "DELETE",
            }
            return methods[operation], path, None
        if operation in {"account", "account_open"}:
            return (
                ("GET", "/api/v1/local-paper/account", None)
                if operation == "account"
                else ("POST", "/api/v1/local-paper/account/open", None)
            )
        if operation == "ledger" and value is not None:
            return (
                "GET",
                "/api/v1/local-paper/account/ledger",
                {key: str(value[key]) for key in ("limit", "after_sequence")},
            )
        raise AcceptanceFailure("CONFIGURATION_INVALID")

    def request(
        self,
        operation: str,
        token: str | None,
        *,
        target: object = None,
        payload: object = None,
        status: int = 200,
        code: str | None = None,
        case_id: str | None = None,
        raw_body: bytes | None = None,
    ) -> dict[str, Any]:
        method, path, query = self.route(operation, target)
        frozen_target, frozen_payload = copy.deepcopy(target), copy.deepcopy(payload)
        if case_id is not None:
            _require(
                case_id in CASE_MAP
                and case_id not in self.cases
                and CASE_MAP[case_id] == (operation, status, code),
                "PROBE_FAILED",
            )
        try:
            correlation = "s3-native-" + str(self.responses_checked)
            response = self.native.current_client().request(
                method,
                path,
                params=query,
                json=frozen_payload if raw_body is None else None,
                content=raw_body,
                headers={
                    "X-Correlation-ID": correlation,
                    **({"Authorization": "Bearer " + token} if token else {}),
                    **({"Content-Type": "application/json"} if raw_body is not None else {}),
                },
            )
            raw = response.content
            _require(
                response.status_code == status
                and not response.history
                and "set-cookie" not in response.headers
                and response.headers.get("content-type", "").split(";")[0] == "application/json",
                "WIRE_INVALID",
            )
            forbidden = (*self.native.tokens, *self.private_identities, str(self.database))
            _require(all(item.encode("utf-8") not in raw for item in forbidden), "TOKEN_REFLECTION")
            data = wire_body(
                raw,
                operation,
                status,
                code,
                target=frozen_target,
                request=frozen_payload if code is None else None,
                forbidden=forbidden,
            )
            decoded = loads(raw)
            _require(
                decoded["error" if code is not None else "meta"]["correlationId"] == correlation,
                "WIRE_INVALID",
            )
            if case_id is not None:
                self.cases[case_id] = {
                    "id": case_id,
                    "operation": operation,
                    "target": frozen_target,
                    "request": frozen_payload if code is None else None,
                    "status": status,
                    "content_type": "application/json",
                    "body_utf8": raw.decode("utf-8"),
                    "expected": {"outcome": "success"}
                    if code is None
                    else {"outcome": "error", "error_code": code},
                }
            self.responses_checked += 1
            return data
        except AcceptanceFailure:
            raise
        except Exception:
            raise AcceptanceFailure("WIRE_INVALID") from None

    def complete(self, token: str, *, other: bool = False) -> None:
        profile = (
            {**PROFILE_REQUEST, "display_name": "Synthetic learner B"} if other else PROFILE_REQUEST
        )
        self.native.request("draft", token, profile)
        self.native.request("consent", token, CONSENT_REQUEST)
        _require(
            self.native.request("complete", token, COMPLETE_REQUEST)["onboarding_completed"] is True
        )

    def restart(self, *, storage_fault: bool = False) -> None:
        original = self.native.current_server()
        original.stop()
        _require(original.reaped and self.database.is_file(), "CHILD_CLEANUP_FAILED")
        replacement = self.native.start()
        _require(
            original.process is not None
            and replacement.process is not None
            and original.process.pid != replacement.process.pid,
            "HANDSHAKE_INVALID",
        )
        if storage_fault:
            self.storage_fault_restarts += 1
        else:
            self.durable_restarts += 1

    def verify_schema(self) -> None:
        try:
            with closing(
                sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)
            ) as connection:
                versions = connection.execute("SELECT version FROM schema_metadata").fetchall()
                _require(
                    SCHEMA_VERSION >= 4
                    and len(versions) == 1
                    and type(versions[0][0]) is int
                    and versions[0][0] == SCHEMA_VERSION
                    and connection.execute("PRAGMA user_version").fetchone() == (0,)
                    and connection.execute("PRAGMA application_id").fetchone() == (0,),
                    "PROBE_FAILED",
                )
        except Exception:
            raise AcceptanceFailure("PROBE_FAILED") from None

    def owned_database(self) -> None:
        """A stopped private child and exact disposable capability precede faults."""
        base = _temporary_base()
        parent = self.database.parent
        _owned_workspace(parent, base, self.database)
        _require(
            self.database.name == "state.sqlite3"
            and self.database.is_file()
            and parent.name.startswith("finex-s1-acceptance-")
            and parent.resolve().parent == base
            and ROOT not in parent.resolve().parents
            and all(server.reaped for server in self.native.servers),
            "TEMPORARY_DIRECTORY_UNSAFE",
        )

    def database_fault(self, token: str, expected: dict[str, Any]) -> None:
        self.native.current_server().stop()
        self.owned_database()
        try:
            with closing(
                sqlite3.connect(self.database.as_uri() + "?mode=rw", uri=True)
            ) as connection:
                self.owned_database()
                _require(
                    connection.execute("PRAGMA application_id").fetchone() == (0,), "PROBE_FAILED"
                )
                connection.execute("PRAGMA application_id=195")
            self.native.start()
            self.storage_fault_restarts += 1
            self.request(
                "watchlists",
                token,
                status=503,
                code="LOCAL_STORE_UNAVAILABLE",
                case_id="storage_unavailable",
            )
        finally:
            self.native.current_server().stop()
            self.owned_database()
            with closing(
                sqlite3.connect(self.database.as_uri() + "?mode=rw", uri=True)
            ) as connection:
                self.owned_database()
                _require(
                    connection.execute("PRAGMA application_id").fetchone() == (195,), "PROBE_FAILED"
                )
                connection.execute("PRAGMA application_id=0")
        self.native.start()
        self.storage_fault_restarts += 1
        _require(
            self.request("account", token, case_id="restored_account") == expected, "PROBE_FAILED"
        )
        self.verify_schema()

    def wait_real_expiry(
        self,
        token: str,
        expires_at: datetime,
        *,
        started: float,
        before_login: datetime,
        after_login: datetime,
    ) -> None:
        _require(
            before_login + timedelta(seconds=60)
            <= expires_at
            <= after_login + timedelta(seconds=60),
            "TTL_FAILED",
        )
        valid_seen = False
        while time.monotonic() < started + 75:
            try:
                response = self.native.current_client().get(
                    "/api/v1/local-paper/account", headers={"Authorization": "Bearer " + token}
                )
                _require(
                    not response.history
                    and "set-cookie" not in response.headers
                    and response.headers.get("content-type", "").split(";")[0]
                    == "application/json",
                    "TTL_FAILED",
                )
                raw = response.content
                forbidden = (*self.native.tokens, *self.private_identities, str(self.database))
                if response.status_code == 401:
                    wire_body(
                        raw, "account", 401, "SESSION_INVALID", target=None, forbidden=forbidden
                    )
                    elapsed = time.monotonic() - started
                    _require(valid_seen and elapsed >= 59, "TTL_FAILED")
                    self.native.ttl_elapsed = round(elapsed, 3)
                    self.responses_checked += 1
                    self.cases["session_expired"] = {
                        "id": "session_expired",
                        "operation": "account",
                        "target": None,
                        "request": None,
                        "status": 401,
                        "content_type": "application/json",
                        "body_utf8": raw.decode("utf-8"),
                        "expected": {"outcome": "error", "error_code": "SESSION_INVALID"},
                    }
                    return
                _require(response.status_code == 200, "TTL_FAILED")
                wire_body(raw, "account", 200, None, target=None, forbidden=forbidden)
                self.responses_checked += 1
                valid_seen = True
            except Exception:
                raise AcceptanceFailure("TTL_FAILED") from None
            time.sleep(0.5)
        raise AcceptanceFailure("TTL_FAILED")

    def run(self) -> None:
        disabled = self.native.start("disabled")
        self.request(
            "search",
            None,
            target={"query": "", "limit": 20},
            status=403,
            code="LOCAL_APPLICATION_ONLY",
            case_id="local_application_only",
            raw_body=b"{malformed",
        )
        _require(not self.database.exists())
        # A mutation also proves that opt-in precedes malformed-body parsing.
        self.request(
            "watchlist_create",
            None,
            status=403,
            code="LOCAL_APPLICATION_ONLY",
            raw_body=b"{malformed",
        )
        disabled.stop()
        self.mark("disabled_body_boundary")
        self.native.start()
        self.request(
            "search",
            None,
            target={"query": "", "limit": 20},
            status=401,
            code="SESSION_INVALID",
            case_id="session_missing",
        )
        _require(not self.database.exists())
        self.mark("missing_credential_boundary")
        owner, owner_id, _ = self.native.login("learner-a")
        self.private_identities.add(owner_id)
        self.request(
            "watchlists",
            owner,
            status=409,
            code="ONBOARDING_REQUIRED",
            case_id="onboarding_required",
        )
        self.complete(owner)
        other, other_id, _ = self.native.login("learner-b")
        self.private_identities.add(other_id)
        self.complete(other, other=True)
        self.mark("current_completed_onboarding")
        self.request("search", owner, target={"query": "", "limit": 20}, case_id="search_default")
        self.request(
            "search", owner, target={"query": "apple", "limit": 2}, case_id="search_filtered"
        )
        self.request(
            "search", owner, target={"query": "no-match", "limit": 2}, case_id="search_empty"
        )
        self.mark("default_search_catalogue")
        quotes = {}
        for identifier, instrument in (
            ("quote_aapl", "SYN:AAPL"),
            ("quote_bond", "SYN:BND"),
            ("quote_msft", "SYN:MSFT"),
            ("quote_unavailable", "SYN:UNAVAILABLE"),
        ):
            quotes[identifier] = self.request(
                "quote", owner, target={"instrument_id": instrument}, case_id=identifier
            )
        _require(
            self.request(
                "quote", owner, target={"instrument_id": "SYN:AAPL"}, case_id="quote_cache_hit"
            )
            == quotes["quote_aapl"]
        )
        self.mark("default_quote_states_and_cache_hit")
        self.request(
            "quote",
            owner,
            target={"instrument_id": "SYN:TEST001"},
            status=404,
            code="INSTRUMENT_NOT_FOUND",
            case_id="instrument_not_found",
        )
        self.mark("unsupported_instrument")
        _require(self.request("watchlists", owner, case_id="watchlists_empty")["items"] == [])
        created = self.request(
            "watchlist_create",
            owner,
            payload={"name": "Synthetic review list"},
            status=201,
            case_id="watchlist_created",
        )
        selected = {"watchlist_id": created["watchlist_id"]}
        renamed = self.request(
            "watchlist_update",
            owner,
            target=selected,
            payload={"name": "Synthetic review list renamed"},
            case_id="watchlist_renamed",
        )
        _require(
            self.request(
                "watchlist_update",
                owner,
                target=selected,
                payload={"name": "Synthetic review list renamed"},
                case_id="watchlist_rename_noop",
            )
            == renamed
        )
        item_target = {**selected, "instrument_id": "SYN:AAPL"}
        added = self.request(
            "watchlist_item_put", owner, target=item_target, case_id="watchlist_item_added"
        )
        _require(
            self.request(
                "watchlist_item_put", owner, target=item_target, case_id="watchlist_item_duplicate"
            )
            == added
        )
        detail = self.request(
            "watchlist_detail", owner, target=selected, case_id="watchlist_detail"
        )
        self.request(
            "watchlist_create", owner, payload={"name": "Synthetic second list"}, status=201
        )
        _require(self.request("watchlists", owner, case_id="watchlist_collection")["count"] == 2)
        self.mark("watchlist_crud_and_stable_noops")
        _require(self.request("watchlists", other, case_id="other_owner_empty")["items"] == [])
        self.request(
            "watchlist_detail",
            other,
            target=selected,
            status=404,
            code="WATCHLIST_NOT_FOUND",
            case_id="watchlist_other_owner",
        )
        for operation, payload in (
            ("watchlist_update", {"name": "Synthetic denied"}),
            ("watchlist_delete", None),
            ("watchlist_item_put", None),
            ("watchlist_item_delete", None),
        ):
            self.request(
                operation,
                other,
                target=item_target if "item" in operation else selected,
                payload=payload,
                status=404,
                code="WATCHLIST_NOT_FOUND",
            )
        _require(self.request("watchlist_detail", owner, target=selected) == detail)
        self.mark("owner_scoped_non_disclosure")
        for index in range(8):
            self.request(
                "watchlist_create",
                owner,
                payload={"name": f"Synthetic quota control {index}"},
                status=201,
            )
        full = self.request("watchlists", owner)
        _require(full["count"] == 10)
        self.request(
            "watchlist_create",
            owner,
            payload={"name": "Synthetic quota rejected"},
            status=409,
            code="WATCHLIST_LIMIT",
            case_id="watchlist_limit",
        )
        _require(self.request("watchlists", owner) == full)
        self.request(
            "watchlist_create",
            owner,
            payload={"name": ""},
            status=422,
            code="VALIDATION_ERROR",
            case_id="invalid_watchlist_name",
        )
        _require(self.request("watchlists", owner) == full)
        removed = self.request(
            "watchlist_item_delete", owner, target=item_target, case_id="watchlist_item_removed"
        )
        removed_at = loads(self.cases["watchlist_item_removed"]["body_utf8"].encode("utf-8"))[
            "meta"
        ]["dataAsOf"]
        _require(
            self.request(
                "watchlist_item_delete",
                owner,
                target=item_target,
                case_id="watchlist_item_remove_noop",
            )
            == removed
            and loads(self.cases["watchlist_item_remove_noop"]["body_utf8"].encode("utf-8"))[
                "meta"
            ]["dataAsOf"]
            == removed_at
        )
        _require(self.request("watchlist_detail", owner, target=selected)["items"] == [])
        self.request("watchlist_item_put", owner, target={**selected, "instrument_id": "SYN:BND"})
        persisted_list = self.request("watchlist_detail", owner, target=selected)
        self.mark("watchlist_capacity_atomic")
        _require(self.request("account", owner, case_id="unopened_account")["account"] is None)
        self.request(
            "ledger",
            owner,
            target={"limit": 2, "after_sequence": 0},
            status=404,
            code="PAPER_ACCOUNT_NOT_OPEN",
            case_id="unopened_ledger",
        )
        _require(self.request("account", owner)["account"] is None)
        self.mark("unopened_read_no_funding")
        self.request(
            "account_open",
            owner,
            payload={"foundation_version": "market_foundation.v0", "currency": "USD"},
            status=409,
            code="MARKET_FOUNDATION_VERSION_MISMATCH",
            case_id="foundation_version_mismatch",
        )
        _require(self.request("account", owner)["account"] is None)
        opened = self.request(
            "account_open",
            owner,
            payload={"foundation_version": FOUNDATION_VERSION, "currency": "USD"},
            case_id="opened_account",
        )
        _require(
            self.request(
                "account_open",
                owner,
                payload={"foundation_version": FOUNDATION_VERSION, "currency": "USD"},
                case_id="repeated_account_open",
            )
            == opened
        )
        _require(self.request("account", other, case_id="other_owner_unopened")["account"] is None)
        self.mark("one_explicit_opening")
        ledger = self.request(
            "ledger", owner, target={"limit": 2, "after_sequence": 0}, case_id="opening_ledger"
        )
        _require(
            self.request(
                "ledger",
                owner,
                target={"limit": 2, "after_sequence": 1},
                case_id="ledger_after_opening",
            )["items"]
            == []
        )
        _require(
            len(ledger["items"]) == 1
            and ledger["items"][0]["ledger_id"] == opened["account"]["opening_ledger_id"]
        )
        self.mark("original_opening_ledger")
        # These reused public assertions prove preserved earlier-domain records,
        # not a second corpus or an unreviewed copy of their native scenarios.
        risk = SavedRiskProof(self.database)
        risk.native, risk.private_identities = self.native, self.private_identities
        saved_risk = risk.request(
            "POST", "/assessments", owner, {**risk_input(), "idempotency_key": str(uuid4())}
        )
        portfolio = PortfolioProof(self.database)
        portfolio.native, portfolio.private_identities = self.native, self.private_identities
        saved_portfolio = portfolio.create(owner, "Synthetic S3 preservation control")
        holding = portfolio.add(
            owner, saved_portfolio["portfolio_id"], "SYN:AAPL", "1.000000", "100.0000"
        )
        self.verify_schema()
        self.restart()
        owner, renewed_id, _ = self.native.login("learner-a")
        _require(renewed_id == owner_id)
        _require(self.request("account", owner, case_id="account_after_restart") == opened)
        _require(
            self.request(
                "watchlist_detail", owner, target=selected, case_id="watchlist_after_restart"
            )
            == persisted_list
        )
        _require(self.request("ledger", owner, target={"limit": 2, "after_sequence": 0}) == ledger)
        self.mark("first_real_process_restart")
        self.native.request("consent", owner, {**CONSENT_REQUEST, "consent_given": False})
        self.request(
            "watchlists",
            owner,
            status=409,
            code="ONBOARDING_REQUIRED",
            case_id="withdrawal_required",
        )
        self.native.request("consent", owner, CONSENT_REQUEST)
        self.request(
            "account", owner, status=409, code="ONBOARDING_REQUIRED", case_id="reaccepted_required"
        )
        _require(
            self.native.request("complete", owner, COMPLETE_REQUEST)["onboarding_completed"] is True
        )
        _require(self.request("account", owner, case_id="account_after_recompletion") == opened)
        _require(self.request("watchlist_detail", owner, target=selected) == persisted_list)
        self.mark("withdrawal_reacceptance_recompletion")
        self.request("watchlist_delete", owner, target=selected, case_id="watchlist_deleted")
        self.request(
            "watchlist_detail",
            owner,
            target=selected,
            status=404,
            code="WATCHLIST_NOT_FOUND",
            case_id="deleted_watchlist_not_found",
        )
        _require(
            self.request("account", owner, case_id="account_after_watchlist_delete") == opened
            and self.request("watchlists", owner)["count"] == 9
        )
        _require(self.request("ledger", owner, target={"limit": 2, "after_sequence": 0}) == ledger)
        assessment_id = saved_risk["assessment_id"]
        _require(risk.request("GET", "/assessments/" + assessment_id, owner) == saved_risk)
        _require(
            portfolio.request(
                "portfolio_detail", owner, portfolio_id=saved_portfolio["portfolio_id"]
            )
            == saved_portfolio
        )
        _require(
            portfolio.request(
                "holding_detail",
                owner,
                portfolio_id=saved_portfolio["portfolio_id"],
                holding_id=holding["holding_id"],
            )
            == holding
        )
        self.mark("watchlist_delete_preserves_other_domains")
        self.native.request("logout", owner)
        self.request(
            "watchlists", owner, status=401, code="SESSION_INVALID", case_id="session_revoked"
        )
        self.restart()
        self.request(
            "account",
            owner,
            status=401,
            code="SESSION_INVALID",
            case_id="session_after_restart_revoked",
        )
        _require(self.durable_restarts == 2)
        self.mark("durable_logout_and_second_restart")
        before_login, started = datetime.now(timezone.utc), time.monotonic()
        expiring, expiring_id, expires = self.native.login("learner-a")
        after_login = datetime.now(timezone.utc)
        _require(expiring_id == owner_id)
        self.wait_real_expiry(
            expiring, expires, started=started, before_login=before_login, after_login=after_login
        )
        owner, final_id, _ = self.native.login("learner-a")
        _require(final_id == owner_id)
        _require(
            self.request("account", owner, case_id="account_after_expiry_relogin") == opened
            and self.request("watchlists", owner)["count"] == 9
        )
        self.mark("real_session_expiry")
        self.database_fault(owner, opened)
        _require(self.storage_fault_restarts == 2)
        self.mark("safe_owned_database_fault")
        self.native.current_server().stop()
        self.owned_database()
        with closing(sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)) as connection:
            digests = connection.execute("SELECT digest FROM local_sessions").fetchall()
            _require(
                bool(digests)
                and all(
                    isinstance(row[0], str) and HASH.fullmatch(row[0]) is not None
                    for row in digests
                )
            )
        raw_database = self.database.read_bytes()
        _require(
            all(token.encode("ascii") not in raw_database for token in self.native.tokens),
            "TOKEN_REFLECTION",
        )
        self.verify_schema()
        self.mark("digest_only_storage_no_leak")
        _require(set(self.cases) == set(CASE_IDS))
        self.mark("complete_original_wire_corpus")


def evaluate_acceptance(
    *, tested_sha: str, tested_tree: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Run owned proof and make successful artifacts only after cleanup/rebinding."""
    provenance: dict[str, Any] = {
        "tested_commit": None,
        "tested_tree": None,
        "working_tree_dirty": None,
        "tracked_dirty": None,
        "source_hashes": [],
        "source_manifest_sha256": None,
    }
    proof: FoundationProof | None = None
    workspace: Path | None = None
    base: Path | None = None
    failure: str | None = None
    corpus: dict[str, Any] | None = None
    removed = False
    try:
        _require(
            all(
                isinstance(value, str) and SHA_PATTERN.fullmatch(value) is not None
                for value in (tested_sha, tested_tree)
            ),
            "PROVENANCE_INVALID",
        )
        provenance.update(repository_provenance(tested_sha, tested_tree))
        _require(
            provenance["tested_commit"] == tested_sha
            and provenance["tested_tree"] == tested_tree
            and provenance["working_tree_dirty"] is False
            and provenance["tracked_dirty"] is False,
            "PROVENANCE_MISMATCH",
        )
        provenance["source_hashes"] = runtime_hashes()
        provenance["source_manifest_sha256"] = manifest_sha256(provenance["source_hashes"])
        base = _temporary_base()
        workspace = Path(tempfile.mkdtemp(prefix="finex-s1-acceptance-", dir=base))
        _owned_workspace(workspace, base, workspace / "state.sqlite3")
        proof = FoundationProof(workspace / "state.sqlite3")
        proof.run()
        _require(
            proof.checks
            == [{"id": identifier, "passed": True} for identifier in REQUIRED_CHECKS[:-1]],
            "PROBE_FAILED",
        )
        _require(
            runtime_hashes() == provenance["source_hashes"]
            and _git(["rev-parse", "HEAD"]) == tested_sha
            and _git(["rev-parse", "HEAD^{tree}"]) == tested_tree
            and not _git(["status", "--porcelain", "--untracked-files=normal"]),
            "SOURCE_CHANGED",
        )
        pids = [server.process.pid for server in proof.native.servers if server.process is not None]
        elapsed = proof.native.ttl_elapsed
        _require(
            len(proof.native.servers) == len(pids) == len(set(pids)) == 6
            and all(type(pid) is int and 1 <= pid <= 2147483647 for pid in pids)
            and proof.durable_restarts == proof.storage_fault_restarts == 2
            and elapsed is not None
            and type(elapsed) in (int, float)
            and math.isfinite(elapsed)
            and 59 <= elapsed <= 75
            and type(proof.responses_checked) is int
            and len(CASE_IDS) <= proof.responses_checked <= 100000,
            "PROBE_FAILED",
        )
        _require(set(proof.cases) == set(CASE_IDS), "CORPUS_INVALID")
        corpus = {
            "schema_version": CORPUS_SCHEMA,
            **SCOPE_FIELDS,
            "provenance": {
                "kind": "native_tcp_capture",
                "source": "owned_loopback_uvicorn",
                "command": COMMAND,
                "tested_commit": tested_sha,
                "tested_tree": tested_tree,
            },
            "source_hashes": provenance["source_hashes"],
            "source_manifest_sha256": provenance["source_manifest_sha256"],
            "cases": [proof.cases[identifier] for identifier in CASE_IDS],
        }
        validate_corpus(
            corpus, forbidden=(*proof.native.tokens, *proof.private_identities, str(proof.database))
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
                except Exception:
                    failure = "CHILD_CLEANUP_FAILED"
        if workspace is not None:
            try:
                _require(
                    proof is not None and all(server.reaped for server in proof.native.servers),
                    "CHILD_CLEANUP_FAILED",
                )
                _require(base is not None, "TEMPORARY_DIRECTORY_UNSAFE")
                if base is None:
                    raise AcceptanceFailure("TEMPORARY_DIRECTORY_UNSAFE")
                _owned_workspace(workspace, base, workspace / "state.sqlite3")
                shutil.rmtree(workspace)
                removed = not workspace.exists()
                _require(removed, "TEMPORARY_CLEANUP_FAILED")
            except AcceptanceFailure as error:
                failure = error.code
            except Exception:
                failure = "TEMPORARY_CLEANUP_FAILED"
    if failure is None and proof is not None and removed and corpus is not None:
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
                proof.checks
                == [{"id": identifier, "passed": True} for identifier in REQUIRED_CHECKS],
                "PROBE_FAILED",
            )
        except AcceptanceFailure as error:
            failure = error.code
        except Exception:
            failure = "INTERNAL_FAILURE"
    success = failure is None and proof is not None and removed and corpus is not None
    if not success:
        corpus = None
    native = proof.native if proof is not None else None
    report = {
        "schema_version": REPORT_SCHEMA,
        **SCOPE_FIELDS,
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
            "starts": len(native.servers) if native is not None else 0,
            "application_restarts": proof.durable_restarts + proof.storage_fault_restarts
            if proof is not None
            else 0,
            "durable_restarts": proof.durable_restarts if proof is not None else 0,
            "storage_fault_restarts": proof.storage_fault_restarts if proof is not None else 0,
            "owned_pids": [
                server.process.pid for server in native.servers if server.process is not None
            ]
            if native is not None
            else [],
            "child_reaped": native is not None and all(server.reaped for server in native.servers),
            "temporary_directory_removed": removed,
            "session_ttl_minutes": 1,
            "real_expiry_elapsed_seconds": native.ttl_elapsed if native is not None else None,
            "shutdown": "owned_terminate_and_reap",
        },
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "limitations": [
            "Default four-instrument synthetic TCP proof, not full S3 or two-client acceptance.",
            "No native injected provider fault, STALE capture or expanded 100-item "
            "catalogue quota claim.",
            "Current schema restart preservation is not physical prior-version migration evidence.",
            "No real identity, live market, real money, cloud, native-device or human UAT claim.",
        ],
    }
    return report, corpus


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AcceptanceFailure("CLI_ARGUMENTS_INVALID")


def main(argv: list[str] | None = None) -> int:
    parser = SafeParser(description=__doc__, add_help=False, allow_abbrev=False)
    parser.add_argument("--tested-sha", required=True)
    parser.add_argument("--tested-tree", required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--corpus", type=Path)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    try:
        options = parser.parse_args(argv)
        report_path = output_target(options.report, ROOT)
        corpus_path = output_target(options.corpus, ROOT)
        _require(
            report_path is None or corpus_path is None or report_path != corpus_path,
            "OUTPUT_INVALID",
        )
        report, corpus = evaluate_acceptance(
            tested_sha=options.tested_sha, tested_tree=options.tested_tree
        )
        if report["success"] is True and corpus is not None and corpus_path is not None:
            write_new_json(corpus_path, corpus)
            _require(
                hashlib.sha256(corpus_path.read_bytes()).hexdigest() == report["corpus_sha256"],
                "OUTPUT_WRITE_FAILED",
            )
        if report_path is not None:
            write_new_json(report_path, report)
        if options.format == "json":
            print(json_bytes(report).decode("utf-8"), end="")
        else:
            print("S3 foundation: " + ("PASS" if report["success"] is True else "FAIL"))
        return 0 if report["success"] is True else 1
    except AcceptanceFailure as error:
        print("S3 foundation: " + error.code)
        return 1
    except Exception:
        print("S3 foundation: INTERNAL_FAILURE")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
