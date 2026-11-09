"""Real HTTP configuration faults, explicit falsey ports and private error boundaries."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.domain.local_portfolio import (
    CATALOG_VERSION,
    FIXTURE_AS_OF,
    QUOTE_SNAPSHOT_VERSION,
    QUOTE_SOURCE,
    QUOTE_SOURCE_TYPE,
    LocalCatalogUnavailable,
    LocalPortfolioCatalogSnapshot,
    LocalPortfolioInstrument,
    LocalPortfolioQuoteRecord,
    LocalPortfolioQuoteSnapshot,
    LocalQuoteUnavailable,
)
from app.main import create_app
from tests.contract.test_local_s1_api import TestClock, assert_error
from tests.contract.test_local_s2_portfolio_api import (
    PORT,
    added,
    application,
    completed,
    created,
    holding_input,
    metrics,
    portfolio_input,
)
from tests.contract.test_local_s2_portfolio_transport import settings


class FalseyCatalogue:
    def __bool__(self) -> bool:
        return False

    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        return LocalPortfolioCatalogSnapshot(
            CATALOG_VERSION,
            "USD",
            (
                LocalPortfolioInstrument(
                    "SYN:AAPL", "Injected synthetic example", "EQUITY", "TEST", "USD"
                ),
            ),
        )


class FalseyQuotes:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def __bool__(self) -> bool:
        return False

    def snapshot(self, instrument_ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        self.calls.append(instrument_ids)
        return LocalPortfolioQuoteSnapshot(
            QUOTE_SNAPSHOT_VERSION,
            QUOTE_SOURCE,
            QUOTE_SOURCE_TYPE,
            FIXTURE_AS_OF,
            tuple(
                LocalPortfolioQuoteRecord(instrument, "100.0000", "CACHED", FIXTURE_AS_OF, None)
                for instrument in instrument_ids
            ),
        )


class BrokenCatalogue:
    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        raise LocalCatalogUnavailable("private synthetic catalogue fault; must not be returned")


class InvalidCatalogue:
    def snapshot(self) -> LocalPortfolioCatalogSnapshot:
        return LocalPortfolioCatalogSnapshot("unsupported.v2", "USD", ())


class BrokenQuotes:
    def __init__(self) -> None:
        self.calls = 0

    def snapshot(self, instrument_ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        self.calls += 1
        raise LocalQuoteUnavailable("private synthetic quote fault; must not be returned")


class InvalidQuotes:
    def snapshot(self, instrument_ids: tuple[str, ...]) -> LocalPortfolioQuoteSnapshot:
        # A record is missing: this is faulty configuration, not a legitimate unavailable quote.
        return LocalPortfolioQuoteSnapshot(
            QUOTE_SNAPSHOT_VERSION, QUOTE_SOURCE, QUOTE_SOURCE_TYPE, FIXTURE_AS_OF, ()
        )


def test_explicit_falsey_catalogue_and_quote_ports_are_never_replaced_by_defaults(
    tmp_path: Path,
) -> None:
    quote_port = FalseyQuotes()
    client = TestClient(
        create_app(
            settings(tmp_path / "explicit.sqlite3"),
            local_clock=TestClock(),
            local_portfolio_catalogue=FalseyCatalogue(),
            local_portfolio_quotes=quote_port,
        )
    )
    headers = completed(client)
    catalogue = client.get(PORT + "/instruments", headers=headers).json()["data"]
    assert catalogue["count"] == 1
    assert catalogue["items"][0]["display_name"] == "Injected synthetic example"
    pid = created(client, headers)["portfolio_id"]
    assert metrics(client, headers, pid).json()["data"]["valuation_status"] == "EMPTY"
    assert quote_port.calls == []
    holding = added(client, headers, pid)
    assert holding["sector"] == "TEST"
    assert quote_port.calls == []
    data = metrics(client, headers, pid).json()["data"]
    assert quote_port.calls == [("SYN:AAPL",)]
    assert data["holdings"][0]["quote"]["unit_price"] == "100.0000"
    assert data["totals"]["market_value"] == "1000.00"


@pytest.mark.parametrize("port", [BrokenCatalogue, InvalidCatalogue])
def test_catalogue_fault_is_safe_503_not_empty_or_unavailable_valuation(
    tmp_path: Path, port
) -> None:
    clock = TestClock()
    path = tmp_path / "catalogue.sqlite3"
    healthy = TestClient(application(path, clock))
    owner, other = completed(healthy), completed(healthy, "learner-b")
    pid = created(healthy, owner)["portfolio_id"]
    client = TestClient(
        create_app(settings(path), local_clock=clock, local_portfolio_catalogue=port())
    )
    response = client.get(PORT + "/instruments", headers=owner)
    assert_error(response, 503, "LOCAL_CATALOG_UNAVAILABLE")
    assert "private synthetic" not in response.text and "unsupported.v2" not in response.text
    # Parent ownership is checked before semantic instrument/catalogue handling.
    assert_error(
        client.post(f"{PORT}/{pid}/holdings", headers=other, json=holding_input("SYN:OTHER")),
        404,
        "LOCAL_PORTFOLIO_NOT_FOUND",
    )
    assert healthy.get(PORT, headers=owner).json()["data"]["count"] == 1
    assert healthy.get(f"{PORT}/{pid}/holdings", headers=owner).json()["data"]["count"] == 0


@pytest.mark.parametrize("port", [BrokenQuotes, InvalidQuotes])
def test_quote_fault_does_not_disable_crud_or_fabricate_valuation(tmp_path: Path, port) -> None:
    quote_port = port()
    client = TestClient(
        create_app(
            settings(tmp_path / "quotes.sqlite3"),
            local_clock=TestClock(),
            local_portfolio_quotes=quote_port,
        )
    )
    headers = completed(client)
    pid = created(client, headers)["portfolio_id"]
    assert metrics(client, headers, pid).json()["data"]["valuation_status"] == "EMPTY"
    first = added(client, headers, pid)
    update = holding_input(quantity="2.000000")
    update.pop("instrument_id")
    assert client.put(f"{PORT}/{pid}", headers=headers, json=portfolio_input()).status_code == 200
    assert (
        client.put(
            f"{PORT}/{pid}/holdings/{first['holding_id']}", headers=headers, json=update
        ).status_code
        == 200
    )
    assert client.get(f"{PORT}/{pid}/holdings", headers=headers).json()["data"]["count"] == 1
    if isinstance(quote_port, BrokenQuotes):
        assert quote_port.calls == 0
    response = client.get(f"{PORT}/{pid}/metrics", headers=headers)
    assert_error(response, 503, "LOCAL_QUOTE_UNAVAILABLE")
    assert "private synthetic" not in response.text
    assert "data" not in response.json()
    assert (
        client.delete(f"{PORT}/{pid}/holdings/{first['holding_id']}", headers=headers).status_code
        == 200
    )
    assert metrics(client, headers, pid).json()["data"]["valuation_status"] == "EMPTY"
