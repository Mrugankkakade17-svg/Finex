"""S1-LI02 fx_006: persist Google OAuth metadata and shared failed login tracking.

Revision ID: s1li02_auth_persistence
Revises: s2mr01_fx005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s1li02_auth_persistence"
down_revision: Union[str, Sequence[str], None] = "s2mr01_fx005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add google_id and picture columns to finex.users
    op.add_column(
        "users",
        sa.Column("google_id", sa.String(length=255), nullable=True),
        schema="finex",
    )
    op.create_index(
        "ix_finex_users_google_id",
        "users",
        ["google_id"],
        unique=True,
        schema="finex",
        postgresql_where=sa.text("google_id IS NOT NULL"),
    )
    op.add_column(
        "users",
        sa.Column("picture", sa.Text(), nullable=True),
        schema="finex",
    )

    # 2. Create finex.failed_logins table for multi-worker failed login rate-limiting
    op.create_table(
        "failed_logins",
        sa.Column("email", sa.String(length=320), primary_key=True),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "first_attempt_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_attempt_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        schema="finex",
    )
    op.create_index(
        "ix_finex_failed_logins_first_attempt",
        "failed_logins",
        ["first_attempt_at"],
        unique=False,
        schema="finex",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_finex_failed_logins_first_attempt",
        table_name="failed_logins",
        schema="finex",
    )
    op.drop_table("failed_logins", schema="finex")
    op.drop_index(
        "ix_finex_users_google_id",
        table_name="users",
        schema="finex",
    )
    op.drop_column("users", "picture", schema="finex")
    op.drop_column("users", "google_id", schema="finex")
