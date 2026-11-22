"""Idempotently seed the educational allocation models and benchmark map.

Run from the repository root with ``python scripts/seed_reference_data.py``.
Set ``DATABASE_URL`` to the target PostgreSQL database before running.
"""

import asyncio
import os
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

ALLOCATION_MODELS: tuple[dict[str, str], ...] = (
    {
        "model_code": "CONSERVATIVE_V1",
        "name": "Conservative educational model",
        "risk_category": "CONSERVATIVE",
        "version": "v1",
        "description": "Illustrative reference weights for educational demonstrations; not advice.",
    },
    {
        "model_code": "MODERATE_V1",
        "name": "Moderate educational model",
        "risk_category": "MODERATE",
        "version": "v1",
        "description": "Illustrative reference weights for educational demonstrations; not advice.",
    },
    {
        "model_code": "AGGRESSIVE_V1",
        "name": "Aggressive educational model",
        "risk_category": "AGGRESSIVE",
        "version": "v1",
        "description": "Illustrative reference weights for educational demonstrations; not advice.",
    },
)

ALLOCATION_TARGETS: tuple[dict[str, Any], ...] = (
    {
        "model_code": "CONSERVATIVE_V1",
        "asset_class": "EQUITY",
        "target_weight": "0.200000",
    },
    {
        "model_code": "CONSERVATIVE_V1",
        "asset_class": "FIXED_INCOME",
        "target_weight": "0.700000",
    },
    {
        "model_code": "CONSERVATIVE_V1",
        "asset_class": "CASH",
        "target_weight": "0.100000",
    },
    {"model_code": "MODERATE_V1", "asset_class": "EQUITY", "target_weight": "0.500000"},
    {
        "model_code": "MODERATE_V1",
        "asset_class": "FIXED_INCOME",
        "target_weight": "0.400000",
    },
    {"model_code": "MODERATE_V1", "asset_class": "CASH", "target_weight": "0.100000"},
    {
        "model_code": "AGGRESSIVE_V1",
        "asset_class": "EQUITY",
        "target_weight": "0.800000",
    },
    {
        "model_code": "AGGRESSIVE_V1",
        "asset_class": "FIXED_INCOME",
        "target_weight": "0.100000",
    },
    {"model_code": "AGGRESSIVE_V1", "asset_class": "CASH", "target_weight": "0.100000"},
)

BENCHMARKS: tuple[dict[str, str], ...] = (
    {
        "asset_class": "EQUITY",
        "benchmark_symbol": "SPY",
        "benchmark_name": "Synthetic S&P 500 ETF proxy",
        "version": "v1",
    },
    {
        "asset_class": "FIXED_INCOME",
        "benchmark_symbol": "AGG",
        "benchmark_name": "Synthetic U.S. aggregate bond ETF proxy",
        "version": "v1",
    },
    {
        "asset_class": "CASH",
        "benchmark_symbol": "CASH",
        "benchmark_name": "Synthetic cash reference",
        "version": "v1",
    },
)


async def seed_reference_data(connection: AsyncConnection) -> None:
    """Upsert the canonical v1 records; repeated runs produce the same state."""
    await connection.execute(
        text(
            """
            INSERT INTO finex.allocation_models
                (model_code, name, risk_category, version, description, is_active)
            VALUES
                (:model_code, :name, :risk_category, :version, :description, TRUE)
            ON CONFLICT (model_code) DO UPDATE SET
                name = EXCLUDED.name,
                risk_category = EXCLUDED.risk_category,
                version = EXCLUDED.version,
                description = EXCLUDED.description,
                is_active = EXCLUDED.is_active
            """
        ),
        ALLOCATION_MODELS,
    )
    await connection.execute(
        text(
            """
            INSERT INTO finex.allocation_model_targets (model_code, asset_class, target_weight)
            VALUES (:model_code, :asset_class, :target_weight)
            ON CONFLICT (model_code, asset_class) DO UPDATE SET
                target_weight = EXCLUDED.target_weight
            """
        ),
        ALLOCATION_TARGETS,
    )
    await connection.execute(
        text(
            """
            INSERT INTO finex.benchmark_map
                (asset_class, benchmark_symbol, benchmark_name, currency, source_type, version)
            VALUES
                (:asset_class, :benchmark_symbol, :benchmark_name, 'USD', 'SYNTHETIC', :version)
            ON CONFLICT (asset_class) DO UPDATE SET
                benchmark_symbol = EXCLUDED.benchmark_symbol,
                benchmark_name = EXCLUDED.benchmark_name,
                currency = EXCLUDED.currency,
                source_type = EXCLUDED.source_type,
                version = EXCLUDED.version
            """
        ),
        BENCHMARKS,
    )


async def main() -> None:
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL must point to the target PostgreSQL database.")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await seed_reference_data(connection)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

