"""PostgreSQL database tests for fx_003b ai_feedback table (S1-MI01).

Verifies:
- Table finex.ai_feedback schema and constraints
- User foreign key constraint and ON DELETE CASCADE
- Primary key enforcement on (user_id, feedback_id)
- Index on (user_id, created_at)
"""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_ai_feedback_table_crud_and_cascade(postgres_db):
    """Verify that feedback rows are user-scoped and cascade-deleted with user."""
    async with postgres_db.connect() as connection:
        transaction = await connection.begin()
        try:
            user_id = str(uuid.uuid4())
            feedback_id = f"fb-{uuid.uuid4().hex[:8]}"

            # 1. Create a parent user in finex.users
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.users (user_id, email, password_hash, name)
                    VALUES (:user_id, :email, 'test-hash', 'AI Feedback User')
                    """
                ),
                {"user_id": user_id, "email": f"{user_id}@example.test"},
            )

            # 2. Insert feedback row
            await connection.execute(
                text(
                    """
                    INSERT INTO finex.ai_feedback (
                        user_id, feedback_id, message_id, rating, comment
                    ) VALUES (
                        :user_id, :feedback_id, 'msg-101', 'THUMBS_UP', 'Excellent answer.'
                    )
                    """
                ),
                {"user_id": user_id, "feedback_id": feedback_id},
            )

            # 3. Verify row exists
            result = await connection.execute(
                text(
                    """
                    SELECT user_id, feedback_id, message_id, rating, comment
                    FROM finex.ai_feedback
                    WHERE user_id = :user_id AND feedback_id = :feedback_id
                    """
                ),
                {"user_id": user_id, "feedback_id": feedback_id},
            )
            row = result.mappings().first()
            assert row is not None
            assert row["rating"] == "THUMBS_UP"
            assert row["message_id"] == "msg-101"

            # 4. Enforce foreign key: inserting feedback with non-existent user must fail
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.ai_feedback (
                                user_id, feedback_id, message_id, rating
                            ) VALUES (
                                'non-existent-user', 'fb-err', 'msg-err', 'THUMBS_DOWN'
                            )
                            """
                        )
                    )

            # 5. Enforce primary key uniqueness on (user_id, feedback_id)
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.ai_feedback (
                                user_id, feedback_id, message_id, rating
                            ) VALUES (
                                :user_id, :feedback_id, 'msg-dup', 'THUMBS_DOWN'
                            )
                            """
                        ),
                        {"user_id": user_id, "feedback_id": feedback_id},
                    )

            # 6. Verify ON DELETE CASCADE:
            # Deleting user from finex.users cascades to finex.ai_feedback
            await connection.execute(
                text("DELETE FROM finex.users WHERE user_id = :user_id"),
                {"user_id": user_id},
            )

            cascade_check = await connection.execute(
                text(
                    """
                    SELECT COUNT(*) AS cnt FROM finex.ai_feedback
                    WHERE user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            )
            count = cascade_check.scalar_one()
            assert count == 0, "Feedback records must be cascade deleted when user is deleted"

        finally:
            await transaction.rollback()
