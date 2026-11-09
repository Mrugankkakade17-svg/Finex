"""Test-first owned S2 portfolio HTTP and golden wire acceptance.

Only synthetic local personas are used; bearer credentials remain in memory.
This file deliberately imports no prospective portfolio implementation.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.main import create_app
from tests.contract.test_local_s1_api import (
    AUTH,
    COMPLETE,
    CONSENT,
    ONBOARDING,
    TestClock,
    assert_error,
    finish,
    login,
)

PORT = "/api/v1/local-portfolios"
PID = "00000000-0000-4000-8000-000000000191"
HID = "00000000-0000-4000-8000-000000000192"
AS_OF = "2026-01-01T00:00:00Z"
SCOPE = {"scope": "local_educational_application", "contract_version": "local.v1"}
PORT_FIELDS = {
    *SCOPE,
    "portfolio_version",
    "portfolio_id",
    "name",
    "description",
    "currency",
    "created_at",
    "updated_at",
}
HOLD_FIELDS = {
    *SCOPE,
    "holding_version",
    "catalog_version",
    "portfolio_id",
    "holding_id",
    "instrument_id",
    "display_name",
    "asset_class",
    "sector",
    "quantity",
    "average_cost",
    "currency",
    "created_at",
    "updated_at",
}
METRIC_FIELDS = {
    *SCOPE,
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
METRIC_HOLD_FIELDS = {
    "holding_version",
    "portfolio_id",
    "holding_id",
    "instrument_id",
    "display_name",
    "asset_class",
    "sector",
    "currency",
    "quantity",
    "average_cost",
    "cost_basis",
    "quote",
    "market_value",
    "gain_loss",
    "gain_loss_percent",
    "weight_percent",
}
OPERATIONS = [
    ("GET", "/instruments"),
    ("POST", ""),
    ("GET", ""),
    ("GET", f"/{PID}"),
    ("PUT", f"/{PID}"),
    ("DELETE", f"/{PID}"),
    ("POST", f"/{PID}/holdings"),
    ("GET", f"/{PID}/holdings"),
    ("GET", f"/{PID}/holdings/{HID}"),
    ("PUT", f"/{PID}/holdings/{HID}"),
    ("DELETE", f"/{PID}/holdings/{HID}"),
    ("GET", f"/{PID}/metrics"),
]


def portfolio_input(**changes: object) -> dict:
    return {
        "portfolio_version": "portfolio.v1",
        "name": "  Training basket  ",
        "description": None,
        "currency": "USD",
        **changes,
    }


def holding_input(instrument: str = "SYN:AAPL", **changes: object) -> dict:
    return {
        "holding_version": "holding.v1",
        "instrument_id": instrument,
        "quantity": "10.000000",
        "average_cost": "150.0000",
        "currency": "USD",
        **changes,
    }


def application(path: Path, clock: TestClock | None = None, *, enabled: bool = True):
    return create_app(
        Settings(
            _env_file=None,
            local_app_enabled=enabled,
            local_db_path=path,
            llm_provider="none",
            market_data_provider="mock",
        ),
        local_clock=clock or TestClock(),
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(application(tmp_path / "portfolio.sqlite3"))


def completed(client: TestClient, alias: str = "learner-a") -> dict[str, str]:
    headers = login(client, alias)
    finish(client, headers)
    return headers


def request_body(method: str, suffix: str) -> dict | None:
    if method not in {"POST", "PUT"}:
        return None
    if "/holdings" not in suffix:
        return portfolio_input()
    body = holding_input()
    if method == "PUT":
        body.pop("instrument_id")
    return body


def created(client: TestClient, headers: dict[str, str], **changes: object) -> dict:
    response = client.post(PORT, headers=headers, json=portfolio_input(**changes))
    assert response.status_code == 201
    return response.json()["data"]


def added(
    client: TestClient,
    headers: dict[str, str],
    pid: str,
    instrument: str = "SYN:AAPL",
    **changes: object,
) -> dict:
    response = client.post(
        f"{PORT}/{pid}/holdings", headers=headers, json=holding_input(instrument, **changes)
    )
    assert response.status_code == 201
    return response.json()["data"]


def metrics(client: TestClient, headers: dict[str, str], pid: str):
    response = client.get(f"{PORT}/{pid}/metrics", headers=headers)
    assert response.status_code == 200
    return response


def utc_instant(value: object) -> datetime:
    """Require an explicit UTC instant without prescribing Z versus +00:00."""
    assert isinstance(value, str)
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)
    return parsed.astimezone(timezone.utc)


@pytest.mark.parametrize("method,suffix", OPERATIONS)
def test_each_operation_rejects_absent_bearer_before_storage(
    tmp_path: Path, method: str, suffix: str
) -> None:
    path = tmp_path / "no-credential.sqlite3"
    response = TestClient(application(path)).request(
        method, PORT + suffix, json=request_body(method, suffix)
    )
    assert_error(response, 401, "SESSION_INVALID")
    assert not path.exists()


@pytest.mark.parametrize("method,suffix", OPERATIONS)
def test_every_operation_requires_current_completed_onboarding(
    client: TestClient, method: str, suffix: str
) -> None:
    headers = login(client)
    response = client.request(
        method, PORT + suffix, headers=headers, json=request_body(method, suffix)
    )
    assert_error(response, 409, "ONBOARDING_REQUIRED")


def test_disabled_boundary_is_an_already_existing_control(tmp_path: Path) -> None:
    path = tmp_path / "disabled.sqlite3"
    response = TestClient(application(path, enabled=False)).post(
        PORT, content="{bad", headers={"Content-Type": "application/json"}
    )
    assert_error(response, 403, "LOCAL_APPLICATION_ONLY")
    assert not path.exists()


def test_catalogue_shape_order_and_no_live_price(client: TestClient) -> None:
    headers = completed(client)
    response = client.get(PORT + "/instruments", headers=headers)
    assert response.status_code == 200
    result = response.json()
    data = result["data"]
    assert set(data) == {*SCOPE, "catalog_version", "currency", "items", "count"}
    assert all(data[key] == value for key, value in SCOPE.items())
    assert data["catalog_version"] == "synthetic_catalog.v1"
    assert data["currency"] == "USD" and data["count"] == 4
    assert [item["instrument_id"] for item in data["items"]] == [
        "SYN:AAPL",
        "SYN:BND",
        "SYN:MSFT",
        "SYN:UNAVAILABLE",
    ]
    for item in data["items"]:
        assert set(item) == {"instrument_id", "display_name", "asset_class", "sector", "currency"}
    assert result["meta"]["dataStatus"] == "CACHED"
    assert result["meta"]["dataAsOf"] is None


def test_portfolio_crud_exact_shape_null_metadata_and_noop_time(tmp_path: Path) -> None:
    clock = TestClock()
    client = TestClient(application(tmp_path / "crud.sqlite3", clock))
    headers = completed(client)
    first = created(client, headers)
    pid = first["portfolio_id"]
    assert set(first) == PORT_FIELDS and first["name"] == "Training basket"
    assert first["description"] is None
    assert first["portfolio_version"] == "portfolio.v1"
    assert first["created_at"] == first["updated_at"]
    assert utc_instant(first["created_at"]) == clock.now
    listing = client.get(PORT, headers=headers)
    assert listing.json()["data"]["items"] == [first]
    assert set(listing.json()["data"]) == {*SCOPE, "portfolio_version", "items", "count"}
    assert listing.json()["meta"]["dataAsOf"] is None
    clock.now += timedelta(seconds=1)
    same = client.put(f"{PORT}/{pid}", headers=headers, json=portfolio_input())
    assert same.status_code == 200 and same.json()["data"] == first
    changed = client.put(
        f"{PORT}/{pid}",
        headers=headers,
        json=portfolio_input(name="  Updated basket  ", description="  synthetic notes  "),
    )
    assert changed.status_code == 200
    after = changed.json()["data"]
    assert after["name"] == "Updated basket" and after["description"] == "synthetic notes"
    assert after["created_at"] == first["created_at"]
    assert utc_instant(after["updated_at"]) == clock.now
    assert changed.json()["meta"]["dataAsOf"] == after["updated_at"]
    assert client.get(f"{PORT}/{pid}", headers=headers).json()["data"] == after
    deleted = client.delete(f"{PORT}/{pid}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {
        **SCOPE,
        "portfolio_version": "portfolio.v1",
        "portfolio_id": pid,
        "entity_type": "portfolio",
        "deleted": True,
    }
    assert deleted.json()["meta"]["dataAsOf"] is None
    assert_error(client.delete(f"{PORT}/{pid}", headers=headers), 404, "LOCAL_PORTFOLIO_NOT_FOUND")


def test_holding_crud_and_fixed_instrument_noop_clock(tmp_path: Path) -> None:
    clock = TestClock()
    client = TestClient(application(tmp_path / "holding.sqlite3", clock))
    headers = completed(client)
    pid = created(client, headers)["portfolio_id"]
    holding = added(client, headers, pid)
    hid = holding["holding_id"]
    assert set(holding) == HOLD_FIELDS
    assert holding["display_name"] == "Synthetic Apple example"
    assert holding["asset_class"] == "EQUITY" and holding["sector"] == "TECHNOLOGY"
    assert holding["catalog_version"] == "synthetic_catalog.v1"
    list_response = client.get(f"{PORT}/{pid}/holdings", headers=headers)
    assert list_response.json()["data"]["items"] == [holding]
    assert set(list_response.json()["data"]) == {
        *SCOPE,
        "holding_version",
        "catalog_version",
        "portfolio_id",
        "items",
        "count",
    }
    assert list_response.json()["meta"]["dataAsOf"] is None
    update = holding_input(quantity="12.000000")
    update.pop("instrument_id")
    clock.now += timedelta(seconds=1)
    changed = client.put(f"{PORT}/{pid}/holdings/{hid}", headers=headers, json=update)
    assert changed.status_code == 200 and changed.json()["data"]["quantity"] == "12.000000"
    assert utc_instant(changed.json()["meta"]["dataAsOf"]) == clock.now
    assert (
        client.get(f"{PORT}/{pid}", headers=headers).json()["data"]["updated_at"]
        == holding["created_at"]
    )
    clock.now += timedelta(seconds=1)
    assert (
        client.put(f"{PORT}/{pid}/holdings/{hid}", headers=headers, json=update).json()["data"]
        == changed.json()["data"]
    )
    assert_error(
        client.put(
            f"{PORT}/{pid}/holdings/{hid}",
            headers=headers,
            json={**update, "instrument_id": "SYN:MSFT"},
        ),
        422,
        "VALIDATION_ERROR",
    )
    deleted = client.delete(f"{PORT}/{pid}/holdings/{hid}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"] == {
        **SCOPE,
        "holding_version": "holding.v1",
        "portfolio_id": pid,
        "holding_id": hid,
        "entity_type": "holding",
        "deleted": True,
    }
    assert deleted.json()["meta"]["dataAsOf"] is None
    assert_error(
        client.get(f"{PORT}/{pid}/holdings/{hid}", headers=headers),
        404,
        "LOCAL_HOLDING_NOT_FOUND",
    )


@pytest.mark.parametrize(
    "change",
    [
        {"portfolio_version": "v2"},
        {"currency": "INR"},
        {"name": "   "},
        {"name": "x" * 101},
        {"name": 3},
        {"description": "x" * 501},
        {"description": False},
        {"owner_id": "synthetic-forbidden"},
        {"scope": "local_educational_application"},
        {"contract_version": "local.v1"},
    ],
)
def test_portfolio_rejects_invalid_types_versions_and_client_authority(
    client: TestClient, change: dict
) -> None:
    headers = completed(client)
    assert_error(
        client.post(PORT, headers=headers, json=portfolio_input(**change)), 422, "VALIDATION_ERROR"
    )
    assert client.get(PORT, headers=headers).json()["data"]["items"] == []


@pytest.mark.parametrize("field", ["portfolio_version", "name", "description", "currency"])
def test_portfolio_input_keys_are_required(client: TestClient, field: str) -> None:
    headers = completed(client)
    payload = portfolio_input()
    payload.pop(field)
    assert_error(client.post(PORT, headers=headers, json=payload), 422, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "field,value",
    [
        ("quantity", 1),
        ("quantity", True),
        ("quantity", "1.0"),
        ("quantity", "01.000000"),
        ("quantity", "+1.000000"),
        ("quantity", "1e1"),
        ("quantity", "0.000000"),
        ("quantity", "1000000.000001"),
        ("quantity", " 1.000000"),
        ("quantity", "1.000000\n"),
        ("average_cost", 150),
        ("average_cost", False),
        ("average_cost", "-0.0000"),
        ("average_cost", "150.00000"),
        ("average_cost", "1000000.0001"),
        ("average_cost", "NaN"),
        ("instrument_id", "SYN:aapl"),
        ("instrument_id", "SYN:AAPL\n"),
        ("instrument_id", "AAPL"),
        ("currency", "EUR"),
        ("holding_version", "v2"),
    ],
)
def test_holding_rejects_noncanonical_numbers_and_identifiers(
    client: TestClient, field: str, value: object
) -> None:
    headers = completed(client)
    pid = created(client, headers)["portfolio_id"]
    assert_error(
        client.post(
            f"{PORT}/{pid}/holdings", headers=headers, json=holding_input(**{field: value})
        ),
        422,
        "VALIDATION_ERROR",
    )
    assert client.get(f"{PORT}/{pid}/holdings", headers=headers).json()["data"]["items"] == []


def test_parent_ownership_and_unsupported_duplicate_precedence(client: TestClient) -> None:
    owner, other = completed(client), completed(client, "learner-b")
    pid = created(client, owner)["portfolio_id"]
    own = added(client, owner, pid)
    other_pid = created(client, other)["portfolio_id"]
    assert_error(
        client.post(f"{PORT}/{pid}/holdings", headers=other, json=holding_input("SYN:OTHER")),
        404,
        "LOCAL_PORTFOLIO_NOT_FOUND",
    )
    assert_error(
        client.post(f"{PORT}/{pid}/holdings", headers=owner, json=holding_input("SYN:OTHER")),
        422,
        "UNSUPPORTED_INSTRUMENT",
    )
    assert_error(
        client.post(f"{PORT}/{pid}/holdings", headers=owner, json=holding_input()),
        409,
        "HOLDING_ALREADY_EXISTS",
    )
    for hidden in (own["holding_id"], str(uuid4())):
        assert_error(
            client.get(f"{PORT}/{other_pid}/holdings/{hidden}", headers=other),
            404,
            "LOCAL_HOLDING_NOT_FOUND",
        )
    assert client.get(PORT, headers=other).json()["data"]["items"][0]["portfolio_id"] == other_pid
    assert_error(client.delete(f"{PORT}/{pid}", headers=other), 404, "LOCAL_PORTFOLIO_NOT_FOUND")


@pytest.mark.parametrize(
    "holdings,expected",
    [
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
    ],
)
def test_default_quote_golden_metrics_and_exact_wire(
    client: TestClient, holdings: list[tuple[str, str, str]], expected: tuple
) -> None:
    headers = completed(client)
    pid = created(client, headers)["portfolio_id"]
    for instrument, quantity, cost in holdings:
        added(client, headers, pid, instrument, quantity=quantity, average_cost=cost)
    response = metrics(client, headers, pid)
    data = response.json()["data"]
    assert set(data) == METRIC_FIELDS and set(data["totals"]) == TOTAL_FIELDS
    assert data["valuation_status"] == "COMPLETE"
    assert data["source"] == "finex.synthetic.portfolio" and data["source_type"] == "SYNTHETIC"
    assert data["fixture_as_of"] == AS_OF and data["calculated_at"] != AS_OF
    assert data["metrics_version"] == "portfolio_metrics.v1"
    assert data["formula_version"] == "manual_portfolio_math.v1"
    assert data["catalog_version"] == "synthetic_catalog.v1"
    assert data["quote_snapshot_version"] == "synthetic_quotes.v1"
    assert data["missing_instrument_ids"] == []
    assert data["limitations"] == [
        "SYNTHETIC_QUOTES_NOT_MARKET_DATA",
        "MANUAL_HOLDINGS_NOT_BROKER_POSITIONS",
        "SPREAD_IS_ALLOCATION_ONLY",
        "NO_FUND_LOOKTHROUGH_OR_SUITABILITY",
    ]
    fields = (
        "cost_basis",
        "market_value",
        "gain_loss",
        "gain_loss_percent",
        "concentration_percent",
        "hhi",
        "educational_spread_percent",
    )
    assert tuple(data["totals"][field] for field in fields) == expected
    assert response.json()["meta"]["dataStatus"] == "CACHED"
    assert response.json()["meta"]["dataAsOf"] == AS_OF
    for holding in data["holdings"]:
        assert set(holding) == METRIC_HOLD_FIELDS
        assert set(holding["quote"]) == {"unit_price", "data_status", "quote_as_of", "reason"}
        assert holding["quote"]["data_status"] == "CACHED"
        assert holding["quote"]["quote_as_of"] == AS_OF and holding["quote"]["reason"] is None
    for field in ("allocation_by_asset_class", "allocation_by_sector"):
        groups = data["totals"][field]
        assert [item["group"] for item in groups] == sorted(item["group"] for item in groups)
        for item in groups:
            assert set(item) == {"group", "market_value", "weight_percent"}


def test_empty_zero_cost_and_missing_price_states_are_honest(client: TestClient) -> None:
    headers = completed(client)
    pid = created(client, headers)["portfolio_id"]
    empty = metrics(client, headers, pid)
    assert empty.json()["data"]["valuation_status"] == "EMPTY"
    assert empty.json()["meta"]["dataAsOf"] is None
    totals = empty.json()["data"]["totals"]
    assert totals["cost_basis"] == totals["market_value"] == totals["gain_loss"] == "0.00"
    assert totals["allocation_by_asset_class"] == totals["allocation_by_sector"] == []
    assert totals["gain_loss_percent"] is None
    priced = added(client, headers, pid, average_cost="0.0000")
    zero_cost = metrics(client, headers, pid).json()["data"]
    assert zero_cost["totals"]["gain_loss"] == "2000.00"
    assert zero_cost["totals"]["gain_loss_percent"] is None
    added(client, headers, pid, "SYN:UNAVAILABLE", average_cost="10.0000")
    partial = metrics(client, headers, pid)
    data = partial.json()["data"]
    assert data["valuation_status"] == "INCOMPLETE"
    assert partial.json()["meta"]["dataStatus"] == "UNAVAILABLE"
    assert partial.json()["meta"]["dataAsOf"] is None
    assert data["totals"]["cost_basis"] == "100.00"
    for field in TOTAL_FIELDS - {"cost_basis"}:
        assert data["totals"][field] is None
    assert data["missing_instrument_ids"] == ["SYN:UNAVAILABLE"]
    for holding in data["holdings"]:
        assert holding["weight_percent"] is None
        if holding["instrument_id"] == "SYN:AAPL":
            assert holding["market_value"] == holding["gain_loss"] == "2000.00"
            assert holding["gain_loss_percent"] is None
        else:
            assert holding["market_value"] is holding["gain_loss"] is None
            assert holding["gain_loss_percent"] is None
            assert holding["quote"] == {
                "unit_price": None,
                "data_status": "UNAVAILABLE",
                "quote_as_of": None,
                "reason": "SYNTHETIC_QUOTE_UNAVAILABLE",
            }
    assert (
        client.delete(f"{PORT}/{pid}/holdings/{priced['holding_id']}", headers=headers).status_code
        == 200
    )
    assert metrics(client, headers, pid).json()["data"]["valuation_status"] == "UNAVAILABLE"


def test_cascade_restart_and_consent_gate_preserve_owned_manual_records(tmp_path: Path) -> None:
    path = tmp_path / "durable.sqlite3"
    clock = TestClock()
    client = TestClient(application(path, clock))
    owner, other = completed(client), completed(client, "learner-b")
    first = created(client, owner)
    pid = first["portfolio_id"]
    holding = added(client, owner, pid)
    unaffected_pid = created(client, other)["portfolio_id"]
    added(client, other, unaffected_pid, "SYN:BND")
    restarted = TestClient(application(path, clock))
    assert restarted.get(f"{PORT}/{pid}", headers=owner).json()["data"] == first
    assert restarted.get(f"{PORT}/{pid}/holdings", headers=owner).json()["data"]["items"] == [
        holding
    ]
    assert (
        restarted.post(
            f"{ONBOARDING}/consent", headers=owner, json={**CONSENT, "consent_given": False}
        ).status_code
        == 200
    )
    assert_error(restarted.get(PORT, headers=owner), 409, "ONBOARDING_REQUIRED")
    assert restarted.post(f"{ONBOARDING}/consent", headers=owner, json=CONSENT).status_code == 200
    assert_error(restarted.get(PORT, headers=owner), 409, "ONBOARDING_REQUIRED")
    assert restarted.post(f"{ONBOARDING}/complete", headers=owner, json=COMPLETE).status_code == 200
    assert restarted.get(f"{PORT}/{pid}/holdings", headers=owner).json()["data"]["items"] == [
        holding
    ]
    assert restarted.delete(f"{PORT}/{pid}", headers=owner).status_code == 200
    assert_error(
        restarted.get(f"{PORT}/{pid}/holdings/{holding['holding_id']}", headers=owner),
        404,
        "LOCAL_PORTFOLIO_NOT_FOUND",
    )
    assert (
        restarted.get(f"{PORT}/{unaffected_pid}/holdings", headers=other).json()["data"]["count"]
        == 1
    )
    assert restarted.post(f"{AUTH}/logout", headers=owner, json={}).status_code == 200
    assert_error(restarted.get(PORT, headers=owner), 401, "SESSION_INVALID")


def test_openapi_mounts_twelve_operations_and_required_request_versions(client: TestClient) -> None:
    spec = client.app.openapi()
    actual = {
        (method.upper(), path[len(PORT) :])
        for path, methods in spec["paths"].items()
        if path == PORT or path.startswith(PORT + "/")
        for method in methods
    }
    expected = {
        ("GET", "/instruments"),
        ("POST", ""),
        ("GET", ""),
        ("GET", "/{portfolio_id}"),
        ("PUT", "/{portfolio_id}"),
        ("DELETE", "/{portfolio_id}"),
        ("POST", "/{portfolio_id}/holdings"),
        ("GET", "/{portfolio_id}/holdings"),
        ("GET", "/{portfolio_id}/holdings/{holding_id}"),
        ("PUT", "/{portfolio_id}/holdings/{holding_id}"),
        ("DELETE", "/{portfolio_id}/holdings/{holding_id}"),
        ("GET", "/{portfolio_id}/metrics"),
    }
    assert actual == expected
    for path, methods in spec["paths"].items():
        if path != PORT and not path.startswith(PORT + "/"):
            continue
        for operation in methods.values():
            assert operation["security"] == [{"LocalApplicationBearer": []}]
            assert {"401", "403", "409", "422", "503"} <= set(operation["responses"])
    for name, fields in (
        ("LocalPortfolioRequest", {"portfolio_version", "name", "description", "currency"}),
        (
            "LocalHoldingCreateRequest",
            {"holding_version", "instrument_id", "quantity", "average_cost", "currency"},
        ),
        ("LocalHoldingUpdateRequest", {"holding_version", "quantity", "average_cost", "currency"}),
    ):
        schema = spec["components"]["schemas"][name]
        assert schema["additionalProperties"] is False
        assert fields <= set(schema["required"])


def test_openapi_success_fields_are_exhaustive_required_and_never_invented_defaults(
    client: TestClient,
) -> None:
    schemas = client.app.openapi()["components"]["schemas"]
    expectations = {
        "LocalPortfolioCatalog": {*SCOPE, "catalog_version", "currency", "items", "count"},
        "LocalPortfolioCatalogItem": {
            "instrument_id",
            "display_name",
            "asset_class",
            "sector",
            "currency",
        },
        "LocalPortfolio": PORT_FIELDS,
        "LocalPortfolioList": {*SCOPE, "portfolio_version", "items", "count"},
        "LocalHolding": HOLD_FIELDS,
        "LocalHoldingList": {
            *SCOPE,
            "holding_version",
            "catalog_version",
            "portfolio_id",
            "items",
            "count",
        },
        "LocalPortfolioDeletion": {
            *SCOPE,
            "portfolio_version",
            "portfolio_id",
            "entity_type",
            "deleted",
        },
        "LocalHoldingDeletion": {
            *SCOPE,
            "holding_version",
            "portfolio_id",
            "holding_id",
            "entity_type",
            "deleted",
        },
        "LocalPortfolioMetrics": METRIC_FIELDS,
        "LocalPortfolioMetricHolding": METRIC_HOLD_FIELDS,
        "LocalPortfolioMetricQuote": {"unit_price", "data_status", "quote_as_of", "reason"},
        "LocalPortfolioTotals": TOTAL_FIELDS,
        "LocalPortfolioAllocation": {"group", "market_value", "weight_percent"},
    }
    for name, fields in expectations.items():
        schema = schemas[name]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == fields
        assert set(schema["required"]) == fields, f"{name} must not invent absent wire fields"
        assert all("default" not in field for field in schema["properties"].values())
