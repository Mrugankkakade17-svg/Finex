"""merge: unify S1 operational and S2 risk migration heads

Revision ID: c9e7b5a2566a
Revises: s1dat02_001, 3ac24ffd069f
Create Date: 2026-08-24 19:34:58.519355

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "c9e7b5a2566a"
down_revision: Union[str, Sequence[str], None] = ("s1dat02_001", "3ac24ffd069f")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
