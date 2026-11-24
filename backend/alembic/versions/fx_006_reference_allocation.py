"""S3-MR01 fx_006: allocation model and benchmark reference data.

Revision ID: s3mr01_fx006
Revises: s2mr01_fx005
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "s3mr01_fx006"
down_revision: Union[str, Sequence[str], None] = "s2mr01_fx005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "allocation_models",
        sa.Column("model_code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("risk_category", sa.String(length=16), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "risk_category IN ('CONSERVATIVE', 'MODERATE', 'AGGRESSIVE')",
            name="ck_allocation_models_risk_category",
        ),
        sa.PrimaryKeyConstraint("model_code", name="pk_allocation_models"),
        sa.UniqueConstraint(
            "risk_category", "version", name="uq_allocation_models_category_version"
        ),
        schema="finex",
    )
    op.create_table(
        "allocation_model_targets",
        sa.Column("model_code", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("target_weight", sa.Numeric(precision=8, scale=6), nullable=False),
        sa.CheckConstraint(
            "asset_class IN ('EQUITY', 'FIXED_INCOME', 'CASH')",
            name="ck_allocation_targets_asset_class",
        ),
        sa.CheckConstraint(
            "target_weight >= 0 AND target_weight <= 1",
            name="ck_allocation_targets_weight_range",
        ),
        sa.ForeignKeyConstraint(
            ["model_code"],
            ["finex.allocation_models.model_code"],
            name="fk_allocation_targets_model",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("model_code", "asset_class", name="pk_allocation_model_targets"),
        schema="finex",
    )
    op.create_table(
        "benchmark_map",
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("benchmark_symbol", sa.String(length=20), nullable=False),
        sa.Column("benchmark_name", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("source_type", sa.String(length=16), nullable=False, server_default="SYNTHETIC"),
        sa.CheckConstraint(
            "asset_class IN ('EQUITY', 'FIXED_INCOME', 'CASH')",
            name="ck_benchmark_map_asset_class",
        ),
        sa.CheckConstraint("currency = 'USD'", name="ck_benchmark_map_currency_usd"),
        sa.CheckConstraint("source_type = 'SYNTHETIC'", name="ck_benchmark_map_source_synthetic"),
        sa.PrimaryKeyConstraint("asset_class", "version", name="pk_benchmark_map"),
        sa.UniqueConstraint("benchmark_symbol", "version", name="uq_benchmark_map_symbol_version"),
        schema="finex",
    )


def downgrade() -> None:
    op.drop_table("benchmark_map", schema="finex")
    op.drop_table("allocation_model_targets", schema="finex")
    op.drop_table("allocation_models", schema="finex")
