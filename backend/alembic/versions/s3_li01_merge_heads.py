"""Merge the S2-PA06 watchlists and S3-PA01 analytics migration heads.

Revision ID: s3_li01_merge_heads
Revises: s2pa06_watchlists, s3_pa01_merge_heads
"""

from typing import Sequence, Union

revision: str = "s3_li01_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "s2pa06_watchlists",
    "s3_pa01_merge_heads",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the watchlists and analytics migration heads without schema changes."""
    pass


def downgrade() -> None:
    """Remove only the merge point; both parent schemas remain intact."""
    pass
