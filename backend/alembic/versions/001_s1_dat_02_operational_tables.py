"""S1-DAT-02 operational tables

Revision ID: s1dat02_001
Revises:
Create Date: 2026-08-21

Creates:
    finex.users
    finex.user_profiles
    finex.portfolio_holdings
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "s1dat02_001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create finex schema and S1-DAT-02 operational tables."""

    # Create the Postgres schema for operational data
    op.execute("CREATE SCHEMA IF NOT EXISTS finex")

    # -- users --
    op.create_table(
        "users",
        sa.Column("user_id", sa.Text(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(50), server_default="user"),
        sa.Column("risk_profile", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="finex",
    )

    # -- user_profiles --
    op.create_table(
        "user_profiles",
        sa.Column("profile_id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Text(), nullable=False, index=True),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="finex",
    )

    # -- portfolio_holdings --
    op.create_table(
        "portfolio_holdings",
        sa.Column("holding_id", sa.Text(), primary_key=True),
        sa.Column("portfolio_id", sa.Text(), nullable=False, index=True),
        sa.Column("user_id", sa.Text(), nullable=False, index=True),
        sa.Column("instrument_symbol", sa.String(20), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_buy_price", sa.Float(), nullable=False),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now()),
        schema="finex",
    )


def downgrade() -> None:
    """Drop S1-DAT-02 tables and schema."""
    op.drop_table("portfolio_holdings", schema="finex")
    op.drop_table("user_profiles", schema="finex")
    op.drop_table("users", schema="finex")
    op.execute("DROP SCHEMA IF EXISTS finex")
