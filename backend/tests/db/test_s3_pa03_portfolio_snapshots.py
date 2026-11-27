"""PostgreSQL integration coverage for daily snapshot idempotence."""

import os
import uuid
from datetime import date
from decimal import Decimal

import psycopg
import pytest

from app.jobs.snapshot_portfolios import PortfolioDailySnapshot, write_daily_snapshots
from app.ports.adapters.postgres_local_store import postgres_dsn

pytestmark = [pytest.mark.postgres, pytest.mark.asyncio]


async def test_daily_snapshot_upsert_is_idempotent_per_portfolio_and_day(postgres_db) -> None:
    database_url = os.environ["DATABASE_URL"]
    owner_a = f"snapshot-owner-{uuid.uuid4().hex}"
    owner_b = f"snapshot-owner-{uuid.uuid4().hex}"
    portfolio_a = f"snapshot-portfolio-{uuid.uuid4().hex}"
    portfolio_b = f"snapshot-portfolio-{uuid.uuid4().hex}"
    day = date(2026, 11, 27)

    def record(user_id: str, portfolio_id: str, value: str) -> PortfolioDailySnapshot:
        return PortfolioDailySnapshot(
            user_id=user_id,
            portfolio_id=portfolio_id,
            snapshot_date=day,
            currency="USD",
            total_value=Decimal(value),
            total_cost=Decimal("100"),
            total_gain_loss=Decimal(value) - Decimal("100"),
            total_gain_loss_pct=(Decimal(value) - Decimal("100")),
            holdings_count=1,
            data_status="LIVE",
            snapshot_data='{"asset_allocation":[],"sector_allocation":[]}',
        )

    try:
        assert write_daily_snapshots(database_url, [record(owner_a, portfolio_a, "125")]) == 1
        assert (
            write_daily_snapshots(
                database_url,
                [record(owner_a, portfolio_a, "130"), record(owner_b, portfolio_b, "240")],
            )
            == 2
        )

        with psycopg.connect(postgres_dsn(database_url)) as connection:
            rows = connection.execute(
                "SELECT user_id, portfolio_id, total_value FROM finex.portfolio_daily_snapshots "
                "WHERE snapshot_date=%s AND portfolio_id IN (%s,%s) ORDER BY portfolio_id",
                (day, portfolio_a, portfolio_b),
            ).fetchall()
            expected_rows = [
                (owner_a, portfolio_a, Decimal("130")),
                (owner_b, portfolio_b, Decimal("240")),
            ]
            assert rows == sorted(expected_rows, key=lambda row: row[1])
    finally:
        with psycopg.connect(postgres_dsn(database_url)) as connection:
            connection.execute(
                "DELETE FROM finex.portfolio_daily_snapshots WHERE portfolio_id IN (%s,%s)",
                (portfolio_a, portfolio_b),
            )
