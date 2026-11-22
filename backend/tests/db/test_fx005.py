import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_fx005_ledger_is_append_only_and_blocks_negative_balance(postgres_db):
    async with postgres_db.connect() as connection:
        transaction = await connection.begin()
        try:
            user_id = str(uuid.uuid4())
            account_id = str(uuid.uuid4())
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.users (user_id, email, password_hash, name)
                    VALUES (:user_id, :email, 'test-hash', 'fx005 test')
                    """
                ),
                {"user_id": user_id, "email": f"{user_id}@example.test"},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.paper_accounts (account_id, user_id)
                    VALUES (:account_id, :user_id)
                    """
                ),
                {"account_id": account_id, "user_id": user_id},
            )

            await connection.execute(
                text(
                    """
                    INSERT INTO finex.paper_ledger
                        (ledger_id, account_id, user_id, cash_delta_cents)
                    VALUES (:ledger_id, :account_id, :user_id, 1000)
                    """
                ),
                {
                    "ledger_id": str(uuid.uuid4()),
                    "account_id": account_id,
                    "user_id": user_id,
                },
            )
            debit_id = str(uuid.uuid4())
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.paper_ledger
                        (ledger_id, account_id, user_id, cash_delta_cents)
                    VALUES (:ledger_id, :account_id, :user_id, -400)
                    """
                ),
                {"ledger_id": debit_id, "account_id": account_id, "user_id": user_id},
            )

            balance = await connection.execute(
                text(
                    "SELECT SUM(cash_delta_cents) FROM finex.paper_ledger "
                    "WHERE account_id = :account_id"
                ),
                {"account_id": account_id},
            )
            assert balance.scalar_one() == 600

            with pytest.raises(DBAPIError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.paper_ledger
                                (ledger_id, account_id, user_id, cash_delta_cents)
                            VALUES (:ledger_id, :account_id, :user_id, -601)
                            """
                        ),
                        {
                            "ledger_id": str(uuid.uuid4()),
                            "account_id": account_id,
                            "user_id": user_id,
                        },
                    )

            for statement in (
                "UPDATE finex.paper_ledger SET cash_delta_cents = 1 WHERE ledger_id = :id",
                "DELETE FROM finex.paper_ledger WHERE ledger_id = :id",
            ):
                with pytest.raises(DBAPIError):
                    async with connection.begin_nested():
                        await connection.execute(text(statement), {"id": debit_id})
        finally:
            await transaction.rollback()

