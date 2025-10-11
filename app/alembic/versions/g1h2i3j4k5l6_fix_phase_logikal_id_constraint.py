"""Fix phase logikal_id constraint to allow multiple null values

Revision ID: g1h2i3j4k5l6
Revises: f2a3b4c5d6e7
Create Date: 2025-10-11 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix the phase table to allow multiple null logikal_id values.
    - Remove the unique constraint on logikal_id
    - Add a composite unique constraint on (logikal_id, project_id)
    - Allow logikal_id to be nullable
    """
    
    # First, drop the existing unique constraint on logikal_id
    try:
        op.drop_constraint('ix_phases_logikal_id', 'phases', type_='unique')
    except Exception:
        # Constraint might not exist or have a different name
        pass
    
    # Make logikal_id nullable
    op.alter_column('phases', 'logikal_id',
                   existing_type=sa.String(255),
                   nullable=True)
    
    # Add composite unique constraint that allows multiple null values
    op.create_unique_constraint('uq_phase_logikal_project', 'phases', ['logikal_id', 'project_id'])


def downgrade():
    """
    Revert the changes - restore the unique constraint on logikal_id only.
    """
    
    # Drop the composite unique constraint
    op.drop_constraint('uq_phase_logikal_project', 'phases', type_='unique')
    
    # Make logikal_id non-nullable again
    op.alter_column('phases', 'logikal_id',
                   existing_type=sa.String(255),
                   nullable=False)
    
    # Restore the unique constraint on logikal_id
    op.create_unique_constraint('ix_phases_logikal_id', 'phases', ['logikal_id'])
