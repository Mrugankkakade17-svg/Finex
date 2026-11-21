"""Shared store-contract suite: the same behavior runs against SQLite and PostgreSQL."""

from datetime import datetime, timezone
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

from app.domain.local_application import LocalUser
from app.domain.local_foundation import (
    PaperAccountRecord,
    PaperOpeningRecord,
    WatchlistRecord,
)
from app.domain.local_portfolio import LocalPortfolioRecord
from app.domain.local_risk import LocalRiskDraftRecord
from app.ports.adapters.postgres_local_application import PostgresLocalApplicationStore
from app.ports.adapters.postgres_local_foundation import PostgresLocalFoundationStore
from app.ports.adapters.postgres_local_portfolio_store import PostgresLocalPortfolioStore
from app.ports.adapters.postgres_local_risk import PostgresLocalRiskStore
from app.ports.adapters.sqlite_local_application import SQLiteLocalApplicationStore
from app.ports.adapters.sqlite_local_foundation import SQLiteLocalFoundationStore
from app.ports.adapters.sqlite_local_portfolio_store import SQLiteLocalPortfolioStore
from app.ports.adapters.sqlite_local_risk import SQLiteLocalRiskStore

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=timezone.utc)
CONTRACT_USER_IDS = (
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
    "33333333-3333-4333-8333-333333333333",
    "55555555-5555-4555-8555-555555555555",
)


def _cleanup_postgres(database_url: str) -> None:
    from app.ports.adapters.postgres_local_store import postgres_dsn

    with psycopg.connect(postgres_dsn(database_url)) as connection:
        connection.execute(
            "DELETE FROM finex.local_users WHERE user_id = ANY(%s)",
            (list(CONTRACT_USER_IDS),),
        )


@pytest.fixture(params=["sqlite", "postgresql"])
def contract_stores(request: pytest.FixtureRequest, tmp_path: Path):
    if request.param == "sqlite":
        path = tmp_path / "contract.sqlite3"
        yield (
            SQLiteLocalApplicationStore(path),
            SQLiteLocalRiskStore(path),
            SQLiteLocalPortfolioStore(path),
            SQLiteLocalFoundationStore(path),
        )
        return

    load_dotenv()
    import os

    database_url = os.getenv("DATABASE_URL") or os.getenv("APP_DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is required for the PostgreSQL contract suite")
    _cleanup_postgres(database_url)
    yield (
        PostgresLocalApplicationStore(database_url),
        PostgresLocalRiskStore(database_url),
        PostgresLocalPortfolioStore(database_url),
        PostgresLocalFoundationStore(database_url),
    )
    _cleanup_postgres(database_url)


def test_application_contract(contract_stores) -> None:
    application, _, _, _ = contract_stores
    user = LocalUser("11111111-1111-4111-8111-111111111111", "contract-user")
    with application.transaction(write=True) as transaction:
        transaction.create_user(user, "s1.application.v1", NOW)
        assert transaction.get_user_by_alias(user.alias) == user
        assert transaction.get_onboarding(user.id).profile_schema_version == "s1.application.v1"


def test_risk_contract(contract_stores) -> None:
    application, risk, _, _ = contract_stores
    user = LocalUser("22222222-2222-4222-8222-222222222222", "risk-contract")
    with application.transaction(write=True) as transaction:
        transaction.create_user(user, "s1.application.v1", NOW)
    draft = LocalRiskDraftRecord(
        user_id=user.id,
        questionnaire_id="11111111-1111-4111-8111-111111111111",
        questionnaire_version="risk.v1",
        answers_json='{"answers":[]}',
        updated_at=NOW,
    )
    with risk.transaction(write=True) as transaction:
        transaction.save_risk_draft(draft)
        assert transaction.get_risk_draft(user.id) == draft


def test_portfolio_contract(contract_stores) -> None:
    application, _, portfolio, _ = contract_stores
    user = LocalUser("33333333-3333-4333-8333-333333333333", "portfolio-contract")
    with application.transaction(write=True) as transaction:
        transaction.create_user(user, "s1.application.v1", NOW)
    record = LocalPortfolioRecord(
        user_id=user.id,
        portfolio_id="44444444-4444-4444-8444-444444444444",
        name="Contract Portfolio",
        description=None,
        currency="USD",
        created_at=NOW,
        updated_at=NOW,
    )
    with portfolio.transaction(write=True) as transaction:
        transaction.insert_portfolio(record)
        assert transaction.get_portfolio(user.id, record.portfolio_id) == record


def test_foundation_contract(contract_stores) -> None:
    application, _, _, foundation = contract_stores
    user = LocalUser("55555555-5555-4555-8555-555555555555", "foundation-contract")
    with application.transaction(write=True) as transaction:
        transaction.create_user(user, "s1.application.v1", NOW)
    watchlist = WatchlistRecord(
        user_id=user.id,
        watchlist_id="66666666-6666-4666-8666-666666666666",
        name="Contract Watchlist",
        created_at=NOW,
        updated_at=NOW,
    )
    account = PaperAccountRecord(
        user_id=user.id,
        account_id="77777777-7777-4777-8777-777777777777",
        opening_ledger_id="88888888-8888-4888-8888-888888888888",
        currency="USD",
        opening_cash_cents=1_000_000,
        cash_balance_cents=1_000_000,
        created_at=NOW,
    )
    opening = PaperOpeningRecord(
        user_id=user.id,
        account_id=account.account_id,
        ledger_id=account.opening_ledger_id,
        sequence=0,
        cash_delta_cents=1_000_000,
        cash_after_cents=1_000_000,
        created_at=NOW,
    )
    with foundation.transaction(write=True) as transaction:
        transaction.insert_watchlist(watchlist)
        transaction.insert_account_with_opening(account, opening)
        assert transaction.watchlist(user.id, watchlist.watchlist_id) == watchlist
        assert transaction.account(user.id) == account
