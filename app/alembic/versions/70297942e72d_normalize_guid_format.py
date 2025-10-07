"""normalize_guid_format

Revision ID: 70297942e72d
Revises: cd593e24c151
Create Date: 2025-09-29 21:57:30.883629

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70297942e72d'
down_revision: Union[str, Sequence[str], None] = 'cd593e24c151'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Update phases table: convert 32-character MD5 hashes to null GUID format
    op.execute("""
        UPDATE phases 
        SET logikal_id = '00000000-0000-0000-0000-000000000000' 
        WHERE LENGTH(logikal_id) = 32 AND logikal_id NOT LIKE '%-%'
    """)
    
    # Update elevations table: convert 32-character MD5 hashes to null GUID format
    op.execute("""
        UPDATE elevations 
        SET logikal_id = '00000000-0000-0000-0000-000000000000' 
        WHERE LENGTH(logikal_id) = 32 AND logikal_id NOT LIKE '%-%'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    pass
