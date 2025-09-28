from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class Phase(Base):
    """Phase model for storing Logikal phase information"""
    __tablename__ = "phases"
    
    id = Column(Integer, primary_key=True, index=True)
    logikal_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Smart sync tracking fields
    last_sync_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was synced from Logikal")
    last_update_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was modified in Logikal")
    
    # Relationships
    project = relationship("Project", backref="phases")
    
    def __repr__(self):
        return f"<Phase(id={self.id}, name='{self.name}', logikal_id='{self.logikal_id}')>"
