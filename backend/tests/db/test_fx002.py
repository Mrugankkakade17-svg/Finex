import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_fx002_quantity_is_numeric_and_rejects_invalid_foreign_keys(postgres_db):
    async with postgres_db.connect() as connection:
        transaction = await connection.begin()
        try:
            quantity_type = await connection.execute(
                text(
                    """
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'finex'
                      AND table_name = 'portfolio_holdings'
                      AND column_name = 'quantity'
                    """
                )
            )
            assert quantity_type.scalar_one() == "numeric"

            user_a = str(uuid.uuid4())
            user_b = str(uuid.uuid4())
            for user_id in (user_a, user_b):
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.users
                            (user_id, email, password_hash, name)
                        VALUES (:user_id, :email, 'test-hash', 'FK Test')
                        """
                    ),
                    {"user_id": user_id, "email": f"{user_id}@example.test"},
                )

            portfolio_id = str(uuid.uuid4())
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.portfolios
                        (portfolio_id, user_id, name)
                    VALUES (:portfolio_id, :user_id, 'FK Test Portfolio')
                    """
                ),
                {"portfolio_id": portfolio_id, "user_id": user_a},
            )

            await connection.execute(
                text(
                    """
                    INSERT INTO finex.portfolio_holdings
                        (holding_id, portfolio_id, user_id, instrument_symbol,
                         quantity, avg_buy_price)
                    VALUES (:holding_id, :portfolio_id, :user_id, 'TEST',
                            1.25, 10.00)
                    """
                ),
                {
                    "holding_id": str(uuid.uuid4()),
                    "portfolio_id": portfolio_id,
                    "user_id": user_a,
                },
            )

            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.portfolio_holdings
                                (holding_id, portfolio_id, user_id, instrument_symbol,
                                 quantity, avg_buy_price)
                            VALUES (:holding_id, :missing_portfolio, :user_id, 'TEST',
                                    1.00, 10.00)
                            """
                        ),
                        {
                            "holding_id": str(uuid.uuid4()),
                            "missing_portfolio": str(uuid.uuid4()),
                            "user_id": user_a,
                        },
                    )

            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.portfolio_holdings
                                (holding_id, portfolio_id, user_id, instrument_symbol,
                                 quantity, avg_buy_price)
                            VALUES (:holding_id, :portfolio_id, :user_id, 'TEST',
                                    1.00, 10.00)
                            """
                        ),
                        {
                            "holding_id": str(uuid.uuid4()),
                            "portfolio_id": portfolio_id,
                            "user_id": user_b,
                        },
                    )
        finally:
            await transaction.rollback()
