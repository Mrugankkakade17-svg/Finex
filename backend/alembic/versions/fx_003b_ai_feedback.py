"""S1-MI01: persist AI feedback in operational schema.

Revision ID: s1mi01_ai_feedback
Revises: s1mr02_fx003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s1mi01_ai_feedback"
down_revision: Union[str, Sequence[str], None] = "s1mr02_fx003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_feedback",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("feedback_id", sa.Text(), nullable=False),
        sa.Column("message_id", sa.Text(), nullable=False),
        sa.Column("rating", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_ai_feedback_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "feedback_id", name="pk_ai_feedback"),
        schema="finex",
    )
    op.create_index(
        "ix_ai_feedback_user_created_at",
        "ai_feedback",
        ["user_id", "created_at"],
        unique=False,
        schema="finex",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ai_feedback_user_created_at",
        table_name="ai_feedback",
        schema="finex",
    )
    op.drop_table("ai_feedback", schema="finex")
