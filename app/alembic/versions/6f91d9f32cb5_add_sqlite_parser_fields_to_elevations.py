"""add_sqlite_parser_fields_to_elevations

Revision ID: 6f91d9f32cb5
Revises: 70297942e72d
Create Date: 2025-10-01 20:22:04.875372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6f91d9f32cb5'
down_revision: Union[str, Sequence[str], None] = '70297942e72d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add SQLite Parser Enrichment Fields
    op.add_column('elevations', sa.Column('auto_description', sa.Text(), nullable=True, comment='AutoDescription from SQLite'))
    op.add_column('elevations', sa.Column('auto_description_short', sa.String(255), nullable=True, comment='AutoDescriptionShort from SQLite'))
    op.add_column('elevations', sa.Column('width_out', sa.Float(), nullable=True, comment='Width_Out from SQLite'))
    op.add_column('elevations', sa.Column('width_unit', sa.String(50), nullable=True, comment='Width_Unit from SQLite'))
    op.add_column('elevations', sa.Column('height_out', sa.Float(), nullable=True, comment='Heighth_Out from SQLite'))
    op.add_column('elevations', sa.Column('height_unit', sa.String(50), nullable=True, comment='Heighth_Unit from SQLite'))
    op.add_column('elevations', sa.Column('weight_out', sa.Float(), nullable=True, comment='Weight_Out from SQLite'))
    op.add_column('elevations', sa.Column('weight_unit', sa.String(50), nullable=True, comment='Weight_Unit from SQLite'))
    op.add_column('elevations', sa.Column('area_output', sa.Float(), nullable=True, comment='Area_Output from SQLite'))
    op.add_column('elevations', sa.Column('area_unit', sa.String(50), nullable=True, comment='Area_Unit from SQLite'))
    op.add_column('elevations', sa.Column('system_code', sa.String(100), nullable=True, comment='Systemcode from SQLite'))
    op.add_column('elevations', sa.Column('system_name', sa.String(255), nullable=True, comment='SystemName from SQLite'))
    op.add_column('elevations', sa.Column('system_long_name', sa.String(500), nullable=True, comment='SystemLongName from SQLite'))
    op.add_column('elevations', sa.Column('color_base_long', sa.String(255), nullable=True, comment='ColorBase_Long from SQLite'))
    
    # Add parsing metadata fields
    op.add_column('elevations', sa.Column('parts_file_hash', sa.String(64), nullable=True, comment='SHA256 hash of SQLite file for change detection'))
    op.add_column('elevations', sa.Column('parse_status', sa.String(50), nullable=False, server_default='pending', comment='Parse status: pending, in_progress, success, failed, partial, validation_failed'))
    op.add_column('elevations', sa.Column('parse_error', sa.Text(), nullable=True, comment='Error message if parsing failed'))
    op.add_column('elevations', sa.Column('parse_retry_count', sa.Integer(), nullable=False, server_default='0', comment='Number of retry attempts'))
    op.add_column('elevations', sa.Column('data_parsed_at', sa.DateTime(timezone=True), nullable=True, comment='When SQLite data was parsed'))


def downgrade() -> None:
    """Downgrade schema."""
    pass
