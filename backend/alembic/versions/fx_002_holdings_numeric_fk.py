"""S1-MR01 fx_002: enforce numeric holdings and foreign keys.

Revision ID: s1mr01_fx002
Revises: s1mr01_fx001
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "s1mr01_fx002"
down_revision: Union[str, Sequence[str], None] = "s1mr01_fx001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "portfolio_holdings",
        "quantity",
        existing_type=sa.Float(),
        type_=sa.Numeric(precision=38, scale=18),
        nullable=False,
        postgresql_using="quantity::numeric",
        schema="finex",
    )

    op.create_foreign_key(
        "fk_portfolio_holdings_portfolio_id_portfolios",
        "portfolio_holdings",
        "portfolios",
        ["portfolio_id"],
        ["portfolio_id"],
        source_schema="finex",
        referent_schema="finex",
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_portfolio_holdings_user_id_users",
        "portfolio_holdings",
        "users",
        ["user_id"],
        ["user_id"],
        source_schema="finex",
        referent_schema="finex",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_portfolio_holdings_user_id_users",
        "portfolio_holdings",
        type_="foreignkey",
        schema="finex",
    )
    op.drop_constraint(
        "fk_portfolio_holdings_portfolio_id_portfolios",
        "portfolio_holdings",
        type_="foreignkey",
        schema="finex",
    )
    op.alter_column(
        "portfolio_holdings",
        "quantity",
        existing_type=sa.Numeric(precision=38, scale=18),
        type_=sa.Float(),
        nullable=False,
        postgresql_using="quantity::double precision",
        schema="finex",
    )
