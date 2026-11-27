"""Merge the parallel auth, allocation, and paper order migration heads.

Revision ID: s3_merge_fx006_heads
Revises: s1li02_auth_persistence, s2mr02_fx007_merge
"""

from typing import Sequence, Union

revision: str = "s3_merge_fx006_heads"
down_revision: Union[str, Sequence[str], None] = (
    "s1li02_auth_persistence",
    "s2mr02_fx007_merge",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
