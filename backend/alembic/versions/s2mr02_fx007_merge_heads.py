"""Merge S2-PA04 paper orders and S3-MR01 allocation revisions."""

from typing import Sequence, Union

revision: str = "s2mr02_fx007_merge"
down_revision: Union[str, Sequence[str], None] = (
    "s3mr01_fx006",
    "s2pa04_fx006",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Join the parallel allocation and paper order migration branches."""


def downgrade() -> None:
    """Remove only the merge point; both parent schemas remain intact."""
