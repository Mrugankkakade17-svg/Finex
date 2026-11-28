"""Persist one portfolio valuation per UTC calendar day.

Revision ID: s3pa03_daily_snapshots
Revises: s3_pa06_merge_heads
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

from alembic import op

revision: str = "s3pa03_daily_snapshots"
down_revision: Union[str, Sequence[str], None] = "s3_pa06_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_daily_snapshots",
        sa.Column("portfolio_id", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_value", sa.Numeric(precision=38, scale=8), nullable=False),
        sa.Column("total_cost", sa.Numeric(precision=38, scale=8), nullable=False),
        sa.Column("total_gain_loss", sa.Numeric(precision=38, scale=8), nullable=False),
        sa.Column("total_gain_loss_pct", sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column("holdings_count", sa.Integer(), nullable=False),
        sa.Column("data_status", sa.String(length=16), nullable=False),
        sa.Column("snapshot_data", JSONB(), nullable=False),
        sa.Column(
            "captured_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("total_value >= 0", name="ck_portfolio_snapshot_value_nonnegative"),
        sa.CheckConstraint("total_cost >= 0", name="ck_portfolio_snapshot_cost_nonnegative"),
        sa.CheckConstraint(
            "holdings_count >= 0", name="ck_portfolio_snapshot_holdings_nonnegative"
        ),
        sa.CheckConstraint(
            "data_status IN ('LIVE', 'DELAYED', 'END_OF_DAY', 'CACHED', 'UNAVAILABLE')",
            name="ck_portfolio_snapshot_data_status",
        ),
        sa.PrimaryKeyConstraint(
            "portfolio_id", "snapshot_date", name="pk_portfolio_daily_snapshots"
        ),
        schema="finex",
    )
    op.create_index(
        "ix_portfolio_daily_snapshots_user_date",
        "portfolio_daily_snapshots",
        ["user_id", "snapshot_date"],
        schema="finex",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_portfolio_daily_snapshots_user_date",
        table_name="portfolio_daily_snapshots",
        schema="finex",
    )
    op.drop_table("portfolio_daily_snapshots", schema="finex")
