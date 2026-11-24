"""Add a linear checkpoint after the fx_006 migration merge.

Revision ID: s3_fx006_checkpoint
Revises: s3_merge_fx006_heads
"""

from typing import Sequence, Union

revision: str = "s3_fx006_checkpoint"
down_revision: Union[str, Sequence[str], None] = "s3_merge_fx006_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
