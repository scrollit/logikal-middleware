"""merge sqlite parser migration

Revision ID: a3459956e10d
Revises: 6f91d9f32cb5, e7f8a9b2c1d4
Create Date: 2025-10-01 21:02:06.221320

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3459956e10d'
down_revision: Union[str, Sequence[str], None] = ('6f91d9f32cb5', 'e7f8a9b2c1d4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
