import pytest
from scripts.seed_reference_data import seed_reference_data
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_fx006_seed_is_idempotent_and_database_constraints_hold(postgres_db):
    async with postgres_db.connect() as connection:
        transaction = await connection.begin()
        try:
            await seed_reference_data(connection)
            first_targets = (
                await connection.execute(
                    text(
                        "SELECT model_code, asset_class, target_weight "
                        "FROM finex.allocation_model_targets ORDER BY model_code, asset_class"
                    )
                )
            ).all()
            await seed_reference_data(connection)
            second_targets = (
                await connection.execute(
                    text(
                        "SELECT model_code, asset_class, target_weight "
                        "FROM finex.allocation_model_targets ORDER BY model_code, asset_class"
                    )
                )
            ).all()
            assert second_targets == first_targets

            # A new benchmark version must coexist with, not overwrite, v1.
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.benchmark_map
                        (asset_class, version, benchmark_symbol, benchmark_name)
                    VALUES ('EQUITY', 'v2', 'VTI', 'Synthetic total market proxy')
                    ON CONFLICT (asset_class, version) DO UPDATE SET
                        benchmark_symbol = EXCLUDED.benchmark_symbol,
                        benchmark_name = EXCLUDED.benchmark_name
                    """
                )
            )
            equity_versions = (
                await connection.execute(
                    text(
                        "SELECT version, benchmark_symbol FROM finex.benchmark_map "
                        "WHERE asset_class = 'EQUITY' ORDER BY version"
                    )
                )
            ).all()
            assert equity_versions == [("v1", "SPY"), ("v2", "VTI")]

            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            "INSERT INTO finex.allocation_model_targets "
                            "(model_code, asset_class, target_weight) "
                            "VALUES ('CONSERVATIVE_V1', 'EQUITY', 1.1)"
                        )
                    )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            "INSERT INTO finex.benchmark_map "
                            "(asset_class, benchmark_symbol, benchmark_name, version) "
                            "VALUES ('CRYPTO', 'BTC', 'Non-contract asset class', 'v1')"
                        )
                    )
        finally:
            await transaction.rollback()
