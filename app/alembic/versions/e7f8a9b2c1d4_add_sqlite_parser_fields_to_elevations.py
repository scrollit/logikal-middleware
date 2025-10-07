"""add_sqlite_parser_fields_to_elevations

Revision ID: e7f8a9b2c1d4
Revises: cd593e24c151
Create Date: 2025-01-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7f8a9b2c1d4'
down_revision: Union[str, Sequence[str], None] = 'cd593e24c151'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new parsing fields to elevations table
    op.add_column('elevations', sa.Column('auto_description', sa.Text(), nullable=True, comment='AutoDescription from SQLite'))
    op.add_column('elevations', sa.Column('auto_description_short', sa.String(length=255), nullable=True, comment='AutoDescriptionShort from SQLite'))
    op.add_column('elevations', sa.Column('width_out', sa.Float(), nullable=True, comment='Width_Out from SQLite'))
    op.add_column('elevations', sa.Column('width_unit', sa.String(length=50), nullable=True, comment='Width_Unit from SQLite'))
    op.add_column('elevations', sa.Column('height_out', sa.Float(), nullable=True, comment='Heighth_Out from SQLite'))
    op.add_column('elevations', sa.Column('height_unit', sa.String(length=50), nullable=True, comment='Heighth_Unit from SQLite'))
    op.add_column('elevations', sa.Column('weight_out', sa.Float(), nullable=True, comment='Weight_Out from SQLite'))
    op.add_column('elevations', sa.Column('weight_unit', sa.String(length=50), nullable=True, comment='Weight_Unit from SQLite'))
    op.add_column('elevations', sa.Column('area_output', sa.Float(), nullable=True, comment='Area_Output from SQLite'))
    op.add_column('elevations', sa.Column('area_unit', sa.String(length=50), nullable=True, comment='Area_Unit from SQLite'))
    op.add_column('elevations', sa.Column('system_code', sa.String(length=100), nullable=True, comment='Systemcode from SQLite'))
    op.add_column('elevations', sa.Column('system_name', sa.String(length=255), nullable=True, comment='SystemName from SQLite'))
    op.add_column('elevations', sa.Column('system_long_name', sa.String(length=500), nullable=True, comment='SystemLongName from SQLite'))
    op.add_column('elevations', sa.Column('color_base_long', sa.String(length=255), nullable=True, comment='ColorBase_Long from SQLite'))
    
    # Add parsing metadata fields
    op.add_column('elevations', sa.Column('parts_file_hash', sa.String(length=64), nullable=True, comment='SHA256 hash of SQLite file for change detection'))
    op.add_column('elevations', sa.Column('parse_status', sa.String(length=50), nullable=False, default='pending', comment='Parse status: pending, in_progress, success, failed, partial, validation_failed'))
    op.add_column('elevations', sa.Column('parse_error', sa.Text(), nullable=True, comment='Error message if parsing failed'))
    op.add_column('elevations', sa.Column('parse_retry_count', sa.Integer(), nullable=False, default=0, comment='Number of retry attempts'))
    
    # Create parsing error logs table
    op.create_table('parsing_error_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('elevation_id', sa.Integer(), nullable=False),
        sa.Column('error_type', sa.String(length=100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['elevation_id'], ['elevations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_parsing_error_logs_id'), 'parsing_error_logs', ['id'], unique=False)
    op.create_index(op.f('ix_parsing_error_logs_elevation_id'), 'parsing_error_logs', ['elevation_id'], unique=False)
    
    # Create elevation glass table
    op.create_table('elevation_glass',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('elevation_id', sa.Integer(), nullable=False),
        sa.Column('glass_id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['elevation_id'], ['elevations.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_elevation_glass_id'), 'elevation_glass', ['id'], unique=False)
    op.create_index(op.f('ix_elevation_glass_elevation_id'), 'elevation_glass', ['elevation_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables
    op.drop_index(op.f('ix_elevation_glass_elevation_id'), table_name='elevation_glass')
    op.drop_index(op.f('ix_elevation_glass_id'), table_name='elevation_glass')
    op.drop_table('elevation_glass')
    
    op.drop_index(op.f('ix_parsing_error_logs_elevation_id'), table_name='parsing_error_logs')
    op.drop_index(op.f('ix_parsing_error_logs_id'), table_name='parsing_error_logs')
    op.drop_table('parsing_error_logs')
    
    # Drop columns from elevations table
    op.drop_column('elevations', 'parse_retry_count')
    op.drop_column('elevations', 'parse_error')
    op.drop_column('elevations', 'parse_status')
    op.drop_column('elevations', 'parts_file_hash')
    op.drop_column('elevations', 'color_base_long')
    op.drop_column('elevations', 'system_long_name')
    op.drop_column('elevations', 'system_name')
    op.drop_column('elevations', 'system_code')
    op.drop_column('elevations', 'area_unit')
    op.drop_column('elevations', 'area_output')
    op.drop_column('elevations', 'weight_unit')
    op.drop_column('elevations', 'weight_out')
    op.drop_column('elevations', 'height_unit')
    op.drop_column('elevations', 'height_out')
    op.drop_column('elevations', 'width_unit')
    op.drop_column('elevations', 'width_out')
    op.drop_column('elevations', 'auto_description_short')
    op.drop_column('elevations', 'auto_description')
