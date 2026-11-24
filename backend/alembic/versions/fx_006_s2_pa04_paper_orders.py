"""S2-PA04: persist idempotent paper orders and current positions.

Revision ID: s2pa04_fx006
Revises: s2mr01_fx005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TIMESTAMP

from alembic import op

revision: str = "s2pa04_fx006"
down_revision: Union[str, Sequence[str], None] = "s2mr01_fx005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "paper_orders",
        sa.Column("order_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("instrument_id", sa.String(length=20), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("executed_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("notional_cents", sa.BigInteger(), nullable=False),
        sa.Column("fee_cents", sa.BigInteger(), nullable=False),
        sa.Column("cash_delta_cents", sa.BigInteger(), nullable=False),
        sa.Column("quote_freshness", sa.String(length=16), nullable=False),
        sa.Column("quote_as_of", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("side IN ('BUY', 'SELL')", name="ck_paper_orders_side"),
        sa.CheckConstraint("quantity > 0", name="ck_paper_orders_quantity_positive"),
        sa.CheckConstraint("executed_price > 0", name="ck_paper_orders_price_positive"),
        sa.CheckConstraint("notional_cents > 0", name="ck_paper_orders_notional_positive"),
        sa.CheckConstraint("fee_cents >= 0", name="ck_paper_orders_fee_nonnegative"),
        sa.CheckConstraint("cash_delta_cents <> 0", name="ck_paper_orders_cash_delta_nonzero"),
        sa.CheckConstraint(
            "quote_freshness IN ('LIVE', 'DELAYED', 'CACHED')",
            name="ck_paper_orders_eligible_quote",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["finex.paper_accounts.account_id", "finex.paper_accounts.user_id"],
            name="fk_paper_orders_account_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("order_id", name="pk_paper_orders"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_paper_orders_user_idempotency"),
        schema="finex",
    )
    op.create_index(
        "ix_paper_orders_account_created",
        "paper_orders",
        ["account_id", "created_at", "order_id"],
        schema="finex",
    )

    op.create_table(
        "paper_positions",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("instrument_id", sa.String(length=20), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.BigInteger(), nullable=False),
        sa.Column("average_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("last_price", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "updated_at",
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("quantity > 0", name="ck_paper_positions_quantity_positive"),
        sa.CheckConstraint("average_cost > 0", name="ck_paper_positions_cost_positive"),
        sa.CheckConstraint("last_price > 0", name="ck_paper_positions_price_positive"),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["finex.paper_accounts.account_id", "finex.paper_accounts.user_id"],
            name="fk_paper_positions_account_owner",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "account_id", "instrument_id", "exchange", name="pk_paper_positions"
        ),
        schema="finex",
    )


def downgrade() -> None:
    op.drop_table("paper_positions", schema="finex")
    op.drop_index("ix_paper_orders_account_created", table_name="paper_orders", schema="finex")
    op.drop_table("paper_orders", schema="finex")
