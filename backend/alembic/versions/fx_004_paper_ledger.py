"""S2-MR01 fx_004: create owned paper cash accounts and ledger entries.

Revision ID: s2mr01_fx004
Revises: s1mi01_ai_feedback
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s2mr01_fx004"
down_revision: Union[str, Sequence[str], None] = "s1mi01_ai_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("currency = 'USD'", name="ck_paper_accounts_currency_usd"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["finex.users.user_id"],
            name="fk_paper_accounts_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("account_id", name="pk_paper_accounts"),
        sa.UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
        sa.UniqueConstraint("account_id", "user_id", name="uq_paper_accounts_id_user"),
        schema="finex",
    )

    op.create_table(
        "paper_ledger",
        sa.Column("ledger_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("cash_delta_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("cash_delta_cents <> 0", name="ck_paper_ledger_nonzero_delta"),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["finex.paper_accounts.account_id", "finex.paper_accounts.user_id"],
            name="fk_paper_ledger_account_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("ledger_id", name="pk_paper_ledger"),
        schema="finex",
    )
    op.create_index(
        "ix_paper_ledger_account_created",
        "paper_ledger",
        ["account_id", "created_at", "ledger_id"],
        schema="finex",
    )


def downgrade() -> None:
    op.drop_index("ix_paper_ledger_account_created", table_name="paper_ledger", schema="finex")
    op.drop_table("paper_ledger", schema="finex")
    op.drop_table("paper_accounts", schema="finex")

