"""S3-LI02: Add goal_contributions table and optional target_date on goals.

Revision ID: s3li02_goal_contributions
Revises: s3pa03_daily_snapshots
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s3li02_goal_contributions"
down_revision: Union[str, Sequence[str], None] = "s3pa03_daily_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "goals",
        sa.Column("target_date", sa.Date(), nullable=True),
        schema="finex",
    )

    op.create_table(
        "goal_contributions",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("goal_id", sa.Text(), nullable=False),
        sa.Column("contribution_id", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=20, scale=4), nullable=False),
        sa.Column("contribution_date", sa.Date(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("amount > 0", name="ck_goal_contributions_amount_positive"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_goal_contributions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "goal_id"],
            ["finex.goals.user_id", "finex.goals.goal_id"],
            name="fk_goal_contributions_goal_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "goal_id", "contribution_id", name="pk_goal_contributions"
        ),
        schema="finex",
    )
    op.create_index(
        "ix_goal_contributions_user_goal_date",
        "goal_contributions",
        ["user_id", "goal_id", "contribution_date"],
        unique=False,
        schema="finex",
    )
    op.create_index(
        "ix_goal_contributions_user_created_at",
        "goal_contributions",
        ["user_id", "created_at"],
        unique=False,
        schema="finex",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_goal_contributions_user_created_at",
        table_name="goal_contributions",
        schema="finex",
    )
    op.drop_index(
        "ix_goal_contributions_user_goal_date",
        table_name="goal_contributions",
        schema="finex",
    )
    op.drop_table("goal_contributions", schema="finex")
    op.drop_column("goals", "target_date", schema="finex")
