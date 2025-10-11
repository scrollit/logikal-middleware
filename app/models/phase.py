from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class Phase(Base):
    """Phase model for storing Logikal phase information"""
    __tablename__ = "phases"
    
    id = Column(Integer, primary_key=True, index=True)
    logikal_id = Column(String(255), nullable=True, index=True)  # Allow null values
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    status = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    # Smart sync tracking fields
    last_sync_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was synced from Logikal")
    last_update_date = Column(DateTime(timezone=True), nullable=True, comment="Last time data was modified in Logikal")
    # Basic sync tracking fields
    synced_at = Column(DateTime(timezone=True), nullable=True, comment="Last sync timestamp")
    sync_status = Column(String(50), default='pending', nullable=False, comment="Sync status: pending, synced, error")
    
    # Relationships
    project = relationship("Project", backref="phases")
    
    # Composite unique constraint: allow multiple null logikal_ids but ensure uniqueness when combined with project_id
    __table_args__ = (
        UniqueConstraint('logikal_id', 'project_id', name='uq_phase_logikal_project'),
    )
    
    def __repr__(self):
        return f"<Phase(id={self.id}, name='{self.name}', logikal_id='{self.logikal_id}')>"
