"""add_object_sync_config_table

Revision ID: f2a3b4c5d6e7
Revises: e7f8a9b2c1d4
Create Date: 2025-01-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e7f8a9b2c1d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create object_sync_configs table
    op.create_table('object_sync_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('object_type', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sync_interval_minutes', sa.Integer(), nullable=False),
        sa.Column('is_sync_enabled', sa.Boolean(), nullable=False),
        sa.Column('staleness_threshold_minutes', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('depends_on', sa.String(length=200), nullable=True),
        sa.Column('cascade_sync', sa.Boolean(), nullable=False),
        sa.Column('batch_size', sa.Integer(), nullable=False),
        sa.Column('max_retry_attempts', sa.Integer(), nullable=False),
        sa.Column('retry_delay_minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_sync', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempt', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_object_sync_configs_id'), 'object_sync_configs', ['id'], unique=False)
    op.create_index(op.f('ix_object_sync_configs_object_type'), 'object_sync_configs', ['object_type'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_object_sync_configs_object_type'), table_name='object_sync_configs')
    op.drop_index(op.f('ix_object_sync_configs_id'), table_name='object_sync_configs')
    
    # Drop table
    op.drop_table('object_sync_configs')
