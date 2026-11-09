"""Fail-closed three-store DI and transport guards for manual portfolios."""

from contextlib import contextmanager
from inspect import signature
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config.settings import Settings
from app.domain.local_application import LocalStoreUnavailable
from app.main import create_app
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore
from tests.contract.test_local_s1_api import assert_error, login
from tests.contract.test_local_s2_portfolio_api import OPERATIONS, PORT, request_body

FORMATTED_CREDENTIAL = {"Authorization": "Bearer " + "a" * 43}


class ClosedFalseyStore:
    def __init__(self) -> None:
        self.calls = 0

    def __bool__(self) -> bool:
        return False

    @contextmanager
    def transaction(self, *, write: bool = False):
        self.calls += 1
        raise LocalStoreUnavailable("private synthetic storage failure; must not be returned")
        yield  # pragma: no cover - a context manager that deliberately cannot enter


def settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        local_app_enabled=True,
        local_db_path=path,
        llm_provider="none",
        market_data_provider="mock",
    )


def test_factory_has_explicit_portfolio_and_snapshot_ports_not_runtime_guessing() -> None:
    parameters = signature(create_app).parameters
    assert {"local_portfolio_store", "local_portfolio_catalogue", "local_portfolio_quotes"} <= set(
        parameters
    )
    assert all(
        parameters[name].default is None
        for name in ("local_portfolio_store", "local_portfolio_catalogue", "local_portfolio_quotes")
    )


@pytest.mark.parametrize("counterpart", ["local_store", "local_risk_store"])
def test_missing_portfolio_counterpart_never_opens_unrelated_fallback_database(
    tmp_path: Path, counterpart: str
) -> None:
    path = tmp_path / "unrelated.sqlite3"
    client = TestClient(create_app(settings(path), **{counterpart: ClosedFalseyStore()}))
    assert_error(client.get(PORT, headers=FORMATTED_CREDENTIAL), 503, "LOCAL_STORE_UNAVAILABLE")
    assert not path.exists()


def test_falsey_portfolio_injection_is_used_without_default_storage(tmp_path: Path) -> None:
    path = tmp_path / "unrelated.sqlite3"
    store = ClosedFalseyStore()
    client = TestClient(create_app(settings(path), local_portfolio_store=store))
    response = client.get(PORT, headers=FORMATTED_CREDENTIAL)
    assert_error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    assert store.calls == 1 and not path.exists()
    assert "private synthetic" not in response.text


@pytest.mark.parametrize("operation", ["signin", "risk"])
def test_portfolio_only_injection_prevents_missing_s1_and_risk_fallbacks(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "unrelated.sqlite3"
    client = TestClient(create_app(settings(path), local_portfolio_store=ClosedFalseyStore()))
    response = (
        client.post("/api/v1/local-auth/mock-login", json={"alias": "learner-a"})
        if operation == "signin"
        else client.get("/api/v1/local-risk/questionnaire", headers=FORMATTED_CREDENTIAL)
    )
    assert_error(response, 503, "LOCAL_STORE_UNAVAILABLE")
    assert not path.exists()


def test_explicit_s1_and_risk_remain_usable_when_portfolio_counterpart_is_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "owned.sqlite3"
    client = TestClient(
        create_app(
            settings(path),
            local_store=SQLiteLocalApplicationStore(path),
            local_risk_store=SQLiteLocalRiskStore(path),
        )
    )
    headers = login(client)
    assert client.get("/api/v1/local-auth/me", headers=headers).status_code == 200
    # Existing risk behavior remains its established completion gate, not a DI fault.
    assert_error(
        client.get("/api/v1/local-risk/questionnaire", headers=headers), 409, "ONBOARDING_REQUIRED"
    )
    assert_error(client.get(PORT, headers=headers), 503, "LOCAL_STORE_UNAVAILABLE")


@pytest.mark.parametrize("method,suffix", OPERATIONS)
@pytest.mark.parametrize("credential", ["Bearer malformed", "Basic invalid", "Bearer " + "a" * 44])
def test_malformed_bearer_precedes_all_three_store_construction_or_calls(
    tmp_path: Path, method: str, suffix: str, credential: str
) -> None:
    path = tmp_path / "unrelated.sqlite3"
    store = ClosedFalseyStore()
    client = TestClient(create_app(settings(path), local_portfolio_store=store))
    response = client.request(
        method,
        PORT + suffix,
        headers={"Authorization": credential},
        json=request_body(method, suffix),
    )
    assert_error(response, 401, "SESSION_INVALID")
    assert store.calls == 0 and not path.exists()
