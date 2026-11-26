"""Join the existing S3 checkpoint and S2 merge migration heads.

Revision ID: s3pa02_merge_heads
Revises: s3_fx006_checkpoint, s2mr02_fx007_merge
"""

from typing import Sequence, Union

revision: str = "s3pa02_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "s3_fx006_checkpoint",
    "s2mr02_fx007_merge",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the already-applied migration branches without changing schema."""


def downgrade() -> None:
    """Remove only this merge point; parent schema changes remain intact."""
