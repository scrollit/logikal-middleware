from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func
from core.database import Base


class SyncLog(Base):
    """Sync operation log model for tracking sync activities"""
    __tablename__ = "sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    sync_type = Column(String(50), nullable=False)  # 'full', 'incremental', 'directory', 'project', 'phase', 'elevation'
    status = Column(String(50), nullable=False)  # 'started', 'completed', 'failed', 'cancelled'
    message = Column(Text, nullable=True)
    items_processed = Column(Integer, default=0)
    items_successful = Column(Integer, default=0)
    items_failed = Column(Integer, default=0)
    duration_seconds = Column(Integer, nullable=True)
    error_details = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self):
        return f"<SyncLog(id={self.id}, sync_type={self.sync_type}, status={self.status}, items_processed={self.items_processed})>"
