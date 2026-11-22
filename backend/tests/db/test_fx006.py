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
