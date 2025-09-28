from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from core.database import Base


class SyncConfig(Base):
    """Sync configuration model for managing sync settings"""
    __tablename__ = "sync_config"
    
    id = Column(Integer, primary_key=True, index=True)
    last_full_sync = Column(DateTime(timezone=True), nullable=True)
    last_incremental_sync = Column(DateTime(timezone=True), nullable=True)
    sync_interval_minutes = Column(Integer, default=60)
    is_sync_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SyncConfig(id={self.id}, last_full_sync={self.last_full_sync}, is_sync_enabled={self.is_sync_enabled})>"
