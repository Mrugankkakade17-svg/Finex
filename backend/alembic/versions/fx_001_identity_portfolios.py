"""S1-MR01 fx_001: identity and portfolio foundation.

Revision ID: s1mr01_fx001
Revises: c9e7b5a2566a
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s1mr01_fx001"
down_revision: Union[str, Sequence[str], None] = "c9e7b5a2566a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS finex")

    op.create_table(
        "portfolios",
        sa.Column("portfolio_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("portfolio_type", sa.String(length=50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_portfolios_user_id_users",
            ondelete="CASCADE",
        ),
        schema="finex",
    )
    op.create_index(
        "ix_finex_portfolios_user_id",
        "portfolios",
        ["user_id"],
        unique=False,
        schema="finex",
    )

    op.create_foreign_key(
        "fk_user_profiles_user_id_users",
        "user_profiles",
        "users",
        ["user_id"],
        ["user_id"],
        source_schema="finex",
        referent_schema="finex",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_user_profiles_user_id_users",
        "user_profiles",
        type_="foreignkey",
        schema="finex",
    )
    op.drop_index(
        "ix_finex_portfolios_user_id",
        table_name="portfolios",
        schema="finex",
    )
    op.drop_table("portfolios", schema="finex")
