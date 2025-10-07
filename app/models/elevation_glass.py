from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class ElevationGlass(Base):
    """Glass specifications for elevations from SQLite Glass table"""
    __tablename__ = "elevation_glass"
    
    id = Column(Integer, primary_key=True, index=True)
    elevation_id = Column(Integer, ForeignKey("elevations.id"), nullable=False)
    glass_id = Column(String(100), nullable=False, comment="GlassID from SQLite")
    name = Column(String(255), nullable=True, comment="Name from SQLite")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    elevation = relationship("Elevation", overlaps="glass_specifications")
    
    def __repr__(self):
        return f"<ElevationGlass(id={self.id}, elevation_id={self.elevation_id}, glass_id='{self.glass_id}', name='{self.name}')>"
