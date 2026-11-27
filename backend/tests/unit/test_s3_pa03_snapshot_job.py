"""Deterministic tests for the daily portfolio snapshot job."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.config.settings import Settings
from app.jobs.snapshot_portfolios import (
    PortfolioDailySnapshot,
    PortfolioOwner,
    build_daily_snapshot,
    run_daily_snapshot_job,
)
from app.schemas.portfolio import PortfolioSummaryResponse

SNAPSHOT_DATE = date(2026, 11, 27)


def summary(
    portfolio_id: str = "portfolio-1",
    *,
    total_value: float = 1250.50,
    total_cost: float = 1000,
    holdings_count: int = 2,
) -> PortfolioSummaryResponse:
    return PortfolioSummaryResponse(
        portfolio_id=portfolio_id,
        name="Retirement",
        currency="usd",
        total_value=total_value,
        total_cost=total_cost,
        total_gain_loss=total_value - total_cost,
        total_gain_loss_pct=(total_value - total_cost) / total_cost * 100,
        holdings_count=holdings_count,
        data_status="LIVE",
        asset_allocation=[],
        sector_allocation=[],
        top_performers=[],
    )


def postgres_settings() -> Settings:
    return Settings(
        _env_file=None,
        app_persistence="postgresql",
        app_database_url="postgresql+asyncpg://finex:secret@localhost/finex_test",
    )


def test_build_snapshot_preserves_owner_and_daily_valuation() -> None:
    result = build_daily_snapshot(
        PortfolioOwner("owner-1", "portfolio-1"), summary(), SNAPSHOT_DATE
    )

    assert result.snapshot_date == SNAPSHOT_DATE
    assert result.user_id == "owner-1"
    assert result.portfolio_id == "portfolio-1"
    assert result.currency == "USD"
    assert result.total_value == Decimal("1250.5")
    assert result.total_cost == Decimal("1000")
    assert result.total_gain_loss == Decimal("250.5")
    assert result.holdings_count == 2
    assert result.data_status == "LIVE"
    assert result.snapshot_data == '{"asset_allocation":[],"sector_allocation":[]}'


@pytest.mark.parametrize(
    "owner,record,day,message",
    [
        (
            PortfolioOwner("owner-1", "portfolio-1"),
            summary("other"),
            SNAPSHOT_DATE,
            "does not match",
        ),
        (
            PortfolioOwner("owner-1", "portfolio-1"),
            summary(total_value=float("nan")),
            SNAPSHOT_DATE,
            "finite",
        ),
        (
            PortfolioOwner("owner-1", "portfolio-1"),
            summary(total_value=-1),
            SNAPSHOT_DATE,
            "nonnegative",
        ),
        (
            PortfolioOwner("owner-1", "portfolio-1"),
            summary(),
            datetime(2026, 11, 27, tzinfo=timezone.utc),
            "date-only",
        ),
    ],
)
def test_build_snapshot_rejects_invalid_identity_values_and_dates(
    owner: PortfolioOwner, record: PortfolioSummaryResponse, day: date, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        build_daily_snapshot(owner, record, day)


@pytest.mark.asyncio
async def test_job_values_each_owner_scoped_portfolio_and_writes_once() -> None:
    owners = [PortfolioOwner("owner-a", "portfolio-a"), PortfolioOwner("owner-b", "portfolio-b")]
    summarized: list[tuple[str, str]] = []
    persisted: list[PortfolioDailySnapshot] = []

    def load(url: str) -> list[PortfolioOwner]:
        assert url.startswith("postgresql+")
        return owners

    async def summarize(portfolio_id: str, user_id: str) -> PortfolioSummaryResponse:
        summarized.append((user_id, portfolio_id))
        return summary(portfolio_id)

    def write(url: str, snapshots: list[PortfolioDailySnapshot]) -> int:
        assert url.startswith("postgresql+")
        persisted.extend(snapshots)
        return len(snapshots)

    result = await run_daily_snapshot_job(
        SNAPSHOT_DATE,
        settings=postgres_settings(),
        portfolio_loader=load,
        summary_provider=summarize,
        snapshot_writer=write,
    )

    assert result.snapshot_date == SNAPSHOT_DATE
    assert result.portfolios_snapshotted == 2
    assert summarized == [("owner-a", "portfolio-a"), ("owner-b", "portfolio-b")]
    assert [(item.user_id, item.portfolio_id) for item in persisted] == [
        ("owner-a", "portfolio-a"),
        ("owner-b", "portfolio-b"),
    ]


@pytest.mark.asyncio
async def test_empty_run_does_not_call_writer() -> None:
    result = await run_daily_snapshot_job(
        SNAPSHOT_DATE,
        settings=postgres_settings(),
        portfolio_loader=lambda _url: [],
        summary_provider=lambda *_args: pytest.fail("No portfolios should be valued"),
        snapshot_writer=lambda *_args: pytest.fail("Empty run should not write"),
    )

    assert result.portfolios_snapshotted == 0


@pytest.mark.asyncio
async def test_failed_valuation_writes_no_partial_daily_batch() -> None:
    owners = [PortfolioOwner("owner-a", "portfolio-a"), PortfolioOwner("owner-b", "portfolio-b")]
    writes: list[PortfolioDailySnapshot] = []

    async def summarize(portfolio_id: str, _user_id: str) -> PortfolioSummaryResponse:
        if portfolio_id == "portfolio-b":
            raise RuntimeError("Market valuation failed")
        return summary(portfolio_id)

    with pytest.raises(RuntimeError, match="Market valuation failed"):
        await run_daily_snapshot_job(
            SNAPSHOT_DATE,
            settings=postgres_settings(),
            portfolio_loader=lambda _url: owners,
            summary_provider=summarize,
            snapshot_writer=lambda _url, batch: writes.extend(batch) or len(batch),
        )

    assert writes == []


@pytest.mark.asyncio
async def test_job_fails_closed_without_postgres_persistence() -> None:
    settings = Settings(_env_file=None, app_persistence="sqlite")
    with pytest.raises(RuntimeError, match="APP_PERSISTENCE=postgresql"):
        await run_daily_snapshot_job(SNAPSHOT_DATE, settings=settings)
