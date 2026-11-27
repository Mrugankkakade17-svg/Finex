"""Capture one owner-scoped valuation row for each portfolio for a UTC day.

Run with ``python -m app.jobs.snapshot_portfolios`` from ``backend`` and
schedule that command once per day in the deployment environment.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Awaitable, Callable, Sequence

import psycopg
from psycopg.rows import dict_row

from app.config.settings import Settings, get_settings
from app.ports.adapters.postgres_local_store import SCHEMA_STATEMENTS, postgres_dsn
from app.schemas.portfolio import PortfolioSummaryResponse
from app.services.portfolio_service import portfolio_service


@dataclass(frozen=True, slots=True)
class PortfolioOwner:
    """Database identity needed to read one portfolio without crossing owners."""

    user_id: str
    portfolio_id: str


@dataclass(frozen=True, slots=True)
class PortfolioDailySnapshot:
    """A validated, privacy-limited daily portfolio valuation record."""

    user_id: str
    portfolio_id: str
    snapshot_date: date
    currency: str
    total_value: Decimal
    total_cost: Decimal
    total_gain_loss: Decimal
    total_gain_loss_pct: Decimal
    holdings_count: int
    data_status: str
    snapshot_data: str


@dataclass(frozen=True, slots=True)
class SnapshotJobResult:
    """Summary of one idempotent daily snapshot run."""

    snapshot_date: date
    portfolios_snapshotted: int


PortfolioLoader = Callable[[str], Sequence[PortfolioOwner]]
SummaryProvider = Callable[[str, str], Awaitable[PortfolioSummaryResponse]]
SnapshotWriter = Callable[[str, Sequence[PortfolioDailySnapshot]], int]


def _decimal(value: object, field: str, *, nonnegative: bool = False) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite decimal.")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite decimal.") from exc
    if not parsed.is_finite() or (nonnegative and parsed < 0):
        raise ValueError(
            f"{field} must be a finite {'nonnegative ' if nonnegative else ''}decimal."
        )
    return parsed


def build_daily_snapshot(
    owner: PortfolioOwner,
    summary: PortfolioSummaryResponse,
    snapshot_date: date,
) -> PortfolioDailySnapshot:
    """Validate the service valuation and build the stable persisted record."""
    if not isinstance(snapshot_date, date) or isinstance(snapshot_date, datetime):
        raise ValueError("snapshot_date must be a date-only value.")
    if not owner.user_id.strip() or not owner.portfolio_id.strip():
        raise ValueError("Portfolio owner and portfolio IDs are required.")
    if summary.portfolio_id != owner.portfolio_id:
        raise ValueError("Portfolio summary does not match the requested portfolio.")
    currency = summary.currency.strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("Portfolio currency must be a three-letter code.")
    if type(summary.holdings_count) is not int or summary.holdings_count < 0:
        raise ValueError("holdings_count must be a nonnegative integer.")

    snapshot_data = {
        "asset_allocation": [item.model_dump(mode="json") for item in summary.asset_allocation],
        "sector_allocation": [item.model_dump(mode="json") for item in summary.sector_allocation],
    }
    encoded = json.dumps(snapshot_data, allow_nan=False, separators=(",", ":"), sort_keys=True)
    return PortfolioDailySnapshot(
        user_id=owner.user_id,
        portfolio_id=owner.portfolio_id,
        snapshot_date=snapshot_date,
        currency=currency,
        total_value=_decimal(summary.total_value, "total_value", nonnegative=True),
        total_cost=_decimal(summary.total_cost, "total_cost", nonnegative=True),
        total_gain_loss=_decimal(summary.total_gain_loss, "total_gain_loss"),
        total_gain_loss_pct=_decimal(summary.total_gain_loss_pct, "total_gain_loss_pct"),
        holdings_count=summary.holdings_count,
        data_status=summary.data_status,
        snapshot_data=encoded,
    )


def list_portfolio_owners(database_url: str) -> list[PortfolioOwner]:
    """Load portfolio/user pairs from the canonical persistent portfolio store."""
    with psycopg.connect(postgres_dsn(database_url), row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            # The operational portfolio store lazily initializes its tables in the
            # same way on normal application requests and standalone job runs.
            for statement in SCHEMA_STATEMENTS:
                cursor.execute(statement)
            rows = cursor.execute(
                "SELECT user_id, portfolio_id FROM finex.local_manual_portfolios "
                "ORDER BY user_id, portfolio_id"
            ).fetchall()
    owners = [PortfolioOwner(row["user_id"], row["portfolio_id"]) for row in rows]
    if len({(item.user_id, item.portfolio_id) for item in owners}) != len(owners):
        raise ValueError("Portfolio store returned duplicate owner/portfolio pairs.")
    return owners


def write_daily_snapshots(database_url: str, snapshots: Sequence[PortfolioDailySnapshot]) -> int:
    """Atomically upsert a run; reruns replace that portfolio's row for the day."""
    if not snapshots:
        return 0
    statement = """
        INSERT INTO finex.portfolio_daily_snapshots (
            user_id, portfolio_id, snapshot_date, currency, total_value, total_cost,
            total_gain_loss, total_gain_loss_pct, holdings_count, data_status,
            snapshot_data, captured_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        ON CONFLICT (portfolio_id, snapshot_date) DO UPDATE SET
            user_id = EXCLUDED.user_id,
            currency = EXCLUDED.currency,
            total_value = EXCLUDED.total_value,
            total_cost = EXCLUDED.total_cost,
            total_gain_loss = EXCLUDED.total_gain_loss,
            total_gain_loss_pct = EXCLUDED.total_gain_loss_pct,
            holdings_count = EXCLUDED.holdings_count,
            data_status = EXCLUDED.data_status,
            snapshot_data = EXCLUDED.snapshot_data,
            captured_at = NOW()
    """
    with psycopg.connect(postgres_dsn(database_url)) as connection:
        with connection.cursor() as cursor:
            for item in snapshots:
                cursor.execute(
                    statement,
                    (
                        item.user_id,
                        item.portfolio_id,
                        item.snapshot_date,
                        item.currency,
                        item.total_value,
                        item.total_cost,
                        item.total_gain_loss,
                        item.total_gain_loss_pct,
                        item.holdings_count,
                        item.data_status,
                        item.snapshot_data,
                    ),
                )
    return len(snapshots)


async def _summarize_portfolio(portfolio_id: str, user_id: str) -> PortfolioSummaryResponse:
    return await portfolio_service.get_portfolio_summary(portfolio_id, user_id)


async def run_daily_snapshot_job(
    snapshot_date: date | None = None,
    *,
    settings: Settings | None = None,
    portfolio_loader: PortfolioLoader | None = None,
    summary_provider: SummaryProvider | None = None,
    snapshot_writer: SnapshotWriter | None = None,
) -> SnapshotJobResult:
    """Value every stored portfolio once and persist one row per UTC day.

    Dependencies are injectable for deterministic tests. Production runs require
    the configured PostgreSQL portfolio store and use its existing valuation service.
    """
    if snapshot_date is None:
        snapshot_date = datetime.now(timezone.utc).date()
    if not isinstance(snapshot_date, date) or isinstance(snapshot_date, datetime):
        raise ValueError("snapshot_date must be a date-only value.")

    active_settings = settings or get_settings()
    if active_settings.app_persistence != "postgresql":
        raise RuntimeError("Daily portfolio snapshots require APP_PERSISTENCE=postgresql.")
    database_url = active_settings.app_database_url.strip()
    if not database_url:
        raise RuntimeError("APP_DATABASE_URL or DATABASE_URL is required for daily snapshots.")

    load = portfolio_loader or list_portfolio_owners
    summarize = summary_provider or _summarize_portfolio
    write = snapshot_writer or write_daily_snapshots
    owners = list(load(database_url))
    if len({(item.user_id, item.portfolio_id) for item in owners}) != len(owners):
        raise ValueError("Portfolio loader returned duplicate owner/portfolio pairs.")

    snapshots = [
        build_daily_snapshot(
            owner, await summarize(owner.portfolio_id, owner.user_id), snapshot_date
        )
        for owner in owners
    ]
    written = write(database_url, snapshots) if snapshots else 0
    return SnapshotJobResult(snapshot_date=snapshot_date, portfolios_snapshotted=written)


def main() -> None:
    """Run the job once; deployment scheduling is intentionally external."""
    result = asyncio.run(run_daily_snapshot_job())
    print(json.dumps(asdict(result), default=str, sort_keys=True))


if __name__ == "__main__":
    main()
