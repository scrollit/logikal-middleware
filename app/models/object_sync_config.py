from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class ObjectSyncConfig(Base):
    """Configuration model for per-object-type sync intervals and settings"""
    __tablename__ = "object_sync_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    object_type = Column(String(50), nullable=False, unique=True, index=True)  # directory, project, phase, elevation
    display_name = Column(String(100), nullable=False)  # Human-readable name
    description = Column(Text, nullable=True)  # Description of what this object type represents
    
    # Sync interval settings
    sync_interval_minutes = Column(Integer, default=60, nullable=False)  # Default sync interval in minutes
    is_sync_enabled = Column(Boolean, default=True, nullable=False)  # Whether sync is enabled for this object type
    
    # Staleness detection settings
    staleness_threshold_minutes = Column(Integer, default=120, nullable=False)  # When to consider data stale
    priority = Column(Integer, default=1, nullable=False)  # Sync priority (1=highest, 5=lowest)
    
    # Dependency settings
    depends_on = Column(String(200), nullable=True)  # Comma-separated list of object types this depends on
    cascade_sync = Column(Boolean, default=True, nullable=False)  # Whether to sync dependent objects
    
    # Advanced settings
    batch_size = Column(Integer, default=100, nullable=False)  # Batch size for bulk operations
    max_retry_attempts = Column(Integer, default=3, nullable=False)  # Max retry attempts on failure
    retry_delay_minutes = Column(Integer, default=5, nullable=False)  # Delay between retry attempts
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_sync = Column(DateTime(timezone=True), nullable=True)  # Last successful sync timestamp
    last_attempt = Column(DateTime(timezone=True), nullable=True)  # Last sync attempt timestamp
    
    def __repr__(self):
        return f"<ObjectSyncConfig(object_type='{self.object_type}', interval={self.sync_interval_minutes}min, enabled={self.is_sync_enabled})>"
    
    def get_dependencies(self):
        """Get list of object types this config depends on"""
        if not self.depends_on:
            return []
        return [dep.strip() for dep in self.depends_on.split(',') if dep.strip()]
    
    def set_dependencies(self, dependencies: list):
        """Set dependencies as comma-separated string"""
        self.depends_on = ','.join(dependencies) if dependencies else None
    
    def is_stale(self, last_update: DateTime = None) -> bool:
        """Check if data is stale based on last update time"""
        if not last_update:
            return True
        
        from datetime import datetime, timedelta
        now = datetime.utcnow()
        if last_update.tzinfo is None:
            last_update = last_update.replace(tzinfo=now.tzinfo)
        
        threshold_time = now - timedelta(minutes=self.staleness_threshold_minutes)
        return last_update < threshold_time
    
    def get_next_sync_time(self) -> DateTime:
        """Calculate when the next sync should occur"""
        from datetime import datetime, timedelta
        
        if not self.last_sync:
            return datetime.utcnow()
        
        if self.last_sync.tzinfo is None:
            last_sync = self.last_sync.replace(tzinfo=datetime.utcnow().tzinfo)
        else:
            last_sync = self.last_sync
            
        return last_sync + timedelta(minutes=self.sync_interval_minutes)
    
    def should_sync_now(self) -> bool:
        """Check if sync should occur now based on interval and staleness"""
        if not self.is_sync_enabled:
            return False
            
        from datetime import datetime
        now = datetime.utcnow()
        next_sync = self.get_next_sync_time()
        
        return now >= next_sync
