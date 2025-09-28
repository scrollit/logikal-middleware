from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from core.database import Base


class Directory(Base):
    """Directory model for storing Logikal directory information"""
    __tablename__ = "directories"
    
    id = Column(Integer, primary_key=True, index=True)
    logikal_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    full_path = Column(String(500), nullable=True)  # Full navigation path
    level = Column(Integer, default=0)  # Directory depth level
    parent_id = Column(Integer, ForeignKey("directories.id"), nullable=True)
    exclude_from_sync = Column(Boolean, default=False, nullable=False)  # Exclusion flag
    synced_at = Column(DateTime(timezone=True), nullable=True)  # Last sync timestamp
    last_api_sync = Column(DateTime(timezone=True), nullable=True)  # Last API sync
    api_created_date = Column(DateTime(timezone=True), nullable=True)  # API creation date
    api_changed_date = Column(DateTime(timezone=True), nullable=True)  # API change date for incremental sync
    sync_status = Column(String(50), default='pending')  # Sync status: pending, synced, error
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    parent = relationship("Directory", remote_side=[id], backref="children")
    
    def is_excluded_from_sync(self):
        """Check if this directory or any parent is excluded from sync"""
        if self.exclude_from_sync:
            return True
        # Use a set to track visited directories to prevent infinite recursion
        visited = set()
        current = self.parent
        while current and current.id not in visited:
            visited.add(current.id)
            if current.exclude_from_sync:
                return True
            current = current.parent
        return False
    
    def get_excluded_subfolders(self):
        """Get all subfolders that are excluded from sync"""
        excluded = []
        visited = set()
        
        def collect_excluded(directory):
            if directory.id in visited:
                return
            visited.add(directory.id)
            
            for child in directory.children:
                if child.exclude_from_sync:
                    excluded.append(child)
                collect_excluded(child)
        
        collect_excluded(self)
        return excluded
    
    def __repr__(self):
        return f"<Directory(id={self.id}, name='{self.name}', logikal_id='{self.logikal_id}', exclude_from_sync={self.exclude_from_sync})>"
