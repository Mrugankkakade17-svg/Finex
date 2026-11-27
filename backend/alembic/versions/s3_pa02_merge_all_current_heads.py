"""Merge all migration heads present in the current dev base and S3-PA02."""

from typing import Sequence, Union

revision: str = "s3pa02_all_heads"
down_revision: Union[str, Sequence[str], None] = (
    "s2pa06_watchlists",
    "s3_pa01_merge_heads",
    "s3pa02_merge_heads",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the current migration branches without changing the schema."""


def downgrade() -> None:
    """Remove only the merge point; parent schema changes remain intact."""
