"""Merge the current S3-PA01 and S2-MR02 migration heads."""

from typing import Sequence, Union

revision: str = "s3_pa01_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "s3_fx006_checkpoint",
    "s2mr02_fx007_merge",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the already-applied migration branches without schema changes."""


def downgrade() -> None:
    """Remove only the merge point; both parent schemas remain intact."""
