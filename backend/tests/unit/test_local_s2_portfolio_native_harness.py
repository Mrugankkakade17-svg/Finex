"""Harness controls only: mocked lifecycle/wire are not actual native acceptance."""

import copy
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, DefaultContext, Inexact, Rounded, localcontext
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

import verify_s2_manual_portfolio as verifier
from app.core.responses import APIResponse
from app.ports.adapters.sqlite_local_schema import SCHEMA_VERSION
from verify_s1_application import CONTRACT_VERSION, SCOPE, AcceptanceFailure

SHA = "a" * 40
TREE = "b" * 40
RESOURCE = "00000000-0000-4000-8000-000000000191"
HOLDING = "00000000-0000-4000-8000-000000000192"
TIME = "2026-10-11T12:00:00+00:00"
SOURCE = [{"path": "backend/app/main.py", "sha256": "c" * 64}]
GOLDENS = [
    (
        [("SYN:AAPL", "10.000000", "150.0000"), ("SYN:BND", "25.000000", "80.0000")],
        ("3500.00", "4000.00", "500.00", "14.29", "50.00", "0.500000", "50.00"),
    ),
    (
        [("SYN:MSFT", "5.000000", "500.0000")],
        ("2500.00", "2000.00", "-500.00", "-20.00", "100.00", "1.000000", "0.00"),
    ),
    (
        [
            ("SYN:AAPL", "1.000000", "200.0000"),
            ("SYN:MSFT", "0.500000", "400.0000"),
            ("SYN:BND", "2.500000", "80.0000"),
        ],
        ("600.00", "600.00", "0.00", "0.00", "33.33", "0.333333", "66.67"),
    ),
    (
        [("SYN:AAPL", "0.005025", "100.0000"), ("SYN:BND", "0.012563", "40.0000")],
        ("1.00", "2.02", "1.02", "102.00", "50.00", "0.500000", "50.00"),
    ),
    (
        [("SYN:AAPL", "0.000001", "1000000.0000")],
        ("1.00", "0.00", "-1.00", "-100.00", None, None, None),
    ),
    (
        [("SYN:MSFT", "1000000.000000", "1000000.0000")],
        (
            "1000000000000.00",
            "400000000.00",
            "-999600000000.00",
            "-99.96",
            "100.00",
            "1.000000",
            "0.00",
        ),
    ),
]


@pytest.mark.parametrize("rows,expected", GOLDENS)
def test_independent_decimal_oracle_matches_all_six_frozen_totals(
    rows: list, expected: tuple
) -> None:
    _, totals = verifier.decimal_expected(rows)
    fields = (
        "cost_basis",
        "market_value",
        "gain_loss",
        "gain_loss_percent",
        "concentration_percent",
        "hhi",
        "educational_spread_percent",
    )
    assert tuple(totals[key] for key in fields) == expected


def test_independent_decimal_oracle_uses_per_row_rounding_and_no_residual_weights() -> None:
    rows, totals = verifier.decimal_expected(GOLDENS[3][0])
    assert totals["market_value"] == "2.02"
    assert all(
        item["cost_basis"] == "0.50" and item["market_value"] == "1.01" for item in rows.values()
    )
    rows, _ = verifier.decimal_expected(GOLDENS[2][0])
    assert [item["weight_percent"] for item in rows.values()] == ["33.33"] * 3


def test_independent_decimal_oracle_handles_empty_zero_cost_and_unpriced_data() -> None:
    rows, totals = verifier.decimal_expected([])
    assert (
        rows == {}
        and totals["cost_basis"] == totals["market_value"] == totals["gain_loss"] == "0.00"
    )
    assert totals["allocation_by_asset_class"] == [] and totals["hhi"] is None
    rows, totals = verifier.decimal_expected([("SYN:AAPL", "10.000000", "0.0000")])
    assert totals["gain_loss"] == "2000.00" and totals["gain_loss_percent"] is None
    rows, totals = verifier.decimal_expected(
        [("SYN:AAPL", "10.000000", "0.0000"), ("SYN:UNAVAILABLE", "10.000000", "10.0000")]
    )
    assert totals["cost_basis"] == "100.00" and all(
        totals[key] is None for key in set(totals) - {"cost_basis"}
    )
    assert (
        rows["SYN:AAPL"]["market_value"] == "2000.00" and rows["SYN:AAPL"]["weight_percent"] is None
    )
    assert rows["SYN:UNAVAILABLE"]["market_value"] is None


def provenance() -> dict:
    return {
        "tested_commit": SHA,
        "tested_tree": TREE,
        "working_tree_dirty": False,
        "tracked_dirty": False,
        "source_hashes": copy.deepcopy(SOURCE),
    }


def install_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(verifier, "_temp_base", lambda: tmp_path.resolve(), raising=False)
    monkeypatch.setattr(verifier, "repository_provenance", lambda *_: provenance(), raising=False)
    monkeypatch.setattr(verifier, "runtime_hashes", lambda: copy.deepcopy(SOURCE))

    def git(arguments: list[str]) -> str:
        return (
            SHA
            if arguments == ["rev-parse", "HEAD"]
            else (TREE if arguments == ["rev-parse", "HEAD^{tree}"] else "")
        )

    monkeypatch.setattr(verifier, "_git", git, raising=False)


@pytest.mark.parametrize("dirty_key", ["working_tree_dirty", "tracked_dirty"])
def test_dirty_provenance_fails_before_process_or_database(
    monkeypatch: pytest.MonkeyPatch, dirty_key: str
) -> None:
    value = {**provenance(), dirty_key: True}
    monkeypatch.setattr(verifier, "repository_provenance", lambda *_: value, raising=False)
    monkeypatch.setattr(verifier, "PortfolioProof", lambda *_: pytest.fail("Unexpected child"))
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False and corpus is None
    assert report["failures"] == [{"code": "PROVENANCE_MISMATCH"}]
    assert report["native_process"]["starts"] == 0


def test_wrong_requested_revision_is_not_replaced(monkeypatch: pytest.MonkeyPatch) -> None:
    def wrong(*_: object) -> dict:
        raise AcceptanceFailure("PROVENANCE_MISMATCH")

    monkeypatch.setattr(verifier, "repository_provenance", wrong, raising=False)
    monkeypatch.setattr(verifier, "PortfolioProof", lambda *_: pytest.fail("Unexpected child"))
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["failures"] == [{"code": "PROVENANCE_MISMATCH"}] and corpus is None


@pytest.mark.parametrize("failure", ["WIRE_INVALID", "CHILD_CLEANUP_FAILED", "private"])
def test_every_failure_reaps_only_owned_child_and_removes_own_sidecars(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure: str
) -> None:
    install_clean(monkeypatch, tmp_path)
    stopped: list[bool] = []

    class Server:
        reaped = False
        process = SimpleNamespace(pid=12345)

        def stop(self) -> None:
            stopped.append(True)
            self.reaped = True
            if failure == "CHILD_CLEANUP_FAILED":
                raise AcceptanceFailure(failure)

    class Proof:
        def __init__(self, database: Path) -> None:
            self.native = SimpleNamespace(servers=[Server()], ttl_elapsed=None, tokens=set())
            self.checks: list[dict] = []
            self.responses_checked = 0
            self.restarts = 0
            self.cases: dict = {}
            self.private_identities: set[str] = set()
            database.write_text("synthetic", encoding="utf-8")
            database.with_name(database.name + "-wal").write_text("synthetic", encoding="utf-8")

        def run(self) -> None:
            if failure == "private":
                raise RuntimeError("synthetic-private-diagnostic")
            if failure == "WIRE_INVALID":
                raise AcceptanceFailure(failure)

    monkeypatch.setattr(verifier, "PortfolioProof", Proof)
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False and corpus is None
    expected = "INTERNAL_FAILURE" if failure == "private" else failure
    assert report["failures"] == [{"code": expected}]
    assert stopped == [True]
    assert report["native_process"]["temporary_directory_removed"] is True
    assert list(tmp_path.iterdir()) == []
    assert "synthetic-private" not in json.dumps(report)


def test_mark_rejects_unknown_and_repeated_check_without_claiming_success(tmp_path: Path) -> None:
    proof = verifier.PortfolioProof(tmp_path / "state.sqlite3")
    with pytest.raises(AcceptanceFailure, match="PROBE_FAILED"):
        proof.mark("invented")
    proof.mark(verifier.REQUIRED_CHECKS[0])
    with pytest.raises(AcceptanceFailure, match="PROBE_FAILED"):
        proof.mark(verifier.REQUIRED_CHECKS[0])
    assert proof.checks == [{"id": verifier.REQUIRED_CHECKS[0], "passed": True}]


def test_manifest_is_sorted_ordinal_utf8_and_rejects_duplicate_paths() -> None:
    items = [{"path": "backend/app/z.py", "sha256": "d" * 64}, *SOURCE]
    expected = hashlib.sha256(
        ("backend/app/main.py " + "C" * 64 + "\nbackend/app/z.py " + "D" * 64 + "\n").encode()
    ).hexdigest()
    assert verifier.manifest_sha256(items) == expected
    with pytest.raises(AcceptanceFailure, match="PROVENANCE_INVALID"):
        verifier.manifest_sha256([*SOURCE, *SOURCE])


def wire_body() -> dict:
    return {
        "success": True,
        "message": "Synthetic portfolio",
        "data": {
            "scope": SCOPE,
            "contract_version": CONTRACT_VERSION,
            "portfolio_version": "portfolio.v1",
            "portfolio_id": RESOURCE,
            "name": "Synthetic native portfolio",
            "description": None,
            "currency": "USD",
            "created_at": TIME,
            "updated_at": TIME,
        },
        "meta": {
            "correlationId": "synthetic-probe",
            "apiVersion": "v1",
            "dataStatus": "CACHED",
            "dataAsOf": TIME,
        },
    }


@pytest.mark.parametrize(
    ("operation", "status", "code"),
    [("portfolio_create", 403, "LOCAL_APPLICATION_ONLY"), *verifier.ERROR_CASES.values()],
)
def test_wire_accepts_real_backend_error_bytes_with_legacy_detail(
    operation: str, status: int, code: str
) -> None:
    """Exercise existing APIResponse output without any server or database."""
    actual = APIResponse.error(
        "Synthetic actual envelope", code, status_code=status, correlation_id="synthetic-probe"
    )
    decoded = verifier._wire_body(actual.body, operation, status, code)
    assert set(decoded) == {"success", "message", "detail", "error_code", "error"}
    assert decoded["detail"] == decoded["message"] == decoded["error"]["message"]


def test_error_capture_uses_actual_response_bytes_without_legacy_shape_repair(
    tmp_path: Path,
) -> None:
    actual = APIResponse.error(
        "Synthetic actual session error",
        "SESSION_INVALID",
        status_code=401,
        correlation_id="synthetic-probe",
    )
    proof = verifier.PortfolioProof(tmp_path / "state.sqlite3")
    installed_response(
        proof,
        httpx.Response(401, content=actual.body, headers={"content-type": "application/json"}),
    )
    proof.request(
        "portfolio_list", None, status=401, code="SESSION_INVALID", case_id="session_invalid"
    )
    case = proof.cases["session_invalid"]
    assert case["body_utf8"].encode("utf-8") == actual.body
    assert set(case) == {
        "id",
        "operation",
        "request",
        "status",
        "content_type",
        "body_utf8",
        "expected",
    }
    assert case["request"] is None and proof.responses_checked == 1
    assert not proof.database.exists()


def installed_response(proof: verifier.PortfolioProof, response: httpx.Response) -> list:
    sent: list = []

    def respond(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return response

    client = httpx.Client(transport=httpx.MockTransport(respond), base_url="http://127.0.0.1")
    proof.native.server = SimpleNamespace(client=client)
    return sent


def test_wire_consumes_actual_response_bytes_and_captures_no_headers(tmp_path: Path) -> None:
    proof = verifier.PortfolioProof(tmp_path / "state.sqlite3")
    sent = installed_response(proof, httpx.Response(200, json=wire_body()))
    result = proof.request(
        "portfolio_detail", None, portfolio_id=RESOURCE, case_id="portfolio_detail"
    )
    assert result["portfolio_id"] == RESOURCE and len(sent) == 1
    case = proof.cases["portfolio_detail"]
    assert set(case) == {
        "id",
        "operation",
        "request",
        "status",
        "content_type",
        "body_utf8",
        "expected",
    }
    assert case["request"] is None and case["expected"] == {"outcome": "success"}


@pytest.mark.parametrize(
    "mutation",
    ["token", "owner", "cookie", "status", "scope", "meta", "malformed", "oversized", "html"],
)
def test_wire_fails_closed_without_private_exception(tmp_path: Path, mutation: str) -> None:
    proof = verifier.PortfolioProof(tmp_path / "state.sqlite3")
    token = "q" * 43
    proof.native.tokens.add(token)
    body = wire_body()
    headers: dict = {}
    status = 200
    content: bytes | None = None
    if mutation == "token":
        body["message"] = token
    if mutation == "owner":
        body["data"]["user_id"] = RESOURCE
    if mutation == "cookie":
        headers["set-cookie"] = "synthetic"
    if mutation == "status":
        status = 302
    if mutation == "scope":
        body["data"]["contract_version"] = "v2"
    if mutation == "meta":
        body["meta"]["dataAsOf"] = None
    if mutation == "malformed":
        content = b"{synthetic-private-diagnostic"
    if mutation == "oversized":
        content = b"x" * (verifier.MAX_BODY + 1)
    if mutation == "html":
        headers["content-type"] = "text/html"
    response = (
        httpx.Response(
            status, content=content, headers={"content-type": "application/json", **headers}
        )
        if content is not None
        else httpx.Response(status, json=body, headers=headers)
    )
    installed_response(proof, response)
    with pytest.raises(AcceptanceFailure) as caught:
        proof.request("portfolio_detail", token, portfolio_id=RESOURCE)
    assert caught.value.code in {"WIRE_INVALID", "TOKEN_REFLECTION"}
    assert token not in str(caught.value) and "private-diagnostic" not in str(caught.value)
    assert proof.cases == {} and proof.responses_checked == 0


@pytest.mark.parametrize("option", ["--report", "--corpus"])
def test_cli_preserves_existing_output_before_any_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, option: str
) -> None:
    target = tmp_path / "existing.json"
    target.write_text("preserve synthetic output\n", encoding="utf-8")
    monkeypatch.setattr(
        verifier, "evaluate_acceptance", lambda **_: pytest.fail("Unexpected proof")
    )
    assert verifier.main(["--tested-sha", SHA, "--tested-tree", TREE, option, str(target)]) == 1
    assert target.read_text(encoding="utf-8") == "preserve synthetic output\n"
    assert json.loads(capsys.readouterr().out)["failures"] == [{"code": "OUTPUT_EXISTS"}]


def test_cli_never_outputs_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    def fail(**_: object) -> tuple:
        raise RuntimeError("synthetic-private-diagnostic")

    monkeypatch.setattr(verifier, "evaluate_acceptance", fail)
    assert verifier.main(["--tested-sha", SHA, "--tested-tree", TREE]) == 1
    output = capsys.readouterr().out
    assert "private-diagnostic" not in output
    assert json.loads(output)["failures"] == [{"code": "INTERNAL_FAILURE"}]


def test_corpus_rejects_absent_or_wrong_schema_without_fallback() -> None:
    for value in (None, {}, {"schema_version": "other"}):
        with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
            verifier.validate_corpus(value)


def corpus_fixture() -> dict:
    """Synthetic loader-unit fixture, never claimed as a real native capture."""
    portfolio = wire_body()["data"]
    instrument = {
        "instrument_id": "SYN:AAPL",
        "display_name": "Synthetic Apple example",
        "asset_class": "EQUITY",
        "sector": "TECHNOLOGY",
        "currency": "USD",
    }
    holding = {
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "holding_version": "holding.v1",
        "catalog_version": "synthetic_catalog.v1",
        "portfolio_id": RESOURCE,
        "holding_id": HOLDING,
        **instrument,
        "quantity": "1.000000",
        "average_cost": "200.0000",
        "created_at": TIME,
        "updated_at": TIME,
    }
    metrics = {
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "metrics_version": "portfolio_metrics.v1",
        "formula_version": "manual_portfolio_math.v1",
        "catalog_version": "synthetic_catalog.v1",
        "quote_snapshot_version": "synthetic_quotes.v1",
        "portfolio_id": RESOURCE,
        "currency": "USD",
        "valuation_status": "EMPTY",
        "source": "finex.synthetic.portfolio",
        "source_type": "SYNTHETIC",
        "fixture_as_of": "2026-01-01T00:00:00Z",
        "calculated_at": TIME,
        "missing_instrument_ids": [],
        "limitations": list(verifier.LIMITATIONS),
        "holdings": [],
        "totals": {
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
    }
    cases: list[dict] = []
    for identifier, operation in verifier.SUCCESS_CASES.items():
        request = None
        if operation in ("portfolio_create", "portfolio_update"):
            request = {
                key: portfolio[key]
                for key in ("portfolio_version", "name", "description", "currency")
            }
        if operation in ("holding_create", "holding_update"):
            request = {
                key: holding[key]
                for key in ("holding_version", "quantity", "average_cost", "currency")
            }
            if operation == "holding_create":
                request["instrument_id"] = holding["instrument_id"]
        data = copy.deepcopy(portfolio)
        if operation == "catalogue":
            data = {
                "scope": SCOPE,
                "contract_version": CONTRACT_VERSION,
                "catalog_version": "synthetic_catalog.v1",
                "currency": "USD",
                "items": [
                    {
                        "instrument_id": key,
                        "display_name": value[0],
                        "asset_class": value[1],
                        "sector": value[2],
                        "currency": "USD",
                    }
                    for key, value in sorted(verifier.DEFAULT_INSTRUMENTS.items())
                ],
                "count": 4,
            }
        if operation == "portfolio_list":
            data = {
                "scope": SCOPE,
                "contract_version": CONTRACT_VERSION,
                "portfolio_version": "portfolio.v1",
                "items": [portfolio],
                "count": 1,
            }
        if operation.startswith("holding_"):
            data = copy.deepcopy(holding)
        if operation == "holding_list":
            data = {
                "scope": SCOPE,
                "contract_version": CONTRACT_VERSION,
                "holding_version": "holding.v1",
                "catalog_version": "synthetic_catalog.v1",
                "portfolio_id": RESOURCE,
                "items": [holding],
                "count": 1,
            }
        if operation.endswith("_delete"):
            data = {
                "scope": SCOPE,
                "contract_version": CONTRACT_VERSION,
                "portfolio_id": RESOURCE,
                "entity_type": operation.split("_")[0],
                "deleted": True,
            }
            if operation == "portfolio_delete":
                data["portfolio_version"] = "portfolio.v1"
            else:
                data.update(holding_version="holding.v1", holding_id=HOLDING)
        if operation == "metrics":
            data = copy.deepcopy(metrics)
            inputs = (
                GOLDENS[int(identifier[-1]) - 1][0]
                if identifier.startswith("golden_")
                else {
                    "empty": [],
                    "zero_cost": [("SYN:AAPL", "10.000000", "0.0000")],
                    "partial": [
                        ("SYN:AAPL", "10.000000", "0.0000"),
                        ("SYN:UNAVAILABLE", "10.000000", "10.0000"),
                    ],
                    "unavailable": [("SYN:UNAVAILABLE", "10.000000", "10.0000")],
                }[identifier]
            )
            expected_rows, totals = verifier.decimal_expected(inputs)
            data["totals"] = totals
            unavailable = [
                key for key, _, _ in inputs if verifier.DEFAULT_INSTRUMENTS[key][3] is None
            ]
            data["valuation_status"] = (
                "EMPTY"
                if not inputs
                else (
                    "UNAVAILABLE"
                    if len(unavailable) == len(inputs)
                    else ("INCOMPLETE" if unavailable else "COMPLETE")
                )
            )
            data["missing_instrument_ids"] = sorted(unavailable)
            for index, (key, quantity, cost) in enumerate(inputs):
                label, asset, sector, price = verifier.DEFAULT_INSTRUMENTS[key]
                data["holdings"].append(
                    {
                        "holding_version": "holding.v1",
                        "portfolio_id": RESOURCE,
                        "holding_id": f"00000000-0000-4000-8000-{index + 200:012d}",
                        "instrument_id": key,
                        "display_name": label,
                        "asset_class": asset,
                        "sector": sector,
                        "currency": "USD",
                        "quantity": quantity,
                        "average_cost": cost,
                        **expected_rows[key],
                        "quote": {
                            "unit_price": price,
                            "data_status": "CACHED" if price else "UNAVAILABLE",
                            "quote_as_of": verifier.AS_OF if price else None,
                            "reason": None if price else "SYNTHETIC_QUOTE_UNAVAILABLE",
                        },
                    }
                )
        envelope = {
            "success": True,
            "message": "Synthetic response",
            "data": data,
            "meta": {
                "correlationId": "synthetic-probe",
                "apiVersion": "v1",
                "dataStatus": "CACHED",
                "dataAsOf": data.get("updated_at"),
            },
        }
        if operation == "metrics":
            envelope["meta"]["dataAsOf"] = (
                verifier.AS_OF if data["valuation_status"] == "COMPLETE" else None
            )
            envelope["meta"]["dataStatus"] = (
                "UNAVAILABLE"
                if data["valuation_status"] in ("INCOMPLETE", "UNAVAILABLE")
                else "CACHED"
            )
        cases.append(
            {
                "id": identifier,
                "operation": operation,
                "request": request,
                "status": 201 if operation.endswith("_create") else 200,
                "content_type": "application/json",
                "body_utf8": json.dumps(envelope),
                "expected": {"outcome": "success"},
            }
        )
    for identifier, (operation, status, code) in verifier.ERROR_CASES.items():
        envelope = json.loads(
            APIResponse.error(
                "Synthetic error", code, status_code=status, correlation_id="synthetic-probe"
            ).body
        )
        cases.append(
            {
                "id": identifier,
                "operation": operation,
                "request": None,
                "status": status,
                "content_type": "application/json",
                "body_utf8": json.dumps(envelope),
                "expected": {"outcome": "error", "error_code": code},
            }
        )
    return {
        "schema_version": verifier.CORPUS_SCHEMA,
        "scope": SCOPE,
        "contract_version": CONTRACT_VERSION,
        "provenance": {
            "kind": "native_tcp_capture",
            "source": "owned_loopback_uvicorn",
            "command": verifier.COMMAND,
            "tested_commit": SHA,
            "tested_tree": TREE,
        },
        "source_hashes": copy.deepcopy(SOURCE),
        "source_manifest_sha256": hashlib.sha256(
            ("backend/app/main.py " + "C" * 64 + "\n").encode()
        ).hexdigest(),
        "cases": cases,
    }


def test_complete_bounded_unit_corpus_is_valid_but_not_native_execution() -> None:
    verifier.validate_corpus(corpus_fixture())


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "scope",
        "extra",
        "provenance",
        "sha",
        "source_manifest",
        "source_path",
        "missing",
        "duplicate",
        "case_extra",
        "operation",
        "status",
        "boolean_status",
        "content_type",
        "raw_utf8",
        "raw_size",
        "token",
        "owner",
        "header",
        "request_owner",
        "error_code",
        "unsafe_request",
    ],
)
def test_corpus_privacy_and_binding_fail_closed(mutation: str) -> None:
    corpus = corpus_fixture()
    case = corpus["cases"][0]
    if mutation == "version":
        corpus["schema_version"] = "other"
    if mutation == "scope":
        corpus["scope"] = "other"
    if mutation == "extra":
        corpus["headers"] = {}
    if mutation == "provenance":
        corpus["provenance"]["kind"] = "synthetic_fixture"
    if mutation == "sha":
        corpus["provenance"]["tested_commit"] = "invalid"
    if mutation == "source_manifest":
        corpus["source_manifest_sha256"] = "e" * 64
    if mutation == "source_path":
        corpus["source_hashes"][0]["path"] = "../private"
    if mutation == "missing":
        corpus["cases"].pop()
    if mutation == "duplicate":
        corpus["cases"][-1] = copy.deepcopy(case)
    if mutation == "case_extra":
        case["headers"] = {}
    if mutation == "operation":
        case["operation"] = "mock_login"
    if mutation == "status":
        case["status"] = 503
    if mutation == "boolean_status":
        case["status"] = True
    if mutation == "content_type":
        case["content_type"] = "text/html"
    if mutation == "raw_utf8":
        case["body_utf8"] = "\ud800"
    if mutation == "raw_size":
        case["body_utf8"] = "x" * (verifier.MAX_BODY + 1)
    if mutation == "token":
        case["body_utf8"] = case["body_utf8"].replace("Synthetic response", "q" * 43)
    if mutation in ("owner", "header"):
        body = json.loads(case["body_utf8"])
        body["user_id" if mutation == "owner" else "authorization"] = "synthetic"
        case["body_utf8"] = json.dumps(body)
    if mutation in ("request_owner", "unsafe_request"):
        corpus["cases"][1]["request"]["owner_id" if mutation == "request_owner" else "extra"] = (
            "synthetic"
        )
    if mutation == "error_code":
        corpus["cases"][-1]["expected"]["error_code"] = "other"
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus, forbidden=("q" * 43,))


@pytest.mark.parametrize("mutation", ["false_golden", "changed_price", "nondefault_catalogue"])
def test_corpus_semantic_case_evidence_cannot_be_relabelled(mutation: str) -> None:
    corpus = corpus_fixture()
    if mutation == "false_golden":
        empty = next(item for item in corpus["cases"] if item["id"] == "empty")
        golden = next(item for item in corpus["cases"] if item["id"] == "golden_1")
        golden["body_utf8"] = empty["body_utf8"]
    else:
        item = (
            corpus["cases"][0]
            if mutation == "nondefault_catalogue"
            else next(item for item in corpus["cases"] if item["id"] == "golden_1")
        )
        body = json.loads(item["body_utf8"])
        if mutation == "nondefault_catalogue":
            body["data"]["items"].pop()
            body["data"]["count"] = 3
        else:
            body["data"]["holdings"][0]["quote"]["unit_price"] = "199.0000"
        item["body_utf8"] = json.dumps(body)
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus)


def fake_complete(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list:
    """Unit-only completed proof: mocks cannot substitute for published acceptance."""
    install_clean(monkeypatch, tmp_path)
    stopped: list = []

    class Server:
        def __init__(self, identifier: int) -> None:
            self.reaped = False
            self.process = SimpleNamespace(pid=identifier)

        def stop(self) -> None:
            stopped.append(self.process.pid)
            self.reaped = True

    class Proof:
        def __init__(self, database: Path) -> None:
            self.database = database
            self.native = SimpleNamespace(
                servers=[Server(index) for index in range(1, 6)],
                ttl_elapsed=60.0,
                tokens={"q" * 43},
            )
            self.checks = [
                {"id": key, "passed": True}
                for key in verifier.REQUIRED_CHECKS
                if key != "owned_cleanup"
            ]
            self.responses_checked = 200
            self.restarts = 2
            self.cases = {item["id"]: item for item in corpus_fixture()["cases"]}
            self.private_identities: set = set()
            database.write_text("synthetic database", encoding="utf-8")
            database.with_name("state.sqlite3-wal").write_text(
                "synthetic sidecar", encoding="utf-8"
            )

        def run(self) -> None:
            pass

        def mark(self, identifier: str) -> None:
            self.checks.append({"id": identifier, "passed": True})

    monkeypatch.setattr(verifier, "PortfolioProof", Proof)
    return stopped


def test_mock_completed_lifecycle_binds_corpus_hashes_then_cleans_owned_files(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    stopped = fake_complete(monkeypatch, tmp_path)
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is True and corpus is not None
    assert (
        report["tested_commit"] == SHA
        and report["tested_tree"] == TREE
        and report["failures"] == []
    )
    assert report["corpus_sha256"] == hashlib.sha256(verifier._json_bytes(corpus)).hexdigest()
    assert {item["id"] for item in report["checks"]} == set(verifier.REQUIRED_CHECKS)
    assert stopped == [1, 2, 3, 4, 5] and list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("mutation", ["sources", "head", "tree", "dirty"])
def test_source_or_revision_change_after_run_cannot_be_certified(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    stopped = fake_complete(monkeypatch, tmp_path)
    if mutation == "sources":
        calls = 0

        def changing() -> list:
            nonlocal calls
            calls += 1
            return SOURCE if calls == 1 else [{"path": "backend/app/main.py", "sha256": "d" * 64}]

        monkeypatch.setattr(verifier, "runtime_hashes", changing)
    else:
        monkeypatch.setattr(
            verifier,
            "_git",
            lambda args: (
                "e" * 40
                if mutation == "head" and args == ["rev-parse", "HEAD"]
                else "f" * 40
                if mutation == "tree" and args == ["rev-parse", "HEAD^{tree}"]
                else "modified"
                if mutation == "dirty" and args[0] == "status"
                else SHA
                if args == ["rev-parse", "HEAD"]
                else TREE
                if args == ["rev-parse", "HEAD^{tree}"]
                else ""
            ),
        )
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert (
        report["success"] is False
        and report["failures"] == [{"code": "SOURCE_CHANGED"}]
        and corpus is None
    )
    assert stopped == [1, 2, 3, 4, 5] and list(tmp_path.iterdir()) == []


def test_mock_unreaped_child_prevents_temporary_database_deletion(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_complete(monkeypatch, tmp_path)

    def no_reap(self: object) -> None:
        raise AcceptanceFailure("CHILD_CLEANUP_FAILED")

    original = verifier.PortfolioProof

    def unreaped(database: Path) -> object:
        proof = original(database)
        proof.native.servers[0].stop = lambda: no_reap(proof.native.servers[0])
        return proof

    monkeypatch.setattr(verifier, "PortfolioProof", unreaped)
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False and corpus is None
    assert report["failures"] == [{"code": "CHILD_CLEANUP_FAILED"}]
    assert report["native_process"]["temporary_directory_removed"] is False
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "mutation", ["missing_check", "duplicate_check", "missing_case", "false_check"]
)
def test_missing_or_repeated_required_evidence_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mutation: str,
) -> None:
    fake_complete(monkeypatch, tmp_path)
    original = verifier.PortfolioProof

    def changed(database: Path) -> object:
        proof = original(database)
        if mutation == "missing_check":
            proof.checks.pop()
        if mutation == "duplicate_check":
            proof.checks[-1] = proof.checks[0]
        if mutation == "missing_case":
            proof.cases.pop(next(iter(proof.cases)))
        if mutation == "false_check":
            proof.checks[0]["passed"] = False
        return proof

    monkeypatch.setattr(verifier, "PortfolioProof", changed)
    report, corpus = verifier.evaluate_acceptance(tested_sha=SHA, tested_tree=TREE)
    assert report["success"] is False and corpus is None
    assert report["failures"] == [{"code": "PROBE_FAILED"}]


def test_native_driver_checks_disabled_remote_and_absent_bearer_before_login(
    tmp_path: Path,
) -> None:
    proof = verifier.PortfolioProof(tmp_path / "state.sqlite3")
    events: list[str] = []
    error = json.loads(
        APIResponse.error(
            "Synthetic error",
            "LOCAL_APPLICATION_ONLY",
            status_code=403,
            correlation_id="synthetic-probe",
        ).body
    )

    class Native:
        tokens: set[str] = set()

        def start(self, mode: str = "enabled") -> SimpleNamespace:
            events.append(mode)
            return SimpleNamespace(stop=lambda: events.append("stop"))

        def current_client(self) -> SimpleNamespace:
            return SimpleNamespace(post=lambda *_, **__: httpx.Response(403, json=error))

        def login(self, _: str) -> tuple:
            events.append("login")
            raise AcceptanceFailure("PROBE_FAILED")

    proof.native = Native()

    def missing(*_: object, **__: object) -> dict:
        events.append("missing_bearer")
        return {}

    proof.request = missing
    with pytest.raises(AcceptanceFailure, match="PROBE_FAILED"):
        proof.run()
    assert events == ["disabled", "stop", "remote", "stop", "enabled", "missing_bearer", "login"]
    assert [item["id"] for item in proof.checks] == list(verifier.REQUIRED_CHECKS[:3])


@pytest.mark.parametrize("scenario", ["early401", "wrong_ttl", "failure"])
def test_mocked_expiry_refuses_early_inactive_or_incorrect_clock_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str
) -> None:
    proof = verifier.PortfolioProof(tmp_path / "state.sqlite3")
    now = datetime.fromisoformat(TIME)
    monkeypatch.setattr(verifier.time, "monotonic", lambda: 0)
    token = "q" * 43
    code = "SESSION_INVALID" if scenario != "failure" else "LOCAL_STORE_UNAVAILABLE"
    error = json.loads(
        APIResponse.error(
            "Synthetic error",
            code,
            status_code=401 if scenario != "failure" else 503,
            correlation_id="synthetic-probe",
        ).body
    )
    installed_response(proof, httpx.Response(401 if scenario != "failure" else 503, json=error))
    with pytest.raises(AcceptanceFailure, match="TTL_FAILED"):
        proof.wait_real_expiry(
            token,
            now + timedelta(seconds=1 if scenario == "wrong_ttl" else 60),
            started=0,
            before_login=now,
            after_login=now,
        )
    assert proof.native.ttl_elapsed is None


def test_current_schema_observer_uses_metadata_and_leaves_owned_file_unchanged(
    tmp_path: Path,
) -> None:
    """A real isolated SQLite read, not a complete native application run."""
    database = tmp_path / "state.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE schema_metadata (version INTEGER NOT NULL)")
        connection.execute("INSERT INTO schema_metadata VALUES(?)", (SCHEMA_VERSION,))
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    proof = verifier.PortfolioProof(database)
    proof.verify_schema3()
    assert before == hashlib.sha256(database.read_bytes()).hexdigest()
    assert proof.checks == []


@pytest.mark.parametrize(
    ("versions", "user_version", "application_id"),
    [
        ((SCHEMA_VERSION,), 3, 0),
        ((SCHEMA_VERSION,), 0, 23),
        ((2,), 3, 0),
        ((SCHEMA_VERSION + 1,), 0, 0),
        ((SCHEMA_VERSION - 1,), 0, 0),
        ((SCHEMA_VERSION, SCHEMA_VERSION), 0, 0),
        ((), 0, 0),
        ((float(SCHEMA_VERSION),), 0, 0),
        ((str(SCHEMA_VERSION),), 0, 0),
        (None, 0, 0),
    ],
)
def test_current_schema_observer_rejects_wrong_authority_and_foreign_markers(
    tmp_path: Path, versions: tuple | None, user_version: int, application_id: int
) -> None:
    database = tmp_path / "state.sqlite3"
    with sqlite3.connect(database) as connection:
        if versions is not None:
            connection.execute("CREATE TABLE schema_metadata (version)")
            connection.executemany(
                "INSERT INTO schema_metadata VALUES(?)", [(v,) for v in versions]
            )
        connection.execute(f"PRAGMA user_version={user_version}")
        connection.execute(f"PRAGMA application_id={application_id}")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    with pytest.raises(AcceptanceFailure, match="PROBE_FAILED"):
        verifier.PortfolioProof(database).verify_schema3()
    assert before == hashlib.sha256(database.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("identifier", "field"),
    [
        ("portfolio_detail", "message"),
        ("session_invalid", "message"),
        ("session_invalid", "error.message"),
    ],
)
@pytest.mark.parametrize("invalid", [17, None, False, []])
def test_corpus_rejects_nonstring_envelope_messages(
    identifier: str, field: str, invalid: object
) -> None:
    corpus = corpus_fixture()
    case = next(item for item in corpus["cases"] if item["id"] == identifier)
    body = json.loads(case["body_utf8"])
    if field == "error.message":
        body["error"]["message"] = invalid
    else:
        body["message"] = invalid
    case["body_utf8"] = json.dumps(body)
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus)


def malformed_detail(body: dict, mutation: str) -> dict:
    if mutation == "missing":
        del body["detail"]
    elif mutation == "divergent_message":
        body["message"] = "Synthetic different message"
    elif mutation == "divergent_nested_message":
        body["error"]["message"] = "Synthetic different nested message"
    else:
        body["detail"] = {
            "null": None,
            "number": 17,
            "boolean": False,
            "list": [],
            "divergent_detail": "Synthetic different detail",
        }[mutation]
    return body


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "null",
        "number",
        "boolean",
        "list",
        "divergent_detail",
        "divergent_message",
        "divergent_nested_message",
    ],
)
def test_wire_rejects_missing_nonstrict_or_divergent_legacy_detail(mutation: str) -> None:
    actual = APIResponse.error(
        "Synthetic error", "SESSION_INVALID", status_code=401, correlation_id="synthetic-probe"
    )
    raw = json.dumps(malformed_detail(json.loads(actual.body), mutation)).encode("utf-8")
    with pytest.raises(AcceptanceFailure, match="WIRE_INVALID"):
        verifier._wire_body(raw, "portfolio_list", 401, "SESSION_INVALID")


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "null",
        "number",
        "boolean",
        "list",
        "divergent_detail",
        "divergent_message",
        "divergent_nested_message",
    ],
)
def test_corpus_rejects_missing_nonstrict_or_divergent_legacy_detail(mutation: str) -> None:
    corpus = corpus_fixture()
    case = next(item for item in corpus["cases"] if item["id"] == "session_invalid")
    case["body_utf8"] = json.dumps(malformed_detail(json.loads(case["body_utf8"]), mutation))
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus)


@pytest.mark.parametrize("operation", ["portfolio_list", "holding_list"])
@pytest.mark.parametrize("ordering", ["duplicate", "reverse_uuid", "reverse_time"])
def test_corpus_rejects_duplicate_or_noncontract_ordered_lists(
    operation: str, ordering: str
) -> None:
    corpus = corpus_fixture()
    case = next(item for item in corpus["cases"] if item["id"] == operation)
    body = json.loads(case["body_utf8"])
    first = body["data"]["items"][0]
    second = copy.deepcopy(first)
    if ordering != "duplicate":
        second["portfolio_id" if operation == "portfolio_list" else "holding_id"] = (
            "00000000-0000-4000-8000-000000000193"
        )
        if operation == "holding_list":
            second.update(
                instrument_id="SYN:BND",
                display_name="Synthetic bond-fund example",
                asset_class="BOND",
                sector="FIXED_INCOME",
            )
        if ordering == "reverse_time":
            second["created_at"] = second["updated_at"] = "2026-10-11T11:59:59Z"
    body["data"]["items"] = [second, first] if ordering == "reverse_uuid" else [first, second]
    body["data"]["count"] = 2
    case["body_utf8"] = json.dumps(body)
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus)


def test_corpus_rejects_duplicate_holding_instrument_with_distinct_record_ids() -> None:
    corpus = corpus_fixture()
    case = next(item for item in corpus["cases"] if item["id"] == "holding_list")
    body = json.loads(case["body_utf8"])
    second = copy.deepcopy(body["data"]["items"][0])
    second["holding_id"] = "00000000-0000-4000-8000-000000000193"
    body["data"]["items"].append(second)
    body["data"]["count"] = 2
    case["body_utf8"] = json.dumps(body)
    with pytest.raises(AcceptanceFailure, match="CORPUS_INVALID"):
        verifier.validate_corpus(corpus)


@pytest.mark.parametrize("operation", ["portfolio_list", "holding_list"])
@pytest.mark.parametrize("order_by", ["uuid", "utc_instant"])
def test_corpus_accepts_distinct_lists_in_contract_order(operation: str, order_by: str) -> None:
    """Positive controls: time ordering compares instants rather than Z/+00 text."""
    corpus = corpus_fixture()
    case = next(item for item in corpus["cases"] if item["id"] == operation)
    body = json.loads(case["body_utf8"])
    first = body["data"]["items"][0]
    second = copy.deepcopy(first)
    second["portfolio_id" if operation == "portfolio_list" else "holding_id"] = (
        "00000000-0000-4000-8000-000000000193"
    )
    if operation == "holding_list":
        second.update(
            instrument_id="SYN:BND",
            display_name="Synthetic bond-fund example",
            asset_class="BOND",
            sector="FIXED_INCOME",
        )
    if order_by == "utc_instant":
        second["created_at"] = second["updated_at"] = "2026-10-11T11:59:59Z"
    body["data"]["items"] = [second, first] if order_by == "utc_instant" else [first, second]
    body["data"]["count"] = 2
    case["body_utf8"] = json.dumps(body)
    verifier.validate_corpus(corpus)


@pytest.mark.parametrize("golden", range(6))
@pytest.mark.parametrize("hostile", ["traps", "exponent_bounds"])
def test_independent_decimal_oracle_ignores_hostile_ambient_context(
    golden: int, hostile: str
) -> None:
    inputs, expected = GOLDENS[golden]
    with localcontext() as ambient:
        if hostile == "traps":
            ambient.traps[Inexact] = ambient.traps[Rounded] = True
        else:
            ambient.Emin, ambient.Emax, ambient.clamp = -1, 1, 1
        before = repr(ambient)
        _, totals = verifier.decimal_expected(inputs)
        assert tuple(totals[key] for key in verifier.GOLDEN_FIELDS) == expected
        assert repr(ambient) == before


def test_oracle_explicit_context_does_not_inherit_or_change_mutable_default_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GREEN-only isolation control; monkeypatch restores each changed default value."""
    monkeypatch.setattr(DefaultContext, "prec", 2)
    monkeypatch.setattr(DefaultContext, "rounding", ROUND_DOWN)
    monkeypatch.setattr(DefaultContext, "Emin", -1)
    monkeypatch.setattr(DefaultContext, "Emax", 1)
    monkeypatch.setattr(DefaultContext, "clamp", 1)
    monkeypatch.setitem(DefaultContext.traps, Inexact, True)
    monkeypatch.setitem(DefaultContext.traps, Rounded, True)
    monkeypatch.setitem(DefaultContext.flags, Inexact, True)
    before = repr(DefaultContext)
    for inputs, expected in GOLDENS:
        _, totals = verifier.decimal_expected(inputs)
        assert tuple(totals[key] for key in verifier.GOLDEN_FIELDS) == expected
    assert repr(DefaultContext) == before
