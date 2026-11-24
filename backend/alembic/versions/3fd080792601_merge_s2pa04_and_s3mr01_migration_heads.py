"""merge s2pa04 and s3mr01 migration heads

Revision ID: 3fd080792601
Revises: s2pa04_fx006, s3mr01_fx006
Create Date: 2026-11-24 15:06:59.030575

"""

from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "3fd080792601"
down_revision: Union[str, Sequence[str], None] = ("s2pa04_fx006", "s3mr01_fx006")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
