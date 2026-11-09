"""Test-first S3 HTTP contract, not native TCP or S4 execution acceptance."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.support.local_s3_client import (
    AUTH,
    COMPLETE,
    CONSENT,
    FIXTURE_TIME,
    LIST_ID,
    LISTS,
    MARKET,
    ONBOARDING,
    OPEN,
    OPERATIONS,
    PAPER,
    SCOPE,
    Clock,
    ControlledCatalogue,
    ControlledQuotes,
    application,
    completed,
    created,
    data,
    error,
    login,
    opened,
    utc,
    uuid4,
)

INSTRUMENT_FIELDS = {"instrument_id", "display_name", "asset_class", "sector", "currency"}
SUMMARY_FIELDS = {"watchlist_id", "name", "created_at", "updated_at", "item_count"}
WATCHLIST_FIELDS = {*SCOPE, "watchlist_version", *SUMMARY_FIELDS, "items"}
QUOTE_FIELDS = {
    *SCOPE,
    "catalog_version",
    "quote_snapshot_version",
    "source",
    "source_type",
    "fixture_as_of",
    "instrument_id",
    "currency",
    "status",
    "unit_price",
    "quote_as_of",
    "fetched_at",
    "cache_expires_at",
    "reason",
}
ACCOUNT_FIELDS = {
    "account_id",
    "opening_ledger_id",
    "currency",
    "opening_cash",
    "cash_balance",
    "created_at",
}
LEDGER_FIELDS = {
    "ledger_id",
    "account_id",
    "sequence",
    "entry_type",
    "cash_delta",
    "cash_after",
    "instrument_id",
    "quantity_delta",
    "position_after",
    "order_id",
    "trade_id",
    "corrects_ledger_id",
    "created_at",
}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(application(tmp_path / "s3-http.sqlite3"))


@pytest.mark.parametrize("method,path,payload", OPERATIONS)
def test_each_s3_operation_requires_local_bearer_before_storage(
    tmp_path: Path, method: str, path: str, payload: dict | None
) -> None:
    database = tmp_path / "denied.sqlite3"
    catalogue, quotes = ControlledCatalogue(), ControlledQuotes()
    response = TestClient(application(database, catalogue=catalogue, quotes=quotes)).request(
        method, path, json=payload
    )
    error(response, 401, "SESSION_INVALID")
    assert not database.exists()
    assert catalogue.calls == 0 and quotes.calls == []


@pytest.mark.parametrize("method,path,payload", OPERATIONS)
def test_each_s3_operation_requires_current_completed_onboarding(
    tmp_path: Path, method: str, path: str, payload: dict | None
) -> None:
    catalogue, quotes = ControlledCatalogue(), ControlledQuotes()
    client = TestClient(
        application(tmp_path / "incomplete.sqlite3", catalogue=catalogue, quotes=quotes)
    )
    headers = login(client)
    response = client.request(method, path, json=payload, headers=headers)
    error(response, 409, "ONBOARDING_REQUIRED")
    assert catalogue.calls == 0 and quotes.calls == []


def test_search_supported_defaults_normalization_order_and_empty_states(client: TestClient) -> None:
    headers = completed(client)
    response = client.get(MARKET + "/instruments", headers=headers)
    result = data(response)
    assert set(result) == {*SCOPE, "catalog_version", "query", "limit", "count", "items"}
    assert result["catalog_version"] == "synthetic_catalog.v1"
    assert result["query"] == "" and result["limit"] == 20 and result["count"] == 4
    assert [item["instrument_id"] for item in result["items"]] == [
        "SYN:AAPL",
        "SYN:BND",
        "SYN:MSFT",
        "SYN:UNAVAILABLE",
    ]
    assert all(set(item) == INSTRUMENT_FIELDS for item in result["items"])
    assert all(item["currency"] == "USD" for item in result["items"])
    assert response.json()["meta"]["dataStatus"] == "CACHED"
    assert response.json()["meta"]["dataAsOf"] == FIXTURE_TIME
    filtered = data(
        client.get(MARKET + "/instruments?query=%20MiCroSoft%20&limit=1", headers=headers)
    )
    assert filtered["query"] == "MiCroSoft" and filtered["limit"] == filtered["count"] == 1
    assert filtered["items"][0]["instrument_id"] == "SYN:MSFT"
    empty = data(client.get(MARKET + "/instruments?query=unsupported-text", headers=headers))
    assert empty["items"] == [] and empty["count"] == 0


@pytest.mark.parametrize(
    "query",
    [
        "?limit=0",
        "?limit=21",
        "?limit=1.0",
        "?limit=true",
        "?limit=-1",
        "?limit=1&limit=2",
        "?query=a&query=b",
        "?owner_id=learner-b",
        "?currency=USD",
        "?source=LIVE",
        "?query=" + "x" * 81,
        "?query=a%01b",
    ],
)
def test_search_rejects_ambiguous_and_unapproved_controls_before_provider(
    tmp_path: Path, query: str
) -> None:
    catalogue = ControlledCatalogue()
    client = TestClient(application(tmp_path / "query.sqlite3", catalogue=catalogue))
    headers = completed(client)
    response = client.get(MARKET + "/instruments" + query, headers=headers)
    error(response, 422, "VALIDATION_ERROR")
    assert catalogue.calls == 0


@pytest.mark.parametrize("identifier", ["SYN:aapl", "AAPL", "SYN:AAPL%0A", "SYN:"])
def test_noncanonical_quote_identifier_is_validation_error(
    client: TestClient, identifier: str
) -> None:
    headers = completed(client)
    response = client.get(MARKET + "/quotes/" + identifier, headers=headers)
    error(response, 422, "VALIDATION_ERROR")


@pytest.mark.parametrize("identifier", ["SYN:OTHER", "SYN:TEST001", "SYN:TEST101"])
def test_default_unsupported_identifier_has_no_provider_or_invented_quote(
    tmp_path: Path, identifier: str
) -> None:
    quotes = ControlledQuotes()
    client = TestClient(application(tmp_path / "unsupported.sqlite3", quotes=quotes))
    headers = completed(client)
    response = client.get(MARKET + "/quotes/" + identifier, headers=headers)
    error(response, 404, "INSTRUMENT_NOT_FOUND")
    assert quotes.calls == []


@pytest.mark.parametrize(
    "identifier,price", [("SYN:AAPL", "200.0000"), ("SYN:BND", "80.0000"), ("SYN:MSFT", "400.0000")]
)
def test_quote_exact_fixed_values_source_and_retrieval_are_distinct(
    tmp_path: Path, identifier: str, price: str
) -> None:
    clock = Clock()
    client = TestClient(application(tmp_path / "priced.sqlite3", clock))
    headers = completed(client)
    response = client.get(MARKET + "/quotes/" + identifier, headers=headers)
    result = data(response)
    assert set(result) == QUOTE_FIELDS
    assert result["catalog_version"] == "synthetic_catalog.v1"
    assert result["quote_snapshot_version"] == "synthetic_quotes.v1"
    assert result["source"] == "finex.synthetic.portfolio" and result["source_type"] == "SYNTHETIC"
    assert result["fixture_as_of"] == result["quote_as_of"] == FIXTURE_TIME
    assert result["instrument_id"] == identifier and result["currency"] == "USD"
    assert result["status"] == "CACHED" and result["reason"] is None
    assert result["unit_price"] == price
    assert utc(result["fetched_at"]) == clock.now
    assert utc(result["cache_expires_at"]) == clock.now + timedelta(seconds=60)
    assert response.json()["meta"]["dataStatus"] == "CACHED"
    assert response.json()["meta"]["dataAsOf"] == FIXTURE_TIME


def test_supported_unavailable_fixture_has_null_price_and_truthful_success_metadata(
    client: TestClient,
) -> None:
    headers = completed(client)
    response = client.get(MARKET + "/quotes/SYN:UNAVAILABLE", headers=headers)
    result = data(response)
    assert set(result) == QUOTE_FIELDS
    assert result["status"] == "UNAVAILABLE" and result["unit_price"] is None
    assert result["quote_as_of"] is None and result["fixture_as_of"] == FIXTURE_TIME
    assert result["reason"] == "SYNTHETIC_QUOTE_UNAVAILABLE"
    assert utc(result["cache_expires_at"]) - utc(result["fetched_at"]) == timedelta(seconds=60)
    assert response.json()["meta"]["dataStatus"] == "UNAVAILABLE"
    assert response.json()["meta"]["dataAsOf"] is None


def test_watchlist_crud_items_noops_order_and_metadata(tmp_path: Path) -> None:
    clock = Clock()
    client = TestClient(application(tmp_path / "watchlist.sqlite3", clock))
    headers = completed(client)
    empty_response = client.get(LISTS, headers=headers)
    empty = data(empty_response)
    assert empty == {
        **SCOPE,
        "watchlist_version": "watchlist.v1",
        "limit": 10,
        "count": 0,
        "items": [],
    }
    assert empty_response.json()["meta"]["dataAsOf"] is None
    first = created(client, headers, "  Teaching examples  ")
    assert set(first) == WATCHLIST_FIELDS
    uuid4(first["watchlist_id"])
    assert (
        first["name"] == "Teaching examples" and first["items"] == [] and first["item_count"] == 0
    )
    assert utc(first["created_at"]) == utc(first["updated_at"]) == clock.now
    path = LISTS + "/" + first["watchlist_id"]
    clock.now += timedelta(seconds=1)
    renamed_response = client.put(path, headers=headers, json={"name": "  Revised examples "})
    renamed = data(renamed_response)
    assert renamed["name"] == "Revised examples"
    assert utc(renamed["updated_at"]) == clock.now
    assert renamed["created_at"] == first["created_at"]
    assert utc(renamed_response.json()["meta"]["dataAsOf"]) == clock.now
    clock.now += timedelta(seconds=1)
    assert data(client.put(path, headers=headers, json={"name": "Revised examples"})) == renamed
    item_path = path + "/items/SYN:AAPL"
    added_response = client.put(item_path, headers=headers, json={})
    added = data(added_response)
    assert set(added) == {
        *SCOPE,
        "watchlist_version",
        "watchlist_item_version",
        "watchlist_id",
        "item",
    }
    assert added["watchlist_item_version"] == "watchlist_item.v1"
    assert set(added["item"]) == {*INSTRUMENT_FIELDS, "added_at"}
    assert added["item"]["display_name"] == "Synthetic Apple example"
    assert utc(added["item"]["added_at"]) == clock.now
    full = data(client.get(path, headers=headers))
    assert full["items"] == [added["item"]] and full["item_count"] == 1
    assert utc(full["updated_at"]) == clock.now
    clock.now += timedelta(seconds=1)
    assert data(client.put(item_path, headers=headers)) == added
    assert data(client.get(path, headers=headers)) == full
    removed = data(client.delete(item_path, headers=headers))
    assert removed == {
        **SCOPE,
        "watchlist_version": "watchlist.v1",
        "watchlist_item_version": "watchlist_item.v1",
        "watchlist_id": first["watchlist_id"],
        "instrument_id": "SYN:AAPL",
        "removed": True,
    }
    after_remove = data(client.get(path, headers=headers))
    assert after_remove["item_count"] == 0 and after_remove["items"] == []
    clock.now += timedelta(seconds=1)
    assert data(client.request("DELETE", item_path, headers=headers, json={})) == removed
    assert data(client.get(path, headers=headers)) == after_remove
    deleted = data(client.delete(path, headers=headers))
    assert deleted == {
        **SCOPE,
        "watchlist_version": "watchlist.v1",
        "watchlist_id": first["watchlist_id"],
        "deleted": True,
    }
    error(client.get(path, headers=headers), 404, "WATCHLIST_NOT_FOUND")
    error(client.delete(path, headers=headers), 404, "WATCHLIST_NOT_FOUND")


def test_watchlist_collection_creation_order_and_item_time_tiebreak_are_deterministic(
    client: TestClient,
) -> None:
    headers = completed(client)
    one, two = created(client, headers, "One"), created(client, headers, "Two")
    collection = data(client.get(LISTS, headers=headers))
    assert [item["watchlist_id"] for item in collection["items"]] == sorted(
        [one["watchlist_id"], two["watchlist_id"]]
    )
    assert all(set(item) == SUMMARY_FIELDS for item in collection["items"])
    path = LISTS + "/" + one["watchlist_id"]
    for identifier in ("SYN:MSFT", "SYN:AAPL", "SYN:BND"):
        data(client.put(path + "/items/" + identifier, headers=headers))
    full = data(client.get(path, headers=headers))
    assert [item["instrument_id"] for item in full["items"]] == ["SYN:AAPL", "SYN:BND", "SYN:MSFT"]


@pytest.mark.parametrize("name", [None, True, 3, "", "   ", "x" * 101])
@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_watchlist_name_strict_validation_never_confirms_write(
    client: TestClient, name: object, method: str
) -> None:
    headers = completed(client)
    path = LISTS if method == "POST" else LISTS + "/" + LIST_ID
    response = client.request(method, path, headers=headers, json={"name": name})
    error(response, 422, "VALIDATION_ERROR")


def test_watchlist_owner_selection_and_missing_name_are_forbidden(client: TestClient) -> None:
    headers = completed(client)
    for payload in (
        {},
        {"name": "Synthetic", "owner_id": "learner-b"},
        {"name": "Synthetic", "currency": "USD"},
    ):
        response = client.post(LISTS, headers=headers, json=payload)
        error(response, 422, "VALIDATION_ERROR")


def test_watchlist_ten_capacity_and_unicode_trimmed_boundary_are_saved_once(
    client: TestClient,
) -> None:
    headers = completed(client)
    accepted = created(client, headers, "  " + "é" * 100 + "  ")
    assert accepted["name"] == "é" * 100
    for index in range(9):
        created(client, headers, f"Teaching {index}")
    response = client.post(LISTS, headers=headers, json={"name": "Eleventh"})
    error(response, 409, "WATCHLIST_LIMIT")
    assert data(client.get(LISTS, headers=headers))["count"] == 10


def test_expanded_trusted_catalogue_proves_hundred_items_and_duplicate_at_capacity(
    tmp_path: Path,
) -> None:
    catalogue, quotes = ControlledCatalogue(expanded=True), ControlledQuotes(expanded=True)
    client = TestClient(
        application(tmp_path / "item-capacity.sqlite3", catalogue=catalogue, quotes=quotes)
    )
    headers = completed(client)
    watchlist = created(client, headers)
    path = LISTS + "/" + watchlist["watchlist_id"]
    first = None
    for index in range(1, 101):
        saved = data(client.put(path + f"/items/SYN:TEST{index:03d}", headers=headers))
        if index == 1:
            first = saved
    assert data(client.get(path, headers=headers))["item_count"] == 100
    assert data(client.put(path + "/items/SYN:TEST001", headers=headers)) == first
    error(client.put(path + "/items/SYN:TEST101", headers=headers), 409, "WATCHLIST_ITEM_LIMIT")
    assert data(client.get(path, headers=headers))["item_count"] == 100


@pytest.mark.parametrize(
    "identifier",
    ["A0000000-0000-4000-8000-000000000195", "not-an-id", "00000000-0000-1000-8000-000000000195"],
)
def test_watchlist_identifiers_must_be_canonical_uuid4(client: TestClient, identifier: str) -> None:
    headers = completed(client)
    response = client.get(LISTS + "/" + identifier, headers=headers)
    error(response, 422, "VALIDATION_ERROR")


def test_two_persona_non_disclosure_and_supported_item_owner_predicates(client: TestClient) -> None:
    owner, other = completed(client), completed(client, "learner-b")
    first, second = created(client, owner), created(client, other)
    path = LISTS + "/" + first["watchlist_id"]
    for method, suffix, payload in (
        ("GET", "", None),
        ("PUT", "", {"name": "Not owned"}),
        ("DELETE", "", None),
        ("PUT", "/items/SYN:AAPL", None),
        ("DELETE", "/items/SYN:AAPL", None),
    ):
        error(
            client.request(method, path + suffix, headers=other, json=payload),
            404,
            "WATCHLIST_NOT_FOUND",
        )
    collection = data(client.get(LISTS, headers=other))
    assert (
        collection["count"] == 1
        and collection["items"][0]["watchlist_id"] == second["watchlist_id"]
    )
    first_survives = data(client.get(path, headers=owner))
    assert first_survives["items"] == []


def test_account_get_is_null_and_ledger_requires_explicit_open(client: TestClient) -> None:
    headers = completed(client)
    response = client.get(PAPER, headers=headers)
    assert data(response) == {
        **SCOPE,
        "paper_account_version": "paper_account.v1",
        "simulation": True,
        "account": None,
    }
    assert response.json()["meta"]["dataAsOf"] is None
    error(client.get(PAPER + "/ledger", headers=headers), 404, "PAPER_ACCOUNT_NOT_OPEN")


def test_opened_account_exact_cents_and_single_immutable_opening_ledger(tmp_path: Path) -> None:
    clock = Clock()
    client = TestClient(application(tmp_path / "paper.sqlite3", clock))
    headers = completed(client)
    response = client.post(PAPER + "/open", headers=headers, json=OPEN)
    result = data(response)
    assert set(result) == {*SCOPE, "paper_account_version", "simulation", "account"}
    assert result["simulation"] is True and result["paper_account_version"] == "paper_account.v1"
    account = result["account"]
    assert set(account) == ACCOUNT_FIELDS
    uuid4(account["account_id"])
    uuid4(account["opening_ledger_id"])
    assert (
        account["currency"] == "USD"
        and account["opening_cash"] == account["cash_balance"] == "10000.00"
    )
    assert utc(account["created_at"]) == utc(response.json()["meta"]["dataAsOf"]) == clock.now
    clock.now += timedelta(seconds=30)
    assert opened(client, headers) == result
    assert data(client.get(PAPER, headers=headers)) == result
    ledger_response = client.get(PAPER + "/ledger", headers=headers)
    ledger = data(ledger_response)
    assert set(ledger) == {
        *SCOPE,
        "paper_ledger_version",
        "simulation",
        "account_id",
        "limit",
        "after_sequence",
        "count",
        "items",
        "next_cursor",
    }
    assert ledger["paper_ledger_version"] == "paper_ledger.v1" and ledger["simulation"] is True
    assert ledger["account_id"] == account["account_id"]
    assert ledger["limit"] == 100 and ledger["after_sequence"] == 0
    assert ledger["count"] == 1 and ledger["next_cursor"] is None
    entry = ledger["items"][0]
    assert set(entry) == LEDGER_FIELDS
    assert (
        entry["ledger_id"] == account["opening_ledger_id"]
        and entry["account_id"] == account["account_id"]
    )
    assert type(entry["sequence"]) is int and 1 <= entry["sequence"] <= 9007199254740991
    assert (
        entry["entry_type"] == "OPENING"
        and entry["cash_delta"] == entry["cash_after"] == "10000.00"
    )
    assert all(
        entry[field] is None
        for field in (
            "instrument_id",
            "quantity_delta",
            "position_after",
            "order_id",
            "trade_id",
            "corrects_ledger_id",
        )
    )
    assert entry["created_at"] == account["created_at"]
    assert utc(ledger_response.json()["meta"]["dataAsOf"]) == utc(entry["created_at"])
    after = data(
        client.get(PAPER + f"/ledger?after_sequence={entry['sequence']}&limit=1", headers=headers)
    )
    assert after["items"] == [] and after["count"] == 0 and after["next_cursor"] is None
    assert after["after_sequence"] == entry["sequence"] and after["limit"] == 1


@pytest.mark.parametrize(
    "query",
    [
        "?limit=0",
        "?limit=101",
        "?limit=1.0",
        "?limit=true",
        "?limit=1&limit=2",
        "?after_sequence=-1",
        "?after_sequence=1.0",
        "?after_sequence=true",
        "?after_sequence=9007199254740992",
        "?after_sequence=0&after_sequence=1",
        "?owner_id=learner-b",
    ],
)
def test_ledger_controls_reject_bounds_and_duplicate_authority(
    client: TestClient, query: str
) -> None:
    headers = completed(client)
    response = client.get(PAPER + "/ledger" + query, headers=headers)
    error(response, 422, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "payload,code,status",
    [
        (
            {"foundation_version": "market_foundation.v2", "currency": "USD"},
            "MARKET_FOUNDATION_VERSION_MISMATCH",
            409,
        ),
        (
            {"foundation_version": "market_foundation.v1", "currency": "INR"},
            "VALIDATION_ERROR",
            422,
        ),
        ({"currency": "USD"}, "VALIDATION_ERROR", 422),
        ({"foundation_version": "market_foundation.v1"}, "VALIDATION_ERROR", 422),
        ({**OPEN, "owner_id": "learner-b"}, "VALIDATION_ERROR", 422),
        ({**OPEN, "opening_cash": "10000.00"}, "VALIDATION_ERROR", 422),
        ({**OPEN, "funding_amount": 10000.0}, "VALIDATION_ERROR", 422),
        ({**OPEN, "broker_credential": "synthetic-forbidden"}, "VALIDATION_ERROR", 422),
        ({"foundation_version": True, "currency": "USD"}, "VALIDATION_ERROR", 422),
    ],
)
def test_open_rejects_versions_types_funding_and_owner_inputs(
    client: TestClient, payload: dict, code: str, status: int
) -> None:
    headers = completed(client)
    response = client.post(PAPER + "/open", headers=headers, json=payload)
    error(response, status, code)
    assert data(client.get(PAPER, headers=headers))["account"] is None


def test_restart_withdrawal_recompletion_logout_and_owner_preserve_account_and_lists(
    tmp_path: Path,
) -> None:
    path, clock = tmp_path / "restart.sqlite3", Clock()
    first = TestClient(application(path, clock))
    owner, other = completed(first), completed(first, "learner-b")
    watchlist = created(first, owner)
    list_path = LISTS + "/" + watchlist["watchlist_id"]
    added = data(first.put(list_path + "/items/SYN:UNAVAILABLE", headers=owner))
    account = opened(first, owner)
    restarted = TestClient(application(path, clock))
    assert data(restarted.get(PAPER, headers=owner)) == account
    assert data(restarted.get(PAPER, headers=other))["account"] is None
    assert data(restarted.get(LISTS, headers=other))["items"] == []
    assert data(restarted.get(list_path, headers=owner))["items"] == [added["item"]]
    withdrawal = restarted.post(
        ONBOARDING + "/consent", headers=owner, json={**CONSENT, "consent_given": False}
    )
    assert withdrawal.status_code == 200
    error(restarted.get(list_path, headers=owner), 409, "ONBOARDING_REQUIRED")
    error(restarted.post(PAPER + "/open", headers=owner, json=OPEN), 409, "ONBOARDING_REQUIRED")
    accept = restarted.post(ONBOARDING + "/consent", headers=owner, json=CONSENT)
    assert accept.status_code == 200
    error(restarted.get(PAPER, headers=owner), 409, "ONBOARDING_REQUIRED")
    recomplete = restarted.post(ONBOARDING + "/complete", headers=owner, json=COMPLETE)
    assert recomplete.status_code == 200
    assert data(restarted.get(PAPER, headers=owner)) == account
    data(restarted.delete(list_path, headers=owner))
    assert data(restarted.get(PAPER, headers=owner)) == account
    assert data(restarted.get(PAPER + "/ledger", headers=owner))["count"] == 1
    logout = restarted.post(AUTH + "/logout", headers=owner, json={})
    assert logout.status_code == 200
    error(restarted.get(PAPER, headers=owner), 401, "SESSION_INVALID")
    fresh = completed(restarted)
    assert data(restarted.get(PAPER, headers=fresh)) == account


def test_expired_session_denies_every_s3_operation_without_new_state(tmp_path: Path) -> None:
    clock = Clock()
    client = TestClient(application(tmp_path / "expiry.sqlite3", clock, ttl=1))
    headers = completed(client)
    clock.now += timedelta(seconds=60)
    for method, path, payload in OPERATIONS:
        response = client.request(method, path, headers=headers, json=payload)
        error(response, 401, "SESSION_INVALID")


def test_openapi_exact_twelve_routes_security_and_no_s4_order_mount(client: TestClient) -> None:
    specification = client.app.openapi()
    actual = {
        (method.upper(), path)
        for path, methods in specification["paths"].items()
        if path.startswith((MARKET + "/", LISTS, PAPER))
        for method in methods
    }
    expected = {
        ("GET", MARKET + "/instruments"),
        ("GET", MARKET + "/quotes/{instrument_id}"),
        ("GET", LISTS),
        ("POST", LISTS),
        ("GET", LISTS + "/{watchlist_id}"),
        ("PUT", LISTS + "/{watchlist_id}"),
        ("DELETE", LISTS + "/{watchlist_id}"),
        ("PUT", LISTS + "/{watchlist_id}/items/{instrument_id}"),
        ("DELETE", LISTS + "/{watchlist_id}/items/{instrument_id}"),
        ("GET", PAPER),
        ("POST", PAPER + "/open"),
        ("GET", PAPER + "/ledger"),
    }
    assert actual == expected
    assert not any("/local-paper/orders" in path for path in specification["paths"])
    for method, path in expected:
        operation = specification["paths"][path][method.lower()]
        assert operation["security"] == [{"LocalApplicationBearer": []}]
        assert {"401", "403", "409", "422", "503"} <= set(operation["responses"])
