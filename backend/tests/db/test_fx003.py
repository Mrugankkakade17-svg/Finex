import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.postgres


@pytest.mark.asyncio
async def test_fx003_user_owned_rows_are_scoped_and_cascade(postgres_db):
    async with postgres_db.connect() as connection:
        transaction = await connection.begin()
        try:
            user_a = str(uuid.uuid4())
            user_b = str(uuid.uuid4())
            for user_id in (user_a, user_b):
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.users
                            (user_id, email, password_hash, name)
                        VALUES (:user_id, :email, 'test-hash', 'fx003 test')
                        """
                    ),
                    {"user_id": user_id, "email": f"{user_id}@example.test"},
                )

            for user_id, goal_id in (
                (user_a, "shared-goal"),
                (user_b, "shared-goal"),
                (user_b, "other-user-goal"),
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.goals
                            (user_id, goal_id, title, target_amount, current_amount,
                             horizon_years, monthly_contribution, expected_annual_return_pct,
                             projected_final_amount, shortfall_or_surplus, is_on_track,
                             assumptions_statement)
                        VALUES (:user_id, :goal_id, 'Test goal', 1000, 100, 5, 10, 6,
                                1500, 500, true, 'Deterministic test projection')
                        """
                    ),
                    {"user_id": user_id, "goal_id": goal_id},
                )

            for user_id in (user_a, user_b):
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.goal_projections
                            (user_id, goal_id, year, projected_balance,
                             contributions_total, growth_total)
                        VALUES (:user_id, 'shared-goal', 1, 200, 220, 20)
                        """
                    ),
                    {"user_id": user_id},
                )
            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.goal_projections
                                (user_id, goal_id, year, projected_balance,
                                 contributions_total, growth_total)
                            VALUES (:user_id, 'other-user-goal', 1, 200, 220, 20)
                            """
                        ),
                        {"user_id": user_a},
                    )

            for user_id in (user_a, user_b):
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.spending_transactions
                            (user_id, transaction_id, date, description_masked,
                             amount, category)
                        VALUES (:user_id, 'shared-transaction', '2026-10-05',
                                'MASKED', 84.50, 'Groceries')
                        """
                    ),
                    {"user_id": user_id},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.alert_rules
                            (user_id, rule_id, rule_name, condition_type,
                             target_symbol_or_goal, comparison_operator, threshold_value,
                             cooldown_minutes, created_at)
                        VALUES (:user_id, :rule_id, 'Test rule', 'PRICE_THRESHOLD',
                                'TEST', 'GT', 100, 60, '2026-10-01T12:00:00Z')
                        """
                    ),
                    {"user_id": user_id, "rule_id": f"rule-{user_id}"},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.alerts
                            (user_id, notification_id, rule_id, title, body, severity,
                             created_at, is_read)
                        VALUES (:user_id, :notification_id, :rule_id, 'Test alert',
                                'Test body', 'INFO', '2026-10-01T12:00:00Z', false)
                        """
                    ),
                    {
                        "user_id": user_id,
                        "notification_id": f"notification-{user_id}",
                        "rule_id": f"rule-{user_id}",
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.privacy_requests
                            (user_id, request_id, action, status, requested_at,
                             message, download_url)
                        VALUES (:user_id, 'shared-request', 'EXPORT', 'COMPLETED',
                                '2026-10-01T12:00:00Z', 'Export queued', NULL)
                        """
                    ),
                    {"user_id": user_id},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO finex.consent_audit
                            (user_id, consent_version, granted_at, is_active)
                        VALUES (:user_id, 'v1.0', '2026-10-01T12:00:00Z', true)
                        """
                    ),
                    {"user_id": user_id},
                )

            with pytest.raises(IntegrityError):
                async with connection.begin_nested():
                    await connection.execute(
                        text(
                            """
                            INSERT INTO finex.alerts
                                (user_id, notification_id, rule_id, title, body,
                                 severity, created_at)
                            VALUES (:user_id, 'cross-user-notification', :other_rule_id,
                                    'Test alert', 'Test body', 'INFO',
                                    '2026-10-01T12:00:00Z')
                            """
                        ),
                        {
                            "user_id": user_a,
                            "other_rule_id": f"rule-{user_b}",
                        },
                    )

            user_a_goals = await connection.execute(
                text("SELECT goal_id FROM finex.goals WHERE user_id = :user_id"),
                {"user_id": user_a},
            )
            assert user_a_goals.scalars().all() == ["shared-goal"]

            await connection.execute(
                text("DELETE FROM finex.users WHERE user_id = :user_id"),
                {"user_id": user_a},
            )
            for table in (
                "goals",
                "goal_projections",
                "spending_transactions",
                "alert_rules",
                "alerts",
                "privacy_requests",
                "consent_audit",
            ):
                remaining = await connection.execute(
                    text(f"SELECT count(*) FROM finex.{table} WHERE user_id = :user_id"),
                    {"user_id": user_a},
                )
                assert remaining.scalar_one() == 0
                other_user_rows = await connection.execute(
                    text(f"SELECT count(*) FROM finex.{table} WHERE user_id = :user_id"),
                    {"user_id": user_b},
                )
                assert other_user_rows.scalar_one() > 0
        finally:
            await transaction.rollback()
