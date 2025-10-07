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
    # Add SQLite Parser Enrichment Fields (check if columns exist first)
    connection = op.get_bind()
    
    # Check if columns already exist
    columns_to_add = [
        ('auto_description', 'TEXT'),
        ('auto_description_short', 'VARCHAR(255)'),
        ('width_out', 'DOUBLE PRECISION'),
        ('width_unit', 'VARCHAR(50)'),
        ('height_out', 'DOUBLE PRECISION'),
        ('height_unit', 'VARCHAR(50)')
    ]
    
    for column_name, column_type in columns_to_add:
        # Check if column exists
        result = connection.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'elevations' 
                AND column_name = '{column_name}'
            );
        """))
        column_exists = result.scalar()
        
        if not column_exists:
            if column_name == 'auto_description':
                op.add_column('elevations', sa.Column('auto_description', sa.Text(), nullable=True, comment='AutoDescription from SQLite'))
            elif column_name == 'auto_description_short':
                op.add_column('elevations', sa.Column('auto_description_short', sa.String(255), nullable=True, comment='AutoDescriptionShort from SQLite'))
            elif column_name == 'width_out':
                op.add_column('elevations', sa.Column('width_out', sa.Float(), nullable=True, comment='Width_Out from SQLite'))
            elif column_name == 'width_unit':
                op.add_column('elevations', sa.Column('width_unit', sa.String(50), nullable=True, comment='Width_Unit from SQLite'))
            elif column_name == 'height_out':
                op.add_column('elevations', sa.Column('height_out', sa.Float(), nullable=True, comment='Heighth_Out from SQLite'))
            elif column_name == 'height_unit':
                op.add_column('elevations', sa.Column('height_unit', sa.String(50), nullable=True, comment='Heighth_Unit from SQLite'))
    # Add remaining columns if they don't exist
    remaining_columns = [
        ('weight_out', 'DOUBLE PRECISION'),
        ('weight_unit', 'VARCHAR(50)'),
        ('area_output', 'DOUBLE PRECISION'),
        ('area_unit', 'VARCHAR(50)'),
        ('system_code', 'VARCHAR(100)')
    ]
    
    for column_name, column_type in remaining_columns:
        result = connection.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'elevations' 
                AND column_name = '{column_name}'
            );
        """))
        column_exists = result.scalar()
        
        if not column_exists:
            if column_name == 'weight_out':
                op.add_column('elevations', sa.Column('weight_out', sa.Float(), nullable=True, comment='Weight_Out from SQLite'))
            elif column_name == 'weight_unit':
                op.add_column('elevations', sa.Column('weight_unit', sa.String(50), nullable=True, comment='Weight_Unit from SQLite'))
            elif column_name == 'area_output':
                op.add_column('elevations', sa.Column('area_output', sa.Float(), nullable=True, comment='Area_Output from SQLite'))
            elif column_name == 'area_unit':
                op.add_column('elevations', sa.Column('area_unit', sa.String(50), nullable=True, comment='Area_Unit from SQLite'))
            elif column_name == 'system_code':
                op.add_column('elevations', sa.Column('system_code', sa.String(100), nullable=True, comment='Systemcode from SQLite'))
    # Add final columns if they don't exist
    final_columns = [
        ('system_name', 'VARCHAR(255)'),
        ('system_long_name', 'VARCHAR(500)'),
        ('color_base_long', 'VARCHAR(255)'),
        ('parts_file_hash', 'VARCHAR(64)'),
        ('parse_status', 'VARCHAR(50)'),
        ('parse_error', 'TEXT'),
        ('parse_retry_count', 'INTEGER'),
        ('data_parsed_at', 'TIMESTAMP WITH TIME ZONE')
    ]
    
    for column_name, column_type in final_columns:
        result = connection.execute(sa.text(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'elevations' 
                AND column_name = '{column_name}'
            );
        """))
        column_exists = result.scalar()
        
        if not column_exists:
            if column_name == 'system_name':
                op.add_column('elevations', sa.Column('system_name', sa.String(255), nullable=True, comment='SystemName from SQLite'))
            elif column_name == 'system_long_name':
                op.add_column('elevations', sa.Column('system_long_name', sa.String(500), nullable=True, comment='SystemLongName from SQLite'))
            elif column_name == 'color_base_long':
                op.add_column('elevations', sa.Column('color_base_long', sa.String(255), nullable=True, comment='ColorBase_Long from SQLite'))
            elif column_name == 'parts_file_hash':
                op.add_column('elevations', sa.Column('parts_file_hash', sa.String(64), nullable=True, comment='SHA256 hash of SQLite file for change detection'))
            elif column_name == 'parse_status':
                op.add_column('elevations', sa.Column('parse_status', sa.String(50), nullable=False, server_default='pending', comment='Parse status: pending, in_progress, success, failed, partial, validation_failed'))
            elif column_name == 'parse_error':
                op.add_column('elevations', sa.Column('parse_error', sa.Text(), nullable=True, comment='Error message if parsing failed'))
            elif column_name == 'parse_retry_count':
                op.add_column('elevations', sa.Column('parse_retry_count', sa.Integer(), nullable=False, server_default='0', comment='Number of retry attempts'))
            elif column_name == 'data_parsed_at':
                op.add_column('elevations', sa.Column('data_parsed_at', sa.DateTime(timezone=True), nullable=True, comment='When SQLite data was parsed'))


def downgrade() -> None:
    """Downgrade schema."""
    pass
