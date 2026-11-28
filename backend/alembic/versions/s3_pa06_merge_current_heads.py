"""Merge the watchlist and current S3-PA01 migration heads."""

from typing import Sequence, Union

revision: str = "s3_pa06_merge_heads"
down_revision: Union[str, Sequence[str], None] = (
    "s2pa06_watchlists",
    "s3_pa01_merge_heads",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the current migration branches without changing the schema."""


def downgrade() -> None:
    """Remove only the merge point; both parent schemas remain intact."""
