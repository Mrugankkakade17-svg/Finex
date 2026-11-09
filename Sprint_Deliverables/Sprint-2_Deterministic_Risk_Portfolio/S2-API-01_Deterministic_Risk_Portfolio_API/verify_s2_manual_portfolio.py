"""Owned native manual-portfolio proof; not full two-client S2 acceptance.

Only a fresh, disposable, loopback child is accepted. Credentials remain in
memory. Current shared-schema preservation includes the accepted S2 schema-3
baseline; SQL migration tests separately prove the frozen earlier generations.
The optional corpus contains only bounded, allowlisted, actual response bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import (
    ROUND_HALF_UP,
    Context,
    Decimal,
    DivisionByZero,
    InvalidOperation,
    Overflow,
    localcontext,
)
from pathlib import Path
from typing import Any, NoReturn
from uuid import uuid4

import httpx

from app.ports.adapters.sqlite_local_schema import SCHEMA_VERSION
from local_s2_evidence import (
    json_bytes,
    output_target,
    reflects_private,
    write_new_json,
)
from local_s2_evidence import (
    manifest_sha256 as manifest_sha256,
)
from local_s2_evidence import (
    runtime_hashes as s2_runtime_hashes,
)
from verify_s1_application import (
    COMPLETE_REQUEST,
    CONSENT_REQUEST,
    CONTRACT_VERSION,
    PROFILE_REQUEST,
    ROOT,
    SCOPE,
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
from verify_s2_saved_risk import SavedRiskProof, risk_input

COMMAND = "python verify_s2_manual_portfolio.py"
CORPUS_SCHEMA = "finex.local_s2.portfolio_corpus.v1"
REPORT_SCHEMA = "finex.local_s2.manual_portfolio.acceptance.v1"
MAX_BODY = 262144
MAX_CORPUS = 2 * 1024 * 1024
LIMITATIONS = (
    "SYNTHETIC_QUOTES_NOT_MARKET_DATA",
    "MANUAL_HOLDINGS_NOT_BROKER_POSITIONS",
    "SPREAD_IS_ALLOCATION_ONLY",
    "NO_FUND_LOOKTHROUGH_OR_SUITABILITY",
)
REQUIRED_CHECKS = (
    "disabled_prebody_no_database",
    "remote_configuration_no_database",
    "missing_bearer_no_database",
    "current_s1_prerequisites",
    # Stable S2 proof identifier names its baseline, not the current generation.
    "schema3_preserves_s1_and_risk",
    "versioned_synthetic_catalog",
    "owned_portfolio_crud_noop",
    "owned_holding_crud_noop",
    "canonical_input_rejections_unchanged",
    "cross_owner_and_parent_isolation",
    "duplicate_and_portfolio_capacity",
    "six_decimal_golden_cases",
    "zero_cost_and_rounded_zero",
    "honest_empty_partial_unavailable",
    "first_native_restart",
    "persisted_portfolios_holdings_and_risk",
    "withdrawal_reacceptance_gates",
    "no_implicit_record_erasure",
    "durable_per_session_logout",
    "second_native_restart",
    "real_one_minute_expiry",
    "records_preserved_after_expiry",
    "digest_only_storage_no_reflection",
    "safe_wire_and_diagnostics",
    "complete_safe_wire_corpus",
    "owned_cleanup",
)
SUCCESS_CASES = {
    "catalogue": "catalogue",
    "portfolio_created": "portfolio_create",
    "portfolio_list": "portfolio_list",
    "portfolio_detail": "portfolio_detail",
    "portfolio_updated": "portfolio_update",
    "portfolio_unchanged": "portfolio_update",
    "portfolio_deleted": "portfolio_delete",
    "holding_created": "holding_create",
    "holding_list": "holding_list",
    "holding_detail": "holding_detail",
    "holding_updated": "holding_update",
    "holding_unchanged": "holding_update",
    "holding_deleted": "holding_delete",
    **{f"golden_{number}": "metrics" for number in range(1, 7)},
    "empty": "metrics",
    "zero_cost": "metrics",
    "partial": "metrics",
    "unavailable": "metrics",
}
ERROR_CASES = {
    "session_invalid": ("portfolio_list", 401, "SESSION_INVALID"),
    "onboarding_required": ("portfolio_list", 409, "ONBOARDING_REQUIRED"),
    "portfolio_not_found": ("portfolio_detail", 404, "LOCAL_PORTFOLIO_NOT_FOUND"),
    "holding_not_found": ("holding_detail", 404, "LOCAL_HOLDING_NOT_FOUND"),
    "validation_error": ("holding_create", 422, "VALIDATION_ERROR"),
    "unsupported_instrument": ("holding_create", 422, "UNSUPPORTED_INSTRUMENT"),
    "holding_duplicate": ("holding_create", 409, "HOLDING_ALREADY_EXISTS"),
    "portfolio_limit": ("portfolio_create", 409, "PORTFOLIO_LIMIT_REACHED"),
}
CASE_IDS = (*SUCCESS_CASES, *ERROR_CASES)
BASE = "/api/v1/local-portfolios"
AS_OF = "2026-01-01T00:00:00Z"
UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
INSTRUMENT_PATTERN = re.compile(r"SYN:[A-Z][A-Z0-9_]{0,31}\Z", re.ASCII)
SCOPE_FIELDS = {"scope", "contract_version"}
CATALOG_ITEM_FIELDS = {"instrument_id", "display_name", "asset_class", "sector", "currency"}
PORTFOLIO_FIELDS = SCOPE_FIELDS | {
    "portfolio_version",
    "portfolio_id",
    "name",
    "description",
    "currency",
    "created_at",
    "updated_at",
}
HOLDING_FIELDS = (
    SCOPE_FIELDS
    | CATALOG_ITEM_FIELDS
    | {
        "holding_version",
        "catalog_version",
        "portfolio_id",
        "holding_id",
        "quantity",
        "average_cost",
        "created_at",
        "updated_at",
    }
)
METRIC_FIELDS = SCOPE_FIELDS | {
    "metrics_version",
    "formula_version",
    "catalog_version",
    "quote_snapshot_version",
    "portfolio_id",
    "currency",
    "valuation_status",
    "source",
    "source_type",
    "fixture_as_of",
    "calculated_at",
    "missing_instrument_ids",
    "limitations",
    "holdings",
    "totals",
}
TOTAL_FIELDS = {
    "cost_basis",
    "market_value",
    "gain_loss",
    "gain_loss_percent",
    "allocation_by_asset_class",
    "allocation_by_sector",
    "concentration_percent",
    "hhi",
    "educational_spread_percent",
}
METRIC_HOLDING_FIELDS = CATALOG_ITEM_FIELDS | {
    "holding_version",
    "portfolio_id",
    "holding_id",
    "quantity",
    "average_cost",
    "cost_basis",
    "quote",
    "market_value",
    "gain_loss",
    "gain_loss_percent",
    "weight_percent",
}
PRIVATE_KEYS = {
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
DEFAULT_INSTRUMENTS = {
    "SYN:AAPL": ("Synthetic Apple example", "EQUITY", "TECHNOLOGY", "200.0000"),
    "SYN:BND": ("Synthetic bond-fund example", "BOND", "FIXED_INCOME", "80.0000"),
    "SYN:MSFT": ("Synthetic Microsoft example", "EQUITY", "TECHNOLOGY", "400.0000"),
    "SYN:UNAVAILABLE": ("Synthetic unavailable-price example", "EQUITY", "GENERAL", None),
}
GOLDEN_INPUTS = (
    [("SYN:AAPL", "10.000000", "150.0000"), ("SYN:BND", "25.000000", "80.0000")],
    [("SYN:MSFT", "5.000000", "500.0000")],
    [
        ("SYN:AAPL", "1.000000", "200.0000"),
        ("SYN:MSFT", "0.500000", "400.0000"),
        ("SYN:BND", "2.500000", "80.0000"),
    ],
    [("SYN:AAPL", "0.005025", "100.0000"), ("SYN:BND", "0.012563", "40.0000")],
    [("SYN:AAPL", "0.000001", "1000000.0000")],
    [("SYN:MSFT", "1000000.000000", "1000000.0000")],
)
GOLDEN_TOTALS = (
    ("3500.00", "4000.00", "500.00", "14.29", "50.00", "0.500000", "50.00"),
    ("2500.00", "2000.00", "-500.00", "-20.00", "100.00", "1.000000", "0.00"),
    ("600.00", "600.00", "0.00", "0.00", "33.33", "0.333333", "66.67"),
    ("1.00", "2.02", "1.02", "102.00", "50.00", "0.500000", "50.00"),
    ("1.00", "0.00", "-1.00", "-100.00", None, None, None),
    (
        "1000000000000.00",
        "400000000.00",
        "-999600000000.00",
        "-99.96",
        "100.00",
        "1.000000",
        "0.00",
    ),
)
GOLDEN_FIELDS = (
    "cost_basis",
    "market_value",
    "gain_loss",
    "gain_loss_percent",
    "concentration_percent",
    "hhi",
    "educational_spread_percent",
)


def _safe_object(value: object, fields: set[str] | None = None) -> dict[str, Any]:
    _require(isinstance(value, dict), "WIRE_INVALID")
    if not isinstance(value, dict):  # Explicit narrowing, not a permissive conversion.
        raise AcceptanceFailure("WIRE_INVALID")
    _require(fields is None or set(value) == fields, "WIRE_INVALID")
    return value


def _private(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            not isinstance(key, str) or key.lower() in PRIVATE_KEYS or _private(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_private(child) for child in value)
    return isinstance(value, str) and ("Bearer " in value or "github_pat_" in value)


def _loads(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate field")
            result[key] = value
        return result

    def nonfinite(_: str) -> NoReturn:
        raise ValueError("Nonfinite JSON")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=nonfinite)
        return _safe_object(value)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise AcceptanceFailure("WIRE_INVALID") from None


def _uuid(value: object) -> None:
    _require(isinstance(value, str) and bool(UUID_PATTERN.fullmatch(value)), "WIRE_INVALID")


def _number(value: object, places: int, *, nullable: bool = False, signed: bool = False) -> None:
    if nullable and value is None:
        return
    pattern = (r"-?" if signed else "") + r"(?:0|[1-9][0-9]*)\." + rf"[0-9]{{{places}}}\Z"
    _require(
        isinstance(value, str) and bool(re.fullmatch(pattern, value, re.ASCII)), "WIRE_INVALID"
    )
    _require(
        not (isinstance(value, str) and value.startswith("-") and Decimal(value) == 0),
        "WIRE_INVALID",
    )


def _scope(data: dict[str, Any]) -> None:
    _require(
        data.get("scope") == SCOPE and data.get("contract_version") == CONTRACT_VERSION,
        "WIRE_INVALID",
    )


def _catalog_item(value: object) -> dict[str, Any]:
    item = _safe_object(value, CATALOG_ITEM_FIELDS)
    _require(
        isinstance(item["instrument_id"], str)
        and bool(INSTRUMENT_PATTERN.fullmatch(item["instrument_id"])),
        "WIRE_INVALID",
    )
    _require(
        all(
            isinstance(item[field], str) and 1 <= len(item[field]) <= 100
            for field in ("display_name", "asset_class", "sector")
        )
        and item["currency"] == "USD",
        "WIRE_INVALID",
    )
    return item


def _record(data: dict[str, Any], *, holding: bool) -> None:
    _safe_object(data, HOLDING_FIELDS if holding else PORTFOLIO_FIELDS)
    _scope(data)
    _uuid(data["portfolio_id"])
    _require(
        data["currency"] == "USD" and _utc(data["created_at"]) <= _utc(data["updated_at"]),
        "WIRE_INVALID",
    )
    if holding:
        _uuid(data["holding_id"])
        _require(
            data["holding_version"] == "holding.v1"
            and data["catalog_version"] == "synthetic_catalog.v1",
            "WIRE_INVALID",
        )
        _catalog_item({key: data[key] for key in CATALOG_ITEM_FIELDS})
        _number(data["quantity"], 6)
        _number(data["average_cost"], 4)
        _require(
            Decimal("0.000001") <= Decimal(data["quantity"]) <= Decimal("1000000")
            and Decimal(data["average_cost"]) <= Decimal("1000000"),
            "WIRE_INVALID",
        )
    else:
        _require(
            data["portfolio_version"] == "portfolio.v1"
            and isinstance(data["name"], str)
            and data["name"] == data["name"].strip()
            and 1 <= len(data["name"]) <= 100,
            "WIRE_INVALID",
        )
        description = data["description"]
        _require(
            description is None
            or (
                isinstance(description, str)
                and len(description) <= 500
                and description == description.strip()
            ),
            "WIRE_INVALID",
        )


def _metrics(data: dict[str, Any]) -> None:
    _safe_object(data, METRIC_FIELDS)
    _scope(data)
    _uuid(data["portfolio_id"])
    _require(
        data["metrics_version"] == "portfolio_metrics.v1"
        and data["formula_version"] == "manual_portfolio_math.v1"
        and data["catalog_version"] == "synthetic_catalog.v1"
        and data["quote_snapshot_version"] == "synthetic_quotes.v1"
        and data["currency"] == "USD"
        and data["source"] == "finex.synthetic.portfolio"
        and data["source_type"] == "SYNTHETIC"
        and data["fixture_as_of"] == AS_OF
        and data["limitations"] == list(LIMITATIONS),
        "WIRE_INVALID",
    )
    _utc(data["calculated_at"])
    status = data["valuation_status"]
    _require(status in ("EMPTY", "COMPLETE", "INCOMPLETE", "UNAVAILABLE"), "WIRE_INVALID")
    rows, missing = data["holdings"], data["missing_instrument_ids"]
    _require(
        isinstance(rows, list)
        and len(rows) <= 100
        and isinstance(missing, list)
        and all(
            isinstance(value, str) and bool(INSTRUMENT_PATTERN.fullmatch(value))
            for value in missing
        )
        and missing == sorted(set(missing)),
        "WIRE_INVALID",
    )
    row_ids: list[str] = []
    unavailable: list[str] = []
    for value in rows:
        row = _safe_object(value, METRIC_HOLDING_FIELDS)
        _catalog_item({key: row[key] for key in CATALOG_ITEM_FIELDS})
        _require(
            row["holding_version"] == "holding.v1" and row["portfolio_id"] == data["portfolio_id"],
            "WIRE_INVALID",
        )
        _uuid(row["holding_id"])
        row_ids.append(row["instrument_id"])
        _number(row["quantity"], 6)
        _number(row["average_cost"], 4)
        _number(row["cost_basis"], 2)
        for field in ("market_value", "gain_loss", "gain_loss_percent", "weight_percent"):
            _number(row[field], 2, nullable=True, signed=field.startswith("gain"))
        quote = _safe_object(row["quote"], {"unit_price", "data_status", "quote_as_of", "reason"})
        if quote["data_status"] == "CACHED":
            _number(quote["unit_price"], 4)
            _require(
                0 < Decimal(quote["unit_price"]) <= Decimal("1000000")
                and quote["quote_as_of"] == AS_OF
                and quote["reason"] is None
                and row["market_value"] is not None
                and row["gain_loss"] is not None,
                "WIRE_INVALID",
            )
        else:
            _require(
                quote
                == {
                    "unit_price": None,
                    "data_status": "UNAVAILABLE",
                    "quote_as_of": None,
                    "reason": "SYNTHETIC_QUOTE_UNAVAILABLE",
                }
                and all(
                    row[field] is None
                    for field in ("market_value", "gain_loss", "gain_loss_percent")
                ),
                "WIRE_INVALID",
            )
            unavailable.append(row["instrument_id"])
        if status in ("INCOMPLETE", "UNAVAILABLE"):
            _require(row["weight_percent"] is None, "WIRE_INVALID")
    _require(len(row_ids) == len(set(row_ids)) and missing == sorted(unavailable), "WIRE_INVALID")
    totals = _safe_object(data["totals"], TOTAL_FIELDS)
    _number(totals["cost_basis"], 2)
    for field in (
        "market_value",
        "gain_loss",
        "gain_loss_percent",
        "concentration_percent",
        "educational_spread_percent",
        "hhi",
    ):
        _number(
            totals[field],
            6 if field == "hhi" else 2,
            nullable=True,
            signed=field.startswith("gain"),
        )
    for field in ("allocation_by_asset_class", "allocation_by_sector"):
        allocation = totals[field]
        _require(allocation is None or isinstance(allocation, list), "WIRE_INVALID")
        groups: list[str] = []
        for value in allocation or []:
            group = _safe_object(value, {"group", "market_value", "weight_percent"})
            _require(
                isinstance(group["group"], str) and 1 <= len(group["group"]) <= 100, "WIRE_INVALID"
            )
            groups.append(group["group"])
            _number(group["market_value"], 2)
            _number(group["weight_percent"], 2, nullable=True)
        _require(groups == sorted(set(groups)), "WIRE_INVALID")
    if status == "EMPTY":
        _require(
            not rows
            and not missing
            and totals
            == {
                "cost_basis": "0.00",
                "market_value": "0.00",
                "gain_loss": "0.00",
                "gain_loss_percent": None,
                "allocation_by_asset_class": [],
                "allocation_by_sector": [],
                "concentration_percent": None,
                "hhi": None,
                "educational_spread_percent": None,
            },
            "WIRE_INVALID",
        )
    elif status == "COMPLETE":
        _require(
            bool(rows)
            and not missing
            and totals["market_value"] is not None
            and totals["gain_loss"] is not None
            and isinstance(totals["allocation_by_asset_class"], list)
            and isinstance(totals["allocation_by_sector"], list),
            "WIRE_INVALID",
        )
    else:
        _require(
            bool(missing)
            and bool(rows)
            and all(totals[field] is None for field in TOTAL_FIELDS - {"cost_basis"}),
            "WIRE_INVALID",
        )
        _require((status == "UNAVAILABLE") == (len(missing) == len(rows)), "WIRE_INVALID")


def _wire_body(
    raw: bytes,
    operation: str,
    status: int,
    code: str | None,
    *,
    forbidden: tuple[str, ...] = (),
) -> dict[str, Any]:
    _require(len(raw) <= MAX_BODY, "WIRE_INVALID")
    body = _loads(raw)
    _require(
        not _private(body) and not _forbidden_keys(body) and not reflects_private(body, forbidden),
        "WIRE_INVALID",
    )
    if code is not None:
        _safe_object(body, {"success", "message", "detail", "error_code", "error"})
        error = _safe_object(body["error"], {"code", "message", "fieldErrors", "correlationId"})
        _require(
            body["success"] is False
            and isinstance(body["message"], str)
            and isinstance(body["detail"], str)
            and isinstance(error["message"], str)
            and body["detail"] == body["message"] == error["message"]
            and body["error_code"] == error["code"] == code
            and 400 <= status < 600
            and isinstance(error["fieldErrors"], list)
            and len(error["fieldErrors"]) <= 50,
            "WIRE_INVALID",
        )
        _require(
            isinstance(error["correlationId"], str)
            and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", error["correlationId"])),
            "WIRE_INVALID",
        )
        for value in error["fieldErrors"]:
            field = _safe_object(value, {"field", "code"})
            _require(
                all(isinstance(item, str) and len(item) <= 200 for item in field.values()),
                "WIRE_INVALID",
            )
        return body
    _safe_object(body, {"success", "message", "data", "meta"})
    _require(
        body["success"] is True
        and isinstance(body["message"], str)
        and status == (201 if operation.endswith("_create") else 200),
        "WIRE_INVALID",
    )
    data = _safe_object(body["data"])
    _scope(data)
    expected_status, expected_asof = "CACHED", None
    if operation in ("portfolio_create", "portfolio_detail", "portfolio_update"):
        _record(data, holding=False)
        expected_asof = data["updated_at"]
    elif operation in ("holding_create", "holding_detail", "holding_update"):
        _record(data, holding=True)
        expected_asof = data["updated_at"]
    elif operation in ("catalogue", "portfolio_list", "holding_list"):
        fields = SCOPE_FIELDS | {"items", "count"}
        fields |= (
            {"catalog_version", "currency"} if operation == "catalogue" else {"portfolio_version"}
        )
        if operation == "holding_list":
            fields -= {"portfolio_version"}
            fields |= {"holding_version", "catalog_version", "portfolio_id"}
            _uuid(data["portfolio_id"])
        _safe_object(data, fields)
        items = data["items"]
        limit = 128 if operation == "catalogue" else (20 if operation == "portfolio_list" else 100)
        _require(
            isinstance(items, list)
            and type(data["count"]) is int
            and data["count"] == len(items) <= limit,
            "WIRE_INVALID",
        )
        for item in items:
            if operation == "catalogue":
                _catalog_item(item)
            else:
                _record(_safe_object(item), holding=operation == "holding_list")
                if operation == "holding_list":
                    _require(item["portfolio_id"] == data["portfolio_id"], "WIRE_INVALID")
        if operation == "catalogue":
            _require(
                data["catalog_version"] == "synthetic_catalog.v1" and data["currency"] == "USD",
                "WIRE_INVALID",
            )
        elif operation == "portfolio_list":
            _require(data["portfolio_version"] == "portfolio.v1", "WIRE_INVALID")
        else:
            _require(
                data["holding_version"] == "holding.v1"
                and data["catalog_version"] == "synthetic_catalog.v1",
                "WIRE_INVALID",
            )
        if operation != "catalogue":
            record_id = "holding_id" if operation == "holding_list" else "portfolio_id"
            order_keys = [(_utc(item["created_at"]), item[record_id]) for item in items]
            _require(
                order_keys == sorted(order_keys)
                and len({item[record_id] for item in items}) == len(items),
                "WIRE_INVALID",
            )
            if operation == "holding_list":
                _require(
                    len({item["instrument_id"] for item in items}) == len(items), "WIRE_INVALID"
                )
    elif operation.endswith("_delete"):
        holding = operation == "holding_delete"
        fields = SCOPE_FIELDS | {"portfolio_id", "entity_type", "deleted"}
        fields |= {"holding_version", "holding_id"} if holding else {"portfolio_version"}
        _safe_object(data, fields)
        _uuid(data["portfolio_id"])
        if holding:
            _uuid(data["holding_id"])
        _require(
            data["deleted"] is True
            and data["entity_type"] == ("holding" if holding else "portfolio")
            and data["holding_version" if holding else "portfolio_version"]
            == ("holding.v1" if holding else "portfolio.v1"),
            "WIRE_INVALID",
        )
    elif operation == "metrics":
        _metrics(data)
        if data["valuation_status"] == "COMPLETE":
            expected_asof = AS_OF
        elif data["valuation_status"] in ("INCOMPLETE", "UNAVAILABLE"):
            expected_status = "UNAVAILABLE"
    else:
        raise AcceptanceFailure("WIRE_INVALID")
    meta = _safe_object(body["meta"], {"correlationId", "apiVersion", "dataStatus", "dataAsOf"})
    _require(
        meta["apiVersion"] == "v1"
        and meta["dataStatus"] == expected_status
        and meta["dataAsOf"] == expected_asof
        and isinstance(meta["correlationId"], str)
        and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", meta["correlationId"])),
        "WIRE_INVALID",
    )
    return data


def runtime_hashes() -> list[dict[str, str]]:
    return s2_runtime_hashes(ROOT, source_hashes())


def validate_corpus(corpus: object, *, forbidden: tuple[str, ...] = ()) -> None:
    try:
        value = _safe_object(
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
        _require(value["schema_version"] == CORPUS_SCHEMA, "CORPUS_INVALID")
        _scope(value)
        provenance = _safe_object(
            value["provenance"], {"kind", "source", "command", "tested_commit", "tested_tree"}
        )
        _require(
            provenance["kind"] == "native_tcp_capture"
            and provenance["source"] == "owned_loopback_uvicorn"
            and provenance["command"] == COMMAND
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
        cases = value["cases"]
        _require(isinstance(cases, list) and len(cases) == len(CASE_IDS), "CORPUS_INVALID")
        seen: set[str] = set()
        for item in cases:
            case = _safe_object(
                item,
                {"id", "operation", "request", "status", "content_type", "body_utf8", "expected"},
            )
            identifier = case["id"]
            _require(
                isinstance(identifier, str) and identifier in CASE_IDS and identifier not in seen,
                "CORPUS_INVALID",
            )
            seen.add(identifier)
            raw = case["body_utf8"].encode("utf-8")
            _require(
                len(raw) <= MAX_BODY
                and all(private.encode("utf-8") not in raw for private in forbidden)
                and not reflects_private(case["request"], forbidden)
                and type(case["status"]) is int
                and case["content_type"] == "application/json",
                "CORPUS_INVALID",
            )
            code: str | None = None
            if identifier in ERROR_CASES:
                operation, status, code = ERROR_CASES[identifier]
                _require(
                    case["operation"] == operation
                    and case["status"] == status
                    and case["request"] is None
                    and case["expected"] == {"outcome": "error", "error_code": code},
                    "CORPUS_INVALID",
                )
            else:
                operation = SUCCESS_CASES[identifier]
                _require(
                    case["operation"] == operation
                    and case["status"] == (201 if operation.endswith("_create") else 200)
                    and case["expected"] == {"outcome": "success"},
                    "CORPUS_INVALID",
                )
                _validate_request(operation, case["request"])
            data = _wire_body(raw, operation, case["status"], code, forbidden=forbidden)
            if code is None:
                _case_semantics(identifier, data, case["request"])
        _require(seen == set(CASE_IDS), "CORPUS_INVALID")
        serialized = _json_bytes(value)
        _require(
            len(serialized) <= MAX_CORPUS
            and all(private.encode("utf-8") not in serialized for private in forbidden),
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


def _json_bytes(value: object) -> bytes:
    return json_bytes(value)


def _validate_request(operation: str, payload: object) -> None:
    if operation not in (
        "portfolio_create",
        "portfolio_update",
        "holding_create",
        "holding_update",
    ):
        _require(payload is None, "CORPUS_INVALID")
        return
    portfolio = operation.startswith("portfolio_")
    fields = (
        {"portfolio_version", "name", "description", "currency"}
        if portfolio
        else {
            "holding_version",
            "quantity",
            "average_cost",
            "currency",
        }
    )
    if operation == "holding_create":
        fields.add("instrument_id")
    data = _safe_object(payload, fields)
    _require(not _private(data) and data["currency"] == "USD", "CORPUS_INVALID")
    if portfolio:
        _require(
            data["portfolio_version"] == "portfolio.v1"
            and isinstance(data["name"], str)
            and 1 <= len(data["name"].strip()) <= 100
            and (
                data["description"] is None
                or (
                    isinstance(data["description"], str) and len(data["description"].strip()) <= 500
                )
            ),
            "CORPUS_INVALID",
        )
    else:
        _require(data["holding_version"] == "holding.v1", "CORPUS_INVALID")
        _number(data["quantity"], 6)
        _number(data["average_cost"], 4)
        _require(
            Decimal("0.000001") <= Decimal(data["quantity"]) <= Decimal("1000000")
            and Decimal(data["average_cost"]) <= Decimal("1000000"),
            "CORPUS_INVALID",
        )
        if operation == "holding_create":
            _require(
                isinstance(data["instrument_id"], str)
                and bool(INSTRUMENT_PATTERN.fullmatch(data["instrument_id"])),
                "CORPUS_INVALID",
            )


def decimal_expected(
    holdings: list[tuple[str, str, str]],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Independent contract oracle, never calling production portfolio math."""

    def display(value: Decimal, places: int = 2) -> str:
        rounded = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        return format(abs(rounded) if rounded == 0 else rounded, f".{places}f")

    independent_context = Context(
        prec=50,
        rounding=ROUND_HALF_UP,
        Emin=-999999,
        Emax=999999,
        capitals=1,
        clamp=0,
        flags=[],
        traps=[InvalidOperation, DivisionByZero, Overflow],
    )
    with localcontext(independent_context):
        rows: dict[str, dict[str, Any]] = {}
        for instrument, quantity, cost in holdings:
            _require(instrument in DEFAULT_INSTRUMENTS and instrument not in rows)
            price = DEFAULT_INSTRUMENTS[instrument][3]
            basis = Decimal(display(Decimal(quantity) * Decimal(cost)))
            value = (
                Decimal(display(Decimal(quantity) * Decimal(price))) if price is not None else None
            )
            gain = value - basis if value is not None else None
            rows[instrument] = {
                "cost_basis": display(basis),
                "market_value": display(value) if value is not None else None,
                "gain_loss": display(gain) if gain is not None else None,
                "gain_loss_percent": display(gain / basis * 100)
                if gain is not None and basis
                else None,
                "weight_percent": None,
            }
        basis = sum((Decimal(row["cost_basis"]) for row in rows.values()), Decimal(0))
        totals: dict[str, Any] = {field: None for field in TOTAL_FIELDS}
        totals["cost_basis"] = display(basis)
        if any(row["market_value"] is None for row in rows.values()):
            return rows, totals
        total = sum((Decimal(row["market_value"]) for row in rows.values()), Decimal(0))
        ratios = [Decimal(row["market_value"]) / total for row in rows.values()] if total else []
        hhi = sum((ratio * ratio for ratio in ratios), Decimal(0)) if ratios else None
        totals.update(
            market_value=display(total),
            gain_loss=display(total - basis),
            gain_loss_percent=display((total - basis) / basis * 100) if basis else None,
            concentration_percent=display(max(ratios) * 100) if ratios else None,
            hhi=display(hhi, 6) if hhi is not None else None,
            educational_spread_percent=display((1 - hhi) * 100) if hhi is not None else None,
        )
        for row in rows.values():
            row["weight_percent"] = (
                display(Decimal(row["market_value"]) / total * 100) if total else None
            )
        for field, index in (("allocation_by_asset_class", 1), ("allocation_by_sector", 2)):
            groups: dict[str, Decimal] = {}
            for instrument, row in rows.items():
                group = DEFAULT_INSTRUMENTS[instrument][index]
                _require(isinstance(group, str))
                if not isinstance(group, str):
                    raise AcceptanceFailure("PROBE_FAILED")
                groups[group] = groups.get(group, Decimal(0)) + Decimal(row["market_value"])
            totals[field] = [
                {
                    "group": group,
                    "market_value": display(value),
                    "weight_percent": display(value / total * 100) if total else None,
                }
                for group, value in sorted(groups.items())
            ]
        return rows, totals


def _assert_valuation(data: dict[str, Any]) -> None:
    inputs = [
        (row["instrument_id"], row["quantity"], row["average_cost"]) for row in data["holdings"]
    ]
    expected_rows, totals = decimal_expected(inputs)
    _require(data["totals"] == totals)
    unpriced = sorted(
        instrument for instrument, _, _ in inputs if DEFAULT_INSTRUMENTS[instrument][3] is None
    )
    status = (
        "EMPTY"
        if not inputs
        else (
            "UNAVAILABLE"
            if len(unpriced) == len(inputs)
            else ("INCOMPLETE" if unpriced else "COMPLETE")
        )
    )
    _require(data["valuation_status"] == status and data["missing_instrument_ids"] == unpriced)
    for row in data["holdings"]:
        instrument = row["instrument_id"]
        label, asset, sector, price = DEFAULT_INSTRUMENTS[instrument]
        _require(
            row["display_name"] == label and row["asset_class"] == asset and row["sector"] == sector
        )
        _require(all(row[field] == value for field, value in expected_rows[instrument].items()))
        _require(
            row["quote"]
            == {
                "unit_price": price,
                "data_status": "CACHED" if price else "UNAVAILABLE",
                "quote_as_of": AS_OF if price else None,
                "reason": None if price else "SYNTHETIC_QUOTE_UNAVAILABLE",
            }
        )


def _case_semantics(identifier: str, data: dict[str, Any], payload: object) -> None:
    """Case labels are evidence claims; an empty response cannot stand in for a golden."""
    if identifier == "catalogue":
        expected = [
            {
                "instrument_id": key,
                "display_name": value[0],
                "asset_class": value[1],
                "sector": value[2],
                "currency": "USD",
            }
            for key, value in sorted(DEFAULT_INSTRUMENTS.items())
        ]
        _require(data["items"] == expected and data["count"] == 4)
    if identifier.startswith("golden_") or identifier in (
        "empty",
        "zero_cost",
        "partial",
        "unavailable",
    ):
        _assert_valuation(data)
        inputs = sorted(
            (row["instrument_id"], row["quantity"], row["average_cost"]) for row in data["holdings"]
        )
        if identifier.startswith("golden_"):
            index = int(identifier[-1]) - 1
            _require(
                inputs == sorted(GOLDEN_INPUTS[index])
                and tuple(data["totals"][key] for key in GOLDEN_FIELDS) == GOLDEN_TOTALS[index]
            )
        else:
            expected_inputs = {
                "empty": [],
                "zero_cost": [("SYN:AAPL", "10.000000", "0.0000")],
                "partial": [
                    ("SYN:AAPL", "10.000000", "0.0000"),
                    ("SYN:UNAVAILABLE", "10.000000", "10.0000"),
                ],
                "unavailable": [("SYN:UNAVAILABLE", "10.000000", "10.0000")],
            }[identifier]
            _require(inputs == sorted(expected_inputs))
    if payload is not None:
        request = _safe_object(payload)
        if identifier.startswith("portfolio_"):
            _require(
                data["name"] == request["name"].strip()
                and data["description"]
                == (request["description"].strip() if request["description"] is not None else None)
            )
        else:
            _require(
                data["quantity"] == request["quantity"]
                and data["average_cost"] == request["average_cost"]
                and (
                    "instrument_id" not in request
                    or data["instrument_id"] == request["instrument_id"]
                )
            )


class PortfolioProof:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.native = NativeProof(database)
        self.checks: list[dict[str, Any]] = []
        self.cases: dict[str, dict[str, Any]] = {}
        self.responses_checked = 0
        self.restarts = 0
        self.private_identities: set[str] = set()

    def mark(self, identifier: str) -> None:
        _require(
            identifier in REQUIRED_CHECKS and identifier not in {item["id"] for item in self.checks}
        )
        self.checks.append({"id": identifier, "passed": True})

    def request(
        self,
        operation: str,
        token: str | None,
        *,
        portfolio_id: str | None = None,
        holding_id: str | None = None,
        payload: dict[str, Any] | None = None,
        status: int = 200,
        code: str | None = None,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        routes = {
            "catalogue": ("GET", "/instruments"),
            "portfolio_create": ("POST", ""),
            "portfolio_list": ("GET", ""),
            "portfolio_detail": ("GET", f"/{portfolio_id}"),
            "portfolio_update": ("PUT", f"/{portfolio_id}"),
            "portfolio_delete": ("DELETE", f"/{portfolio_id}"),
            "holding_create": ("POST", f"/{portfolio_id}/holdings"),
            "holding_list": ("GET", f"/{portfolio_id}/holdings"),
            "holding_detail": ("GET", f"/{portfolio_id}/holdings/{holding_id}"),
            "holding_update": ("PUT", f"/{portfolio_id}/holdings/{holding_id}"),
            "holding_delete": ("DELETE", f"/{portfolio_id}/holdings/{holding_id}"),
            "metrics": ("GET", f"/{portfolio_id}/metrics"),
        }
        _require(operation in routes, "CONFIGURATION_INVALID")
        if operation not in ("catalogue", "portfolio_create", "portfolio_list"):
            _uuid(portfolio_id)
        if operation in ("holding_detail", "holding_update", "holding_delete"):
            _uuid(holding_id)
        if case_id is not None:
            _require(case_id in CASE_IDS and case_id not in self.cases)
            if code is None:
                _require(SUCCESS_CASES.get(case_id) == operation)
                _validate_request(operation, payload)
            else:
                _require(ERROR_CASES.get(case_id) == (operation, status, code))
        try:
            method, suffix = routes[operation]
            response = self.native.current_client().request(
                method,
                BASE + suffix,
                json=payload,
                headers={"Authorization": "Bearer " + token} if token else {},
            )
            raw = response.content
            _require(
                response.status_code == status
                and not response.history
                and "set-cookie" not in response.headers
                and response.headers.get("content-type", "").split(";")[0] == "application/json",
                "WIRE_INVALID",
            )
            private = (*self.native.tokens, *self.private_identities, str(self.database))
            _require(all(value.encode("utf-8") not in raw for value in private), "TOKEN_REFLECTION")
            data = _wire_body(raw, operation, status, code, forbidden=private)
            if case_id is not None:
                self.cases[case_id] = {
                    "id": case_id,
                    "operation": operation,
                    "request": json.loads(json.dumps(payload)) if code is None else None,
                    "status": status,
                    "content_type": "application/json",
                    "body_utf8": raw.decode("utf-8"),
                    "expected": {"outcome": "error", "error_code": code}
                    if code
                    else {"outcome": "success"},
                }
            self.responses_checked += 1
            return data
        except AcceptanceFailure as error:
            if error.code in ("CORPUS_INVALID",):
                raise AcceptanceFailure("WIRE_INVALID") from None
            raise
        except (httpx.HTTPError, ValueError, TypeError, UnicodeError, KeyError, RecursionError):
            raise AcceptanceFailure("WIRE_INVALID") from None

    def run(self) -> None:
        disabled = self.native.start("disabled")
        response = self.native.current_client().post(
            BASE, content=b"{malformed", headers={"Content-Type": "application/json"}
        )
        _require(response.status_code == 403 and not self.database.exists())
        _wire_body(response.content, "portfolio_create", 403, "LOCAL_APPLICATION_ONLY")
        disabled.stop()
        self.mark("disabled_prebody_no_database")
        remote = self.native.start("remote")
        remote.stop()
        _require(not self.database.exists())
        self.mark("remote_configuration_no_database")
        self.native.start()
        self.request(
            "portfolio_list", None, status=401, code="SESSION_INVALID", case_id="session_invalid"
        )
        _require(not self.database.exists())
        self.mark("missing_bearer_no_database")
        a, a_id, _ = self.native.login("learner-a")
        self.private_identities.add(a_id)
        b, b_id, _ = self.native.login("learner-b")
        self.private_identities.add(b_id)
        _require(a_id != b_id)
        self.request(
            "portfolio_list",
            a,
            status=409,
            code="ONBOARDING_REQUIRED",
            case_id="onboarding_required",
        )
        self.complete(a)
        self.complete(b, other=True)
        a_other, a_other_id, _ = self.native.login("learner-a")
        _require(a_other_id == a_id and a_other != a)
        self.mark("current_s1_prerequisites")
        s1_a = self.native.request("state", a)
        s1_b = self.native.request("state", b)
        risk = SavedRiskProof(self.database)
        risk.native = self.native
        risk_draft = risk.request("PUT", "/draft", a, risk_input(partial=True))
        risk_a = risk.request(
            "POST", "/assessments", a, {**risk_input(), "idempotency_key": str(uuid4())}
        )
        risk_b = risk.request(
            "POST", "/assessments", b, {**risk_input("D"), "idempotency_key": str(uuid4())}
        )
        catalogue = self.request("catalogue", a, case_id="catalogue")
        expected_catalogue = [
            {
                "instrument_id": instrument,
                "display_name": fields[0],
                "asset_class": fields[1],
                "sector": fields[2],
                "currency": "USD",
            }
            for instrument, fields in sorted(DEFAULT_INSTRUMENTS.items())
        ]
        _require(catalogue["items"] == expected_catalogue and catalogue["count"] == 4)
        self.mark("versioned_synthetic_catalog")
        p = self.create(a, "Synthetic native portfolio", case_id="portfolio_created")
        pid = p["portfolio_id"]
        listed = self.request("portfolio_list", a, case_id="portfolio_list")
        _require(
            listed["items"] == [p]
            and self.request("portfolio_detail", a, portfolio_id=pid, case_id="portfolio_detail")
            == p
        )
        update = self.portfolio_payload(" Synthetic native revised ", " synthetic description ")
        changed = self.request(
            "portfolio_update", a, portfolio_id=pid, payload=update, case_id="portfolio_updated"
        )
        _require(
            changed["name"] == "Synthetic native revised"
            and changed["description"] == "synthetic description"
            and changed["created_at"] == p["created_at"]
            and _utc(changed["updated_at"]) >= _utc(p["updated_at"])
        )
        _require(
            self.request(
                "portfolio_update",
                a,
                portfolio_id=pid,
                payload=update,
                case_id="portfolio_unchanged",
            )
            == changed
        )
        h = self.add(a, pid, "SYN:AAPL", "10.000000", "150.0000", case_id="holding_created")
        hid = h["holding_id"]
        _require(
            self.request("holding_list", a, portfolio_id=pid, case_id="holding_list")["items"]
            == [h]
            and self.request(
                "holding_detail", a, portfolio_id=pid, holding_id=hid, case_id="holding_detail"
            )
            == h
        )
        h_update = self.holding_payload("2.000000", "100.0000")
        h_changed = self.request(
            "holding_update",
            a,
            portfolio_id=pid,
            holding_id=hid,
            payload=h_update,
            case_id="holding_updated",
        )
        _require(
            h_changed["quantity"] == "2.000000"
            and h_changed["average_cost"] == "100.0000"
            and h_changed["instrument_id"] == h["instrument_id"]
            and h_changed["created_at"] == h["created_at"]
        )
        _require(
            self.request(
                "holding_update",
                a,
                portfolio_id=pid,
                holding_id=hid,
                payload=h_update,
                case_id="holding_unchanged",
            )
            == h_changed
        )
        _require(self.request("portfolio_detail", a, portfolio_id=pid) == changed)
        self.mark("owned_holding_crud_noop")
        holdings_before = self.request("holding_list", a, portfolio_id=pid)
        for number, invalid in enumerate(
            (
                {**self.holding_payload("1.000000", "1.0000", "SYN:BND"), "quantity": 1},
                {**self.holding_payload("1.000000", "1.0000", "SYN:BND"), "quantity": "1.0"},
                {**self.holding_payload("1.000000", "1.0000", "SYN:BND"), "holding_version": "v0"},
                {**self.holding_payload("1.000000", "1.0000", "SYN:BND"), "owner_id": b_id},
            )
        ):
            self.request(
                "holding_create",
                a,
                portfolio_id=pid,
                payload=invalid,
                status=422,
                code="VALIDATION_ERROR",
                case_id="validation_error" if number == 0 else None,
            )
        _require(self.request("holding_list", a, portfolio_id=pid) == holdings_before)
        self.request(
            "portfolio_update",
            a,
            portfolio_id=pid,
            payload={**update, "portfolio_version": "v0"},
            status=422,
            code="VALIDATION_ERROR",
        )
        _require(self.request("portfolio_detail", a, portfolio_id=pid) == changed)
        self.mark("canonical_input_rejections_unchanged")
        other_a = self.create(a, "Synthetic second parent")
        other_b = self.create(b, "Synthetic learner B portfolio")
        b_holding = self.add(b, other_b["portfolio_id"], "SYN:BND", "1.000000", "80.0000")
        for operation in (
            "portfolio_detail",
            "portfolio_update",
            "portfolio_delete",
            "holding_list",
            "holding_create",
            "metrics",
        ):
            payload = (
                self.portfolio_payload("Synthetic forbidden update")
                if operation == "portfolio_update"
                else (
                    self.holding_payload("1.000000", "1.0000", "SYN:OTHER")
                    if operation == "holding_create"
                    else None
                )
            )
            self.request(
                operation,
                b,
                portfolio_id=pid,
                payload=payload,
                status=404,
                code="LOCAL_PORTFOLIO_NOT_FOUND",
                case_id="portfolio_not_found" if operation == "portfolio_detail" else None,
            )
        for operation in ("holding_detail", "holding_update", "holding_delete"):
            self.request(
                operation,
                a,
                portfolio_id=other_a["portfolio_id"],
                holding_id=hid,
                payload=h_update if operation == "holding_update" else None,
                status=404,
                code="LOCAL_HOLDING_NOT_FOUND",
                case_id="holding_not_found" if operation == "holding_detail" else None,
            )
        self.request(
            "holding_detail",
            a,
            portfolio_id=other_a["portfolio_id"],
            holding_id=b_holding["holding_id"],
            status=404,
            code="LOCAL_HOLDING_NOT_FOUND",
        )
        _require(
            self.request("holding_list", a, portfolio_id=pid) == holdings_before
            and self.request("holding_list", b, portfolio_id=other_b["portfolio_id"])["items"]
            == [b_holding]
        )
        self.mark("cross_owner_and_parent_isolation")
        self.request(
            "holding_create",
            a,
            portfolio_id=pid,
            payload=self.holding_payload("1.000000", "1.0000", "SYN:OTHER"),
            status=422,
            code="UNSUPPORTED_INSTRUMENT",
            case_id="unsupported_instrument",
        )
        self.request(
            "holding_create",
            a,
            portfolio_id=pid,
            payload=self.holding_payload("1.000000", "1.0000", "SYN:AAPL"),
            status=409,
            code="HOLDING_ALREADY_EXISTS",
            case_id="holding_duplicate",
        )
        self.request(
            "holding_delete", a, portfolio_id=pid, holding_id=hid, case_id="holding_deleted"
        )
        _require(self.request("holding_list", a, portfolio_id=pid)["items"] == [])
        self.add(a, pid, "SYN:MSFT", "1.000000", "400.0000")
        self.request("portfolio_delete", a, portfolio_id=pid, case_id="portfolio_deleted")
        self.request(
            "holding_list", a, portfolio_id=pid, status=404, code="LOCAL_PORTFOLIO_NOT_FOUND"
        )
        _require(self.request("portfolio_list", a)["items"] == [other_a])
        self.mark("owned_portfolio_crud_noop")
        golden_portfolios: list[str] = []
        for number, (inputs, expected) in enumerate(
            zip(GOLDEN_INPUTS, GOLDEN_TOTALS, strict=True), start=1
        ):
            golden = self.create(a, f"Synthetic golden {number}")
            golden_portfolios.append(golden["portfolio_id"])
            for instrument, quantity, cost in inputs:
                self.add(a, golden["portfolio_id"], instrument, quantity, cost)
            result = self.request(
                "metrics", a, portfolio_id=golden["portfolio_id"], case_id=f"golden_{number}"
            )
            _assert_valuation(result)
            _require(tuple(result["totals"][key] for key in GOLDEN_FIELDS) == expected)
        self.mark("six_decimal_golden_cases")
        mixed = self.create(a, "Synthetic price availability")
        mixed_id = mixed["portfolio_id"]
        _assert_valuation(self.request("metrics", a, portfolio_id=mixed_id, case_id="empty"))
        priced = self.add(a, mixed_id, "SYN:AAPL", "10.000000", "0.0000")
        zero = self.request("metrics", a, portfolio_id=mixed_id, case_id="zero_cost")
        _assert_valuation(zero)
        _require(
            zero["totals"]["gain_loss_percent"] is None and zero["totals"]["gain_loss"] == "2000.00"
        )
        self.mark("zero_cost_and_rounded_zero")
        self.add(a, mixed_id, "SYN:UNAVAILABLE", "10.000000", "10.0000")
        _assert_valuation(self.request("metrics", a, portfolio_id=mixed_id, case_id="partial"))
        self.request("holding_delete", a, portfolio_id=mixed_id, holding_id=priced["holding_id"])
        _assert_valuation(self.request("metrics", a, portfolio_id=mixed_id, case_id="unavailable"))
        self.mark("honest_empty_partial_unavailable")
        current = self.request("portfolio_list", a)
        for number in range(current["count"], 20):
            self.create(a, f"Synthetic quota {number + 1}")
        saved_a = self.request("portfolio_list", a)
        _require(saved_a["count"] == 20)
        self.request(
            "portfolio_create",
            a,
            payload=self.portfolio_payload("Synthetic overflow"),
            status=409,
            code="PORTFOLIO_LIMIT_REACHED",
            case_id="portfolio_limit",
        )
        _require(
            self.request("portfolio_list", a) == saved_a
            and self.request("portfolio_list", b)["items"] == [other_b]
        )
        self.mark("duplicate_and_portfolio_capacity")
        self.verify_schema3()
        _require(
            self.native.request("state", a) == s1_a
            and self.native.request("state", b) == s1_b
            and risk.request("GET", "/draft", a) == risk_draft
            and risk.request("GET", "/assessments", a)["items"] == [risk_a]
            and risk.request("GET", "/assessments", b)["items"] == [risk_b]
        )
        self.mark("schema3_preserves_s1_and_risk")
        kept = golden_portfolios[0]
        kept_holdings = self.request("holding_list", a, portfolio_id=kept)
        self.restart()
        self.mark("first_native_restart")
        _require(
            self.request("portfolio_list", a) == saved_a
            and self.request("holding_list", a, portfolio_id=kept) == kept_holdings
            and self.native.request("state", a) == s1_a
            and self.native.request("state", b) == s1_b
            and risk.request("GET", "/draft", a) == risk_draft
            and risk.request("GET", "/assessments", a)["items"] == [risk_a]
            and risk.request("GET", "/assessments", b)["items"] == [risk_b]
        )
        self.mark("persisted_portfolios_holdings_and_risk")
        self.native.request("consent", a, {**CONSENT_REQUEST, "consent_given": False})
        self.request("portfolio_list", a, status=409, code="ONBOARDING_REQUIRED")
        self.native.request("consent", a, CONSENT_REQUEST)
        self.request("metrics", a, portfolio_id=kept, status=409, code="ONBOARDING_REQUIRED")
        self.native.request("complete", a, COMPLETE_REQUEST)
        recompleted = self.native.request("state", a)
        self.mark("withdrawal_reacceptance_gates")
        _require(
            self.request("portfolio_list", a) == saved_a
            and self.request("holding_list", a, portfolio_id=kept) == kept_holdings
            and risk.request("GET", "/assessments", a)["items"] == [risk_a]
        )
        self.mark("no_implicit_record_erasure")
        self.native.request("logout", a)
        self.request("portfolio_list", a, status=401, code="SESSION_INVALID")
        _require(self.request("portfolio_list", a_other) == saved_a)
        self.mark("durable_per_session_logout")
        self.restart()
        self.mark("second_native_restart")
        self.request("portfolio_list", a, status=401, code="SESSION_INVALID")
        _require(self.request("portfolio_list", a_other) == saved_a)
        started = time.monotonic()
        before = datetime.now(timezone.utc)
        expiring, expiring_id, expires = self.native.login("learner-b")
        after = datetime.now(timezone.utc)
        _require(expiring_id == b_id)
        self.wait_real_expiry(
            expiring, expires, started=started, before_login=before, after_login=after
        )
        # The same real wait must deny both domains; never add another expiry sleep.
        risk.request("GET", "/draft", expiring, status=401, code="SESSION_INVALID")
        risk.request("GET", "/assessments?limit=2", expiring, status=401, code="SESSION_INVALID")
        self.mark("real_one_minute_expiry")
        fresh_a, fresh_a_id, _ = self.native.login("learner-a")
        fresh_b, fresh_b_id, _ = self.native.login("learner-b")
        _require(
            fresh_a_id == a_id
            and fresh_b_id == b_id
            and self.request("portfolio_list", fresh_a) == saved_a
            and self.request("holding_list", fresh_a, portfolio_id=kept) == kept_holdings
            and self.request("portfolio_list", fresh_b)["items"] == [other_b]
            and self.request("holding_list", fresh_b, portfolio_id=other_b["portfolio_id"])["items"]
            == [b_holding]
            and self.native.request("state", fresh_a) == recompleted
            and self.native.request("state", fresh_b) == s1_b
            and risk.request("GET", "/draft", fresh_a) == risk_draft
            and risk.request("GET", "/assessments", fresh_a)["items"] == [risk_a]
            and risk.request("GET", "/assessments", fresh_b)["items"] == [risk_b]
            and risk.request("GET", "/assessments/" + risk_b["assessment_id"], fresh_b) == risk_b
        )
        self.mark("records_preserved_after_expiry")
        for server in self.native.servers:
            server.stop()
            _require(
                all(
                    value.encode("utf-8") not in server.diagnostics()
                    for value in (*self.native.tokens, *self.private_identities)
                ),
                "TOKEN_REFLECTION",
            )
        self.native.verify_storage()
        self.mark("digest_only_storage_no_reflection")
        self.mark("safe_wire_and_diagnostics")
        _require(set(self.cases) == set(CASE_IDS))
        self.mark("complete_safe_wire_corpus")

    @staticmethod
    def portfolio_payload(name: str, description: str | None = None) -> dict[str, Any]:
        return {
            "portfolio_version": "portfolio.v1",
            "name": name,
            "description": description,
            "currency": "USD",
        }

    @staticmethod
    def holding_payload(quantity: str, cost: str, instrument: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "holding_version": "holding.v1",
            "quantity": quantity,
            "average_cost": cost,
            "currency": "USD",
        }
        if instrument is not None:
            payload["instrument_id"] = instrument
        return payload

    def create(self, token: str, name: str, *, case_id: str | None = None) -> dict[str, Any]:
        data = self.request(
            "portfolio_create",
            token,
            payload=self.portfolio_payload(name),
            status=201,
            case_id=case_id,
        )
        _require(data["name"] == name.strip() and data["description"] is None)
        return data

    def add(
        self,
        token: str,
        portfolio_id: str,
        instrument: str,
        quantity: str,
        cost: str,
        *,
        case_id: str | None = None,
    ) -> dict[str, Any]:
        data = self.request(
            "holding_create",
            token,
            portfolio_id=portfolio_id,
            payload=self.holding_payload(quantity, cost, instrument),
            status=201,
            case_id=case_id,
        )
        _require(
            data["portfolio_id"] == portfolio_id
            and data["instrument_id"] == instrument
            and data["quantity"] == quantity
            and data["average_cost"] == cost
        )
        return data

    def complete(self, token: str, *, other: bool = False) -> None:
        profile = (
            {**PROFILE_REQUEST, "display_name": "Synthetic learner B"} if other else PROFILE_REQUEST
        )
        self.native.request("draft", token, profile)
        self.native.request("consent", token, CONSENT_REQUEST)
        _require(
            self.native.request("complete", token, COMPLETE_REQUEST)["onboarding_completed"] is True
        )

    def verify_schema3(self) -> None:
        """Read the exact current authority; retain the stable S2 baseline check ID.

        The method/check names remain compatible with strict S2 consumers. They
        do not claim that a later schema owner still bootstraps generation 3.
        Earlier-record preservation is checked separately in this same journey.
        """
        try:
            with closing(
                sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True)
            ) as connection:
                versions = connection.execute("SELECT version FROM schema_metadata").fetchall()
                _require(
                    type(SCHEMA_VERSION) is int
                    and SCHEMA_VERSION >= 3
                    and len(versions) == 1
                    and type(versions[0][0]) is int
                    and versions[0][0] == SCHEMA_VERSION
                    and connection.execute("PRAGMA user_version").fetchone() == (0,)
                    and connection.execute("PRAGMA application_id").fetchone() == (0,)
                )
        except sqlite3.Error:
            raise AcceptanceFailure("PROBE_FAILED") from None

    def restart(self) -> None:
        previous = self.native.current_server()
        previous.stop()
        _require(previous.reaped and self.database.exists(), "CHILD_CLEANUP_FAILED")
        replacement = self.native.start()
        _require(
            previous.process is not None
            and replacement.process is not None
            and previous.process.pid != replacement.process.pid,
            "HANDSHAKE_INVALID",
        )
        self.restarts += 1

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
        private = (*self.native.tokens, *self.private_identities, str(self.database))
        valid_seen = False
        while time.monotonic() < started + 75:
            try:
                response = self.native.current_client().get(
                    BASE, headers={"Authorization": "Bearer " + token}
                )
                raw = response.content
                _require(
                    len(raw) <= MAX_BODY
                    and not response.history
                    and "set-cookie" not in response.headers
                    and response.headers.get("content-type", "").split(";")[0] == "application/json"
                    and all(value.encode("utf-8") not in raw for value in private),
                    "TTL_FAILED",
                )
                if response.status_code == 401:
                    _wire_body(raw, "portfolio_list", 401, "SESSION_INVALID", forbidden=private)
                    elapsed = time.monotonic() - started
                    _require(valid_seen and elapsed >= 59, "TTL_FAILED")
                    self.native.ttl_elapsed = round(elapsed, 3)
                    self.responses_checked += 1
                    return
                _require(response.status_code == 200, "TTL_FAILED")
                _wire_body(raw, "portfolio_list", 200, None, forbidden=private)
                self.responses_checked += 1
                valid_seen = True
            except (AcceptanceFailure, httpx.HTTPError, ValueError, TypeError, UnicodeError):
                raise AcceptanceFailure("TTL_FAILED") from None
            time.sleep(0.5)
        raise AcceptanceFailure("TTL_FAILED")


def evaluate_acceptance(
    *, tested_sha: str, tested_tree: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    provenance: dict[str, Any] = {}
    proof: PortfolioProof | None = None
    workspace: Path | None = None
    base: Path | None = None
    failure: str | None = None
    corpus: dict[str, Any] | None = None
    removed = False
    try:
        _require(
            all(
                isinstance(value, str) and bool(SHA_PATTERN.fullmatch(value))
                for value in (tested_sha, tested_tree)
            ),
            "PROVENANCE_INVALID",
        )
        provenance = repository_provenance(tested_sha, tested_tree)
        _require(
            provenance.get("tested_commit") == tested_sha
            and provenance.get("tested_tree") == tested_tree
            and provenance.get("working_tree_dirty") is False
            and provenance.get("tracked_dirty") is False,
            "PROVENANCE_MISMATCH",
        )
        provenance["source_hashes"] = runtime_hashes()
        provenance["source_manifest_sha256"] = manifest_sha256(provenance["source_hashes"])
        base = _temp_base().resolve()
        _require(
            base.is_dir() and base != ROOT and ROOT not in base.parents,
            "TEMPORARY_DIRECTORY_UNSAFE",
        )
        # The unchanged audited child accepts only this prefix and DB filename.
        workspace = Path(tempfile.mkdtemp(prefix="finex-s1-acceptance-", dir=base))
        proof = PortfolioProof(workspace / "state.sqlite3")
        proof.run()
        _require(
            runtime_hashes() == provenance["source_hashes"]
            and _git(["rev-parse", "HEAD"]) == tested_sha
            and _git(["rev-parse", "HEAD^{tree}"]) == tested_tree
            and not _git(["status", "--porcelain", "--untracked-files=normal"]),
            "SOURCE_CHANGED",
        )
        ids = [item.get("id") for item in proof.checks]
        _require(
            len(ids) == len(REQUIRED_CHECKS) - 1
            and set(ids) == set(REQUIRED_CHECKS) - {"owned_cleanup"}
            and all(item == {"id": item["id"], "passed": True} for item in proof.checks),
            "PROBE_FAILED",
        )
        _require(set(proof.cases) == set(CASE_IDS), "PROBE_FAILED")
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
        _require(
            proof.restarts == 2
            and len(proof.native.servers) == 5
            and proof.native.ttl_elapsed is not None
            and 59 <= proof.native.ttl_elapsed <= 75,
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
                    proof is None or all(server.reaped for server in proof.native.servers),
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
            # A change during child cleanup must not certify the earlier tree.
            _require(
                runtime_hashes() == provenance["source_hashes"]
                and _git(["rev-parse", "HEAD"]) == tested_sha
                and _git(["rev-parse", "HEAD^{tree}"]) == tested_tree
                and not _git(["status", "--porcelain", "--untracked-files=normal"]),
                "SOURCE_CHANGED",
            )
            proof.mark("owned_cleanup")
            completed_ids = [item.get("id") for item in proof.checks]
            _require(
                len(completed_ids) == len(REQUIRED_CHECKS)
                and set(completed_ids) == set(REQUIRED_CHECKS)
                and all(item == {"id": item["id"], "passed": True} for item in proof.checks),
                "PROBE_FAILED",
            )
            # Canonicalize existing validated records for reporting only;
            # actual check execution and response/case order are unchanged.
            records = {item["id"]: item for item in proof.checks}
            proof.checks = [records[identifier] for identifier in REQUIRED_CHECKS]
        except AcceptanceFailure as error:
            failure = error.code
        except Exception:
            failure = "INTERNAL_FAILURE"
    success = failure is None and proof is not None and removed and corpus is not None
    if not success:
        corpus = None
    report = {
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
        "corpus_sha256": hashlib.sha256(_json_bytes(corpus)).hexdigest()
        if corpus is not None
        else None,
        "corpus_case_ids": list(CASE_IDS) if corpus is not None else [],
        "native_process": {
            "starts": len(proof.native.servers) if proof is not None else 0,
            "application_restarts": proof.restarts if proof is not None else 0,
            "owned_pids": [
                server.process.pid for server in proof.native.servers if server.process is not None
            ]
            if proof is not None
            else [],
            "child_reaped": proof is not None
            and all(server.reaped for server in proof.native.servers),
            "temporary_directory_removed": removed,
            "session_ttl_minutes": 1,
            "real_expiry_elapsed_seconds": proof.native.ttl_elapsed if proof is not None else None,
            "shutdown": "owned_terminate_and_reap",
        },
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "limitations": [
            "Current schema-3 preservation through real restarts; "
            "populated v1/v2 upgrades are SQL-test evidence.",
            "Native 20-portfolio quota/default-catalogue duplicate checks; "
            "100-holding quota uses separate expanded-catalogue tests.",
            "Healthy default errors only; 503 faults are separate unit/HTTP tests, "
            "not fabricated native captures.",
            "No two-client S2 completion, live market data, verified identity, real money, "
            "cloud, human UAT or native-device proof.",
        ],
    }
    return report, corpus


class SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise AcceptanceFailure("CLI_ARGUMENTS_INVALID")


def _output_target(value: Path | None) -> Path | None:
    return output_target(value, ROOT)


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
            _output_target(options.report),
            _output_target(options.corpus),
        )
        _require(
            report_target is None or corpus_target is None or report_target != corpus_target,
            "OUTPUT_INVALID",
        )
        report, corpus = evaluate_acceptance(
            tested_sha=options.tested_sha, tested_tree=options.tested_tree
        )
        if corpus_target is not None and report["success"]:
            if corpus is None:
                raise AcceptanceFailure("CORPUS_INVALID")
            write_new_json(corpus_target, corpus)
        if report_target is not None:
            write_new_json(report_target, report)
        if options.format == "json":
            print(json.dumps(report, sort_keys=True))
        else:
            print(
                "S2 manual portfolio native acceptance: "
                + ("PASS" if report["success"] else "FAIL")
            )
        return 0 if report["success"] else 1
    except AcceptanceFailure as error:
        print(json.dumps({"success": False, "failures": [{"code": error.code}]}))
        return 1
    except Exception:
        print(json.dumps({"success": False, "failures": [{"code": "INTERNAL_FAILURE"}]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
