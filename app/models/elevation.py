from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class Elevation(Base):
    """Elevation model for storing Logikal elevation information"""
    __tablename__ = "elevations"
    
    id = Column(Integer, primary_key=True, index=True)
    logikal_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    phase_id = Column(Integer, ForeignKey("phases.id"), nullable=True)  # Phase database ID
    thumbnail_url = Column(String(500), nullable=True)
    thumbnail_data = Column(Text, nullable=True)  # Base64 encoded thumbnail
    image_path = Column(String(500), nullable=True)  # Local path to downloaded image
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    depth = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Smart sync tracking fields
    last_sync_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was synced from Logikal")
    last_update_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was modified in Logikal")
    # Basic sync tracking fields
    synced_at = Column(DateTime(timezone=True), nullable=True, comment="Last sync timestamp")
    sync_status = Column(String(50), default='pending', nullable=False, comment="Sync status: pending, synced, error")
    
    # Parts/Components (from parts-list endpoint)
    parts_data = Column(Text, nullable=True, comment="Base64-encoded SQLite database from parts-list API")
    parts_db_path = Column(String(500), nullable=True, comment="Local filesystem path to extracted SQLite file")
    parts_count = Column(Integer, nullable=True, comment="Number of parts/components")
    has_parts_data = Column(Boolean, default=False, nullable=False, comment="Whether parts list has been fetched")
    parts_synced_at = Column(DateTime(timezone=True), nullable=True, comment="Timestamp of last parts sync")
    
    # SQLite Parser Enrichment Fields (from Elevations table in SQLite)
    auto_description = Column(Text, nullable=True, comment="AutoDescription from SQLite")
    auto_description_short = Column(String(255), nullable=True, comment="AutoDescriptionShort from SQLite")
    width_out = Column(Float, nullable=True, comment="Width_Out from SQLite")
    width_unit = Column(String(50), nullable=True, comment="Width_Unit from SQLite")
    height_out = Column(Float, nullable=True, comment="Heighth_Out from SQLite")
    height_unit = Column(String(50), nullable=True, comment="Heighth_Unit from SQLite")
    weight_out = Column(Float, nullable=True, comment="Weight_Out from SQLite")
    weight_unit = Column(String(50), nullable=True, comment="Weight_Unit from SQLite")
    area_output = Column(Float, nullable=True, comment="Area_Output from SQLite")
    area_unit = Column(String(50), nullable=True, comment="Area_Unit from SQLite")
    system_code = Column(String(100), nullable=True, comment="Systemcode from SQLite")
    system_name = Column(String(255), nullable=True, comment="SystemName from SQLite")
    system_long_name = Column(String(500), nullable=True, comment="SystemLongName from SQLite")
    color_base_long = Column(String(255), nullable=True, comment="ColorBase_Long from SQLite")
    
    # Parsing metadata
    parts_file_hash = Column(String(64), nullable=True, comment="SHA256 hash of SQLite file for change detection")
    parse_status = Column(String(50), default='pending', nullable=False, comment="Parse status: pending, in_progress, success, failed, partial, validation_failed")
    parse_error = Column(Text, nullable=True, comment="Error message if parsing failed")
    parse_retry_count = Column(Integer, default=0, nullable=False, comment="Number of retry attempts")
    data_parsed_at = Column(DateTime(timezone=True), nullable=True, comment="When SQLite data was parsed")
    
    # Relationships
    project = relationship("Project", backref="elevations")
    phase = relationship("Phase", backref="elevations")
    glass_specifications = relationship("ElevationGlass", cascade="all, delete-orphan")
    parsing_errors = relationship("ParsingErrorLog", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Elevation(id={self.id}, name='{self.name}', logikal_id='{self.logikal_id}')>"
    
    def calculate_data_quality_score(self):
        """Calculate data quality score based on available enrichment data"""
        score = 0.0
        max_score = 0.0
        
        # Basic data (always available)
        max_score += 20
        if self.name:
            score += 10
        if self.description:
            score += 10
        
        # SQLite enrichment data (40 points total)
        max_score += 40
        if self.auto_description:
            score += 10
        if self.auto_description_short:
            score += 5
        if self.width_out and self.width_unit:
            score += 5
        if self.height_out and self.height_unit:
            score += 5
        if self.weight_out and self.weight_unit:
            score += 5
        if self.area_output and self.area_unit:
            score += 5
        if self.system_code and self.system_name:
            score += 5
        
        # Parts data (20 points)
        max_score += 20
        if self.has_parts_data:
            score += 10
        if self.parts_count and self.parts_count > 0:
            score += 10
        
        # Glass specifications (10 points)
        max_score += 10
        if self.glass_specifications:
            score += 10
        
        # Parse status bonus (10 points)
        max_score += 10
        if self.parse_status == 'success':
            score += 10
        elif self.parse_status == 'partial':
            score += 5
        
        # Return score as percentage
        return round((score / max_score) * 100, 1) if max_score > 0 else 0.0