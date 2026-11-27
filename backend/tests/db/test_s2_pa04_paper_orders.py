import asyncio
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.config.settings import Settings
from app.repositories.paper_trading_repository import (
    PaperOrderRecord,
    PaperTradingConflict,
    PostgresPaperTradingRepository,
)

pytestmark = pytest.mark.postgres


def _order(user_id: str, key: str, *, quantity: int = 1) -> PaperOrderRecord:
    return PaperOrderRecord(
        order_id=f"paper-order-{uuid.uuid4().hex}",
        account_id=f"paper-{uuid.uuid4().hex}",
        user_id=user_id,
        idempotency_key=key,
        request_fingerprint="a" * 64,
        instrument_id="AAPL",
        exchange="NASDAQ",
        side="BUY",
        quantity=quantity,
        executed_price=Decimal("80.00"),
        notional_cents=8000 * quantity,
        fee_cents=8 * quantity,
        cash_delta_cents=-8008 * quantity,
        balance_after_cents=0,
        quote_freshness="DELAYED",
        quote_as_of="2026-11-23T15:00:00Z",
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_paper_order_is_idempotent_and_persists_one_ledger_entry(postgres_db):
    user_id = str(uuid.uuid4())
    async with postgres_db.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO finex.users(user_id,email,password_hash,name) "
                "VALUES(:user_id,:email,'test-hash','PA04 test')"
            ),
            {"user_id": user_id, "email": f"{user_id}@paper.test"},
        )

    repository = PostgresPaperTradingRepository(
        Settings(
            app_database_url=os.environ["DATABASE_URL"],
            paper_trading_initial_cash=Decimal("100.00"),
            paper_trading_fee_bps=10,
        )
    )
    order = _order(user_id, "integration-order-001")
    saved, created = await asyncio.to_thread(
        repository.execute_order, order, initial_cash_cents=10_000
    )
    replayed, replay_created = await asyncio.to_thread(
        repository.execute_order, order, initial_cash_cents=10_000
    )

    assert created is True
    assert replay_created is False
    assert replayed.order_id == saved.order_id
    assert saved.balance_after_cents == 1_992
    assert await asyncio.to_thread(repository.find_order, user_id, order.idempotency_key)

    async with postgres_db.connect() as connection:
        result = await connection.execute(
            text(
                "SELECT COUNT(*) FROM finex.paper_orders WHERE user_id=:user_id "
                "AND idempotency_key=:key"
            ),
            {"user_id": user_id, "key": order.idempotency_key},
        )
        assert result.scalar_one() == 1
        result = await connection.execute(
            text("SELECT SUM(cash_delta_cents) FROM finex.paper_ledger WHERE user_id=:user_id"),
            {"user_id": user_id},
        )
        assert result.scalar_one() == 1_992


@pytest.mark.asyncio
async def test_parallel_orders_lock_account_and_prevent_negative_cash(postgres_db):
    user_id = str(uuid.uuid4())
    async with postgres_db.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO finex.users(user_id,email,password_hash,name) "
                "VALUES(:user_id,:email,'test-hash','PA04 concurrency test')"
            ),
            {"user_id": user_id, "email": f"{user_id}@paper.test"},
        )

    repository = PostgresPaperTradingRepository(
        Settings(
            app_database_url=os.environ["DATABASE_URL"],
            paper_trading_initial_cash=Decimal("100.00"),
        )
    )

    async def place(key: str):
        return await asyncio.to_thread(
            repository.execute_order,
            _order(user_id, key),
            initial_cash_cents=10_000,
        )

    outcomes = await asyncio.gather(
        place("integration-order-002"),
        place("integration-order-003"),
        return_exceptions=True,
    )
    fills = [item for item in outcomes if not isinstance(item, Exception)]
    rejects = [item for item in outcomes if isinstance(item, PaperTradingConflict)]
    assert len(fills) == 1
    assert len(rejects) == 1
    assert rejects[0].code == "INSUFFICIENT_CASH"

    async with postgres_db.connect() as connection:
        result = await connection.execute(
            text("SELECT SUM(cash_delta_cents) FROM finex.paper_ledger WHERE user_id=:user_id"),
            {"user_id": user_id},
        )
        assert result.scalar_one() == 1_992
        result = await connection.execute(
            text("SELECT COUNT(*) FROM finex.paper_orders WHERE user_id=:user_id"),
            {"user_id": user_id},
        )
        assert result.scalar_one() == 1
