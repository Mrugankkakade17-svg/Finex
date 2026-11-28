"""Contract tests for the production Watchlist API (/api/v1/watchlists)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.principal import Principal, get_current_principal
from app.main import create_app
from app.repositories.watchlist_repository import WatchlistRepository
from app.services.watchlist_service import WatchlistService


@pytest.fixture
def watchlist_client(tmp_path):
    application = create_app()
    repo = WatchlistRepository(tmp_path / "test-watchlists.sqlite3")
    service = WatchlistService(repo)

    from app.routers import watchlists

    orig_service = watchlists.watchlist_service
    watchlists.watchlist_service = service

    client = TestClient(application)
    try:
        yield client, application, service
    finally:
        watchlists.watchlist_service = orig_service
        application.dependency_overrides.clear()


def test_watchlist_endpoints_require_authentication(watchlist_client) -> None:
    client, _, _ = watchlist_client
    # Unauthenticated requests return 401
    assert client.get("/api/v1/watchlists").status_code == 401
    assert client.post("/api/v1/watchlists", json={"name": "Tech"}).status_code == 401
    assert client.get("/api/v1/watchlists/some-id").status_code == 401
    assert client.put("/api/v1/watchlists/some-id", json={"name": "New"}).status_code == 401
    assert client.delete("/api/v1/watchlists/some-id").status_code == 401
    assert (
        client.post("/api/v1/watchlists/some-id/items", json={"instrument_id": "AAPL"}).status_code
        == 401
    )
    assert client.get("/api/v1/watchlists/some-id/items").status_code == 401
    assert client.delete("/api/v1/watchlists/some-id/items/AAPL").status_code == 401


def test_watchlist_full_crud_and_item_lifecycle(watchlist_client) -> None:
    client, app, _ = watchlist_client
    app.dependency_overrides[get_current_principal] = lambda: Principal(
        user_id="user-owner-1",
        is_synthetic=False,
    )

    # 1. Create watchlist
    create_res = client.post("/api/v1/watchlists", json={"name": "Growth Stocks"})
    assert create_res.status_code == 201
    body = create_res.json()
    assert body["success"] is True
    watchlist_id = body["data"]["watchlist_id"]
    assert body["data"]["name"] == "Growth Stocks"
    assert body["data"]["item_count"] == 0

    # 2. List watchlists
    list_res = client.get("/api/v1/watchlists")
    assert list_res.status_code == 200
    list_body = list_res.json()
    assert list_body["data"]["count"] == 1
    assert list_body["data"]["items"][0]["watchlist_id"] == watchlist_id

    # 3. Get individual watchlist
    get_res = client.get(f"/api/v1/watchlists/{watchlist_id}")
    assert get_res.status_code == 200
    assert get_res.json()["data"]["name"] == "Growth Stocks"
    assert get_res.json()["data"]["items"] == []

    # 4. Add items (via POST and idempotent PUT)
    add_res1 = client.post(
        f"/api/v1/watchlists/{watchlist_id}/items",
        json={"instrument_id": "AAPL"},
    )
    assert add_res1.status_code == 201
    assert add_res1.json()["data"]["instrument_id"] == "AAPL"

    # Add second item via PUT
    add_res2 = client.put(f"/api/v1/watchlists/{watchlist_id}/items/MSFT")
    assert add_res2.status_code == 200
    assert add_res2.json()["data"]["instrument_id"] == "MSFT"

    # Adding duplicate item is idempotent
    add_dup = client.post(
        f"/api/v1/watchlists/{watchlist_id}/items",
        json={"instrument_id": "AAPL"},
    )
    assert add_dup.status_code in (200, 201)

    # 5. List items
    items_res = client.get(f"/api/v1/watchlists/{watchlist_id}/items")
    assert items_res.status_code == 200
    items_data = items_res.json()["data"]
    assert items_data["count"] == 2
    symbols = [it["instrument_id"] for it in items_data["items"]]
    assert "AAPL" in symbols and "MSFT" in symbols

    # 6. Verify item count in watchlist
    w_res = client.get(f"/api/v1/watchlists/{watchlist_id}")
    assert w_res.json()["data"]["item_count"] == 2

    # 7. Update watchlist name
    update_res = client.put(
        f"/api/v1/watchlists/{watchlist_id}",
        json={"name": "Big Tech Growth"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["name"] == "Big Tech Growth"

    # 8. Remove an item
    del_item_res = client.delete(f"/api/v1/watchlists/{watchlist_id}/items/AAPL")
    assert del_item_res.status_code == 200

    # Verify 1 item remains
    items_after = client.get(f"/api/v1/watchlists/{watchlist_id}/items").json()["data"]
    assert items_after["count"] == 1
    assert items_after["items"][0]["instrument_id"] == "MSFT"

    # 9. Delete watchlist
    del_w_res = client.delete(f"/api/v1/watchlists/{watchlist_id}")
    assert del_w_res.status_code == 200

    # 10. Verify 404 after deletion
    assert client.get(f"/api/v1/watchlists/{watchlist_id}").status_code == 404
    assert client.get("/api/v1/watchlists").json()["data"]["count"] == 0


def test_cross_user_isolation(watchlist_client) -> None:
    client, app, _ = watchlist_client

    # User A creates a watchlist
    app.dependency_overrides[get_current_principal] = lambda: Principal(user_id="user-alice")
    created = client.post("/api/v1/watchlists", json={"name": "Alice Watchlist"}).json()
    alice_watchlist_id = created["data"]["watchlist_id"]
    client.post(
        f"/api/v1/watchlists/{alice_watchlist_id}/items",
        json={"instrument_id": "RELIANCE"},
    )

    # Switch to User B
    app.dependency_overrides[get_current_principal] = lambda: Principal(user_id="user-bob")

    # User B listing should be empty
    bob_lists = client.get("/api/v1/watchlists").json()["data"]
    assert bob_lists["count"] == 0
    assert bob_lists["items"] == []

    # User B attempting to read Alice's watchlist receives 404
    assert client.get(f"/api/v1/watchlists/{alice_watchlist_id}").status_code == 404

    # User B attempting to update Alice's watchlist receives 404
    assert (
        client.put(
            f"/api/v1/watchlists/{alice_watchlist_id}",
            json={"name": "Hacked Name"},
        ).status_code
        == 404
    )

    # User B attempting to add item to Alice's watchlist receives 404
    assert (
        client.post(
            f"/api/v1/watchlists/{alice_watchlist_id}/items",
            json={"instrument_id": "TCS"},
        ).status_code
        == 404
    )

    # User B attempting to list items of Alice's watchlist receives 404
    assert client.get(f"/api/v1/watchlists/{alice_watchlist_id}/items").status_code == 404

    # User B attempting to delete Alice's watchlist receives 404
    assert client.delete(f"/api/v1/watchlists/{alice_watchlist_id}").status_code == 404

    # Switch back to Alice and confirm her watchlist remains intact
    app.dependency_overrides[get_current_principal] = lambda: Principal(user_id="user-alice")
    alice_check = client.get(f"/api/v1/watchlists/{alice_watchlist_id}").json()["data"]
    assert alice_check["name"] == "Alice Watchlist"
    assert alice_check["item_count"] == 1


def test_watchlist_input_validation(watchlist_client) -> None:
    client, app, _ = watchlist_client
    app.dependency_overrides[get_current_principal] = lambda: Principal(user_id="user-valid")

    # Empty name fails validation (422)
    assert client.post("/api/v1/watchlists", json={"name": ""}).status_code == 422
    assert client.post("/api/v1/watchlists", json={"name": "   "}).status_code == 422

    # Extra fields forbidden (422)
    assert (
        client.post("/api/v1/watchlists", json={"name": "Valid", "extra": "forbidden"}).status_code
        == 422
    )

    # Valid list created
    w_id = client.post("/api/v1/watchlists", json={"name": "Valid List"}).json()["data"][
        "watchlist_id"
    ]

    # Empty item symbol fails (422)
    assert (
        client.post(f"/api/v1/watchlists/{w_id}/items", json={"instrument_id": ""}).status_code
        == 422
    )
    assert (
        client.post(f"/api/v1/watchlists/{w_id}/items", json={"instrument_id": "   "}).status_code
        == 422
    )
