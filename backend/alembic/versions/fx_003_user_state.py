"""S1-MR02 fx_003: persist user-owned module stores.

Revision ID: s1mr02_fx003
Revises: s1mr01_fx002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s1mr02_fx003"
down_revision: Union[str, Sequence[str], None] = "s1mr01_fx002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "goals",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("target_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("current_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("horizon_years", sa.Integer(), nullable=False),
        sa.Column("monthly_contribution", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("expected_annual_return_pct", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("projected_final_amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("shortfall_or_surplus", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("is_on_track", sa.Boolean(), nullable=False),
        sa.Column("assumptions_statement", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_goals_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "goal_id", name="pk_goals"),
        schema="finex",
    )

    op.create_table(
        "goal_projections",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("projected_balance", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("contributions_total", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("growth_total", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_goal_projections_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "goal_id"],
            ["finex.goals.user_id", "finex.goals.goal_id"],
            name="fk_goal_projections_goal_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "goal_id", "year", name="pk_goal_projections"),
        schema="finex",
    )

    op.create_table(
        "spending_transactions",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("transaction_id", sa.Text(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description_masked", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=38, scale=18), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("is_user_corrected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_spending_transactions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "transaction_id", name="pk_spending_transactions"),
        schema="finex",
    )
    op.create_index(
        "ix_spending_transactions_user_date",
        "spending_transactions",
        ["user_id", "date"],
        unique=False,
        schema="finex",
    )

    op.create_table(
        "alert_rules",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=False),
        sa.Column("rule_name", sa.String(length=80), nullable=False),
        sa.Column("condition_type", sa.String(length=32), nullable=False),
        sa.Column("target_symbol_or_goal", sa.String(length=40), nullable=False),
        sa.Column("comparison_operator", sa.String(length=3), nullable=False),
        sa.Column("threshold_value", sa.Float(), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_alert_rules_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "rule_id", name="pk_alert_rules"),
        schema="finex",
    )

    op.create_table(
        "alerts",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("notification_id", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_alerts_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "rule_id"],
            ["finex.alert_rules.user_id", "finex.alert_rules.rule_id"],
            name="fk_alerts_rule_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "notification_id", name="pk_alerts"),
        schema="finex",
    )
    op.create_index(
        "ix_alerts_user_created_at",
        "alerts",
        ["user_id", "created_at"],
        unique=False,
        schema="finex",
    )
    op.create_index(
        "ix_alerts_user_is_read",
        "alerts",
        ["user_id", "is_read"],
        unique=False,
        schema="finex",
    )

    op.create_table(
        "privacy_requests",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("action", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("requested_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("download_url", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_privacy_requests_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "request_id", name="pk_privacy_requests"),
        schema="finex",
    )

    op.create_table(
        "consent_audit",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("consent_version", sa.String(length=50), nullable=False),
        sa.Column("granted_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("revoked_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "privacy_notice_url",
            sa.Text(),
            nullable=False,
            server_default="/docs/privacy-policy-v1.md",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_consent_audit_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id",
            "consent_version",
            "granted_at",
            name="pk_consent_audit",
        ),
        schema="finex",
    )


def downgrade() -> None:
    op.drop_table("consent_audit", schema="finex")
    op.drop_table("privacy_requests", schema="finex")
    op.drop_index(
        "ix_alerts_user_is_read",
        table_name="alerts",
        schema="finex",
    )
    op.drop_index(
        "ix_alerts_user_created_at",
        table_name="alerts",
        schema="finex",
    )
    op.drop_table("alerts", schema="finex")
    op.drop_table("alert_rules", schema="finex")
    op.drop_index(
        "ix_spending_transactions_user_date",
        table_name="spending_transactions",
        schema="finex",
    )
    op.drop_table("spending_transactions", schema="finex")
    op.drop_table("goal_projections", schema="finex")
    op.drop_table("goals", schema="finex")
