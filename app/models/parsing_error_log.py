from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class ParsingErrorLog(Base):
    """Detailed error logging for parsing failures"""
    __tablename__ = "parsing_error_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    elevation_id = Column(Integer, ForeignKey("elevations.id"), nullable=False)
    error_type = Column(String(100), nullable=False, comment="validation, parsing, database, etc.")
    error_message = Column(Text, nullable=False)
    error_details = Column(JSON, nullable=True, comment="Stack trace, file info, etc.")
    retry_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    elevation = relationship("Elevation", overlaps="parsing_errors")
    
    def __repr__(self):
        return f"<ParsingErrorLog(id={self.id}, elevation_id={self.elevation_id}, error_type='{self.error_type}', created_at='{self.created_at}')>"
