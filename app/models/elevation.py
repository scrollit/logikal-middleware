from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
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
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    phase_id = Column(String(255), nullable=True)  # Phase identifier from Logikal
    thumbnail_url = Column(String(500), nullable=True)
    thumbnail_data = Column(Text, nullable=True)  # Base64 encoded thumbnail
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    depth = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Smart sync tracking fields
    last_sync_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was synced from Logikal")
    last_update_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was modified in Logikal")
    
    # Relationships
    project = relationship("Project", backref="elevations")
    
    def __repr__(self):
        return f"<Elevation(id={self.id}, name='{self.name}', logikal_id='{self.logikal_id}')>"
