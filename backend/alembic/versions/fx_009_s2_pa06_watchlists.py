"""S2-PA06: Add Postgres-backed watchlist and watchlist_items tables.

Revision ID: s2pa06_watchlists
Revises: s3_fx006_checkpoint
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s2pa06_watchlists"
down_revision: Union[str, Sequence[str], None] = "s3_fx006_checkpoint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "watchlists",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("watchlist_id", sa.Text(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_watchlists_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "watchlist_id", name="pk_watchlists"),
        sa.UniqueConstraint("watchlist_id", name="uq_watchlists_watchlist_id"),
        schema="finex",
    )
    op.create_index(
        "ix_watchlists_user_id_created_at",
        "watchlists",
        ["user_id", "created_at"],
        unique=False,
        schema="finex",
    )

    op.create_table(
        "watchlist_items",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("watchlist_id", sa.Text(), nullable=False),
        sa.Column("instrument_id", sa.String(length=32), nullable=False),
        sa.Column("added_at", TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_watchlist_items_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "watchlist_id"],
            ["finex.watchlists.user_id", "finex.watchlists.watchlist_id"],
            name="fk_watchlist_items_watchlist_owner",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("watchlist_id", "instrument_id", name="pk_watchlist_items"),
        schema="finex",
    )
    op.create_index(
        "ix_watchlist_items_user_id_watchlist_id",
        "watchlist_items",
        ["user_id", "watchlist_id"],
        unique=False,
        schema="finex",
    )


def downgrade() -> None:
    op.drop_table("watchlist_items", schema="finex")
    op.drop_table("watchlists", schema="finex")
