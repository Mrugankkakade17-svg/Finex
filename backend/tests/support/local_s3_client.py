"""Synthetic-only S3 HTTP test setup using accepted S1/S2 interfaces.

No prospective S3 module is imported. Credentials stay in memory and assertions
must not format a login DTO, Authorization header or database path.
"""

import re
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response
from pydantic_settings import SettingsConfigDict

from app.config.settings import AppEnv, Settings
from app.domain.local_portfolio import (
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteRecord,
    LocalPortfolioQuoteSnapshot,
)
from app.main import create_app
from app.ports.adapters.synthetic_local_portfolio import (
    SyntheticLocalPortfolioCatalog,
    SyntheticLocalPortfolioQuotes,
)

MARKET = "/api/v1/local-market"
LISTS = "/api/v1/local-watchlists"
PAPER = "/api/v1/local-paper/account"
AUTH = "/api/v1/local-auth"
ONBOARDING = "/api/v1/local-onboarding"
FOUNDATION = "market_foundation.v1"
FIXTURE_TIME = "2026-01-01T00:00:00Z"
SCOPE = {
    "scope": "local_educational_application",
    "contract_version": "local.v1",
    "foundation_version": FOUNDATION,
}
LIST_ID = "00000000-0000-4000-8000-000000000195"
OPEN = {"foundation_version": FOUNDATION, "currency": "USD"}
CONSENT = {"consent_version": "consent.v1", "consent_given": True}
PROFILE = {
    "profile_schema_version": "profile.v1",
    "display_name": "Synthetic teaching learner",
    "experience_level": "beginner",
}
COMPLETE = {"consent_version": "consent.v1", "profile_schema_version": "profile.v1"}
OPERATIONS = (
    ("GET", MARKET + "/instruments", None),
    ("GET", MARKET + "/quotes/SYN:AAPL", None),
    ("GET", LISTS, None),
    ("POST", LISTS, {"name": "Synthetic watchlist"}),
    ("GET", LISTS + "/" + LIST_ID, None),
    ("PUT", LISTS + "/" + LIST_ID, {"name": "Synthetic renamed list"}),
    ("DELETE", LISTS + "/" + LIST_ID, None),
    ("PUT", LISTS + "/" + LIST_ID + "/items/SYN:AAPL", None),
    ("DELETE", LISTS + "/" + LIST_ID + "/items/SYN:AAPL", None),
    ("GET", PAPER, None),
    ("POST", PAPER + "/open", OPEN),
    ("GET", PAPER + "/ledger", None),
)
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z")


class TestSettings(Settings):
    __test__ = False
    model_config = SettingsConfigDict(**Settings.model_config)
    model_config["env_file"] = None


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 12, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now


class ControlledCatalogue:
    def __init__(self, *, expanded: bool = False) -> None:
        self.calls = 0
        self.failed = False
        self.invalid = False
        self.expanded = expanded

    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        self.calls += 1
        if self.failed:
            raise RuntimeError("Opaque synthetic catalogue failure")
        snapshot = SyntheticLocalPortfolioCatalog().snapshot()
        if self.expanded:
            snapshot = replace(
                snapshot,
                items=tuple(
                    LocalPortfolioInstrument(
                        f"SYN:TEST{index:03d}",
                        f"Synthetic capacity example {index}",
                        "EQUITY",
                        "GENERAL",
                        "USD",
                    )
                    for index in range(1, 102)
                ),
            )
        return replace(snapshot, catalog_version="unapproved.v9") if self.invalid else snapshot


class ControlledQuotes:
    def __init__(self, *, expanded: bool = False) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.failed = False
        self.invalid = False
        self.expanded = expanded

    def snapshot(self, identifiers: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        self.calls.append(identifiers)
        if self.failed:
            raise RuntimeError("Opaque synthetic quote failure")
        snapshot = SyntheticLocalPortfolioQuotes().snapshot(() if self.expanded else identifiers)
        if self.expanded:
            snapshot = replace(
                snapshot,
                quotes=tuple(
                    LocalPortfolioQuoteRecord(identifier, "1.0000", "CACHED", FIXTURE_TIME, None)
                    for identifier in identifiers
                ),
            )
        return replace(snapshot, source_type="LIVE") if self.invalid else snapshot


def application(
    path: Path,
    clock: Clock | None = None,
    *,
    enabled: bool = True,
    environment: AppEnv = AppEnv.LOCAL,
    catalogue: ControlledCatalogue | None = None,
    quotes: ControlledQuotes | None = None,
    ttl: int = 30,
) -> FastAPI:
    return create_app(
        TestSettings(
            app_env=environment,
            debug=False,
            api_base_url="https://api.example.invalid",
            allowed_origins=["http://127.0.0.1:3000"],
            secret_key="s" * 32,
            llm_provider="none",
            local_app_enabled=enabled,
            local_db_path=path,
            local_session_ttl_minutes=ttl,
        ),
        local_clock=clock or Clock(),
        local_portfolio_catalogue=catalogue,
        local_portfolio_quotes=quotes,
    )


def data(response: Response, *, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"success", "message", "data", "meta"}
    assert body["success"] is True
    assert type(body["message"]) is str
    assert set(body["meta"]) == {"apiVersion", "dataStatus", "dataAsOf", "correlationId"}
    assert body["meta"]["apiVersion"] == "v1"
    assert body["meta"]["correlationId"] == response.headers["X-Correlation-ID"]
    result = body["data"]
    assert type(result) is dict
    scope_matches = all(result.get(key) == value for key, value in SCOPE.items())
    assert scope_matches
    for field in ("limit", "count", "item_count", "after_sequence"):
        if field in result:
            assert type(result[field]) is int
    if "watchlist_version" in result:
        assert result["watchlist_version"] == "watchlist.v1"
    if "watchlist_item_version" in result:
        assert result["watchlist_item_version"] == "watchlist_item.v1"
    return result


def error(response: Response, status: int, code: str) -> None:
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"success", "message", "error_code", "error", "detail"}
    assert body["success"] is False
    assert type(body["message"]) is str and type(body["detail"]) is str
    assert body["error_code"] == code
    assert body["error"]["code"] == code
    assert set(body["error"]) == {"code", "message", "fieldErrors", "correlationId"}
    assert type(body["error"]["message"]) is str
    assert type(body["error"]["fieldErrors"]) is list
    for field in body["error"]["fieldErrors"]:
        assert type(field) is dict and set(field) == {"field", "code"}
        assert type(field["field"]) is str and type(field["code"]) is str
    messages_match = body["message"] == body["detail"] == body["error"]["message"]
    assert messages_match
    assert body["error"]["correlationId"] == response.headers["X-Correlation-ID"]


def login(client: TestClient, alias: str = "learner-a") -> dict[str, str]:
    response = client.post(AUTH + "/mock-login", json={"alias": alias})
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["scope"] == SCOPE["scope"]
    token = result["access_token"]
    return {"Authorization": "Bearer " + token}


def finish(client: TestClient, headers: dict[str, str]) -> None:
    for method, suffix, payload in (
        ("PUT", "/draft", PROFILE),
        ("POST", "/consent", CONSENT),
        ("POST", "/complete", COMPLETE),
    ):
        response = client.request(method, ONBOARDING + suffix, headers=headers, json=payload)
        assert response.status_code == 200


def completed(client: TestClient, alias: str = "learner-a") -> dict[str, str]:
    headers = login(client, alias)
    finish(client, headers)
    return headers


def created(client: TestClient, headers: dict[str, str], name: str = "Teaching examples") -> dict:
    response = client.post(LISTS, headers=headers, json={"name": name})
    return data(response, status=201)


def opened(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(PAPER + "/open", headers=headers, json=OPEN)
    return data(response)


def utc(value: object) -> datetime:
    if not isinstance(value, str) or _UTC.fullmatch(value) is None:
        raise AssertionError("A canonical UTC timestamp is required")
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() != timedelta(0):
        raise AssertionError("A UTC instant is required")
    return parsed


def uuid4(value: object) -> None:
    if not isinstance(value, str):
        raise AssertionError("A canonical UUID4 is required")
    try:
        parsed = UUID(value)
    except ValueError:
        raise AssertionError("A canonical UUID4 is required") from None
    if parsed.version != 4 or str(parsed) != value:
        raise AssertionError("A canonical UUID4 is required")
