from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from core.database import get_db
from services.object_sync_config_service import ObjectSyncConfigService
from models.object_sync_config import ObjectSyncConfig

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/sync-intervals", tags=["sync-intervals"])


# Pydantic models for request/response
class ObjectSyncConfigUpdate(BaseModel):
    """Model for updating object sync configuration"""
    display_name: Optional[str] = Field(None, description="Human-readable display name")
    description: Optional[str] = Field(None, description="Description of the object type")
    sync_interval_minutes: Optional[int] = Field(None, ge=1, le=10080, description="Sync interval in minutes (1 minute to 1 week)")
    is_sync_enabled: Optional[bool] = Field(None, description="Whether sync is enabled")
    staleness_threshold_minutes: Optional[int] = Field(None, ge=1, le=10080, description="Staleness threshold in minutes")
    priority: Optional[int] = Field(None, ge=1, le=10, description="Sync priority (1=highest)")
    depends_on: Optional[List[str]] = Field(None, description="List of object types this depends on")
    cascade_sync: Optional[bool] = Field(None, description="Whether to cascade sync to dependent objects")
    batch_size: Optional[int] = Field(None, ge=1, le=1000, description="Batch size for bulk operations")
    max_retry_attempts: Optional[int] = Field(None, ge=1, le=10, description="Maximum retry attempts")
    retry_delay_minutes: Optional[int] = Field(None, ge=1, le=60, description="Delay between retry attempts")


class ObjectSyncConfigCreate(BaseModel):
    """Model for creating new object sync configuration"""
    object_type: str = Field(..., description="Object type identifier")
    display_name: str = Field(..., description="Human-readable display name")
    description: Optional[str] = Field(None, description="Description of the object type")
    sync_interval_minutes: int = Field(60, ge=1, le=10080, description="Sync interval in minutes")
    is_sync_enabled: bool = Field(True, description="Whether sync is enabled")
    staleness_threshold_minutes: int = Field(120, ge=1, le=10080, description="Staleness threshold in minutes")
    priority: int = Field(1, ge=1, le=10, description="Sync priority")
    depends_on: List[str] = Field(default_factory=list, description="List of object types this depends on")
    cascade_sync: bool = Field(True, description="Whether to cascade sync to dependent objects")
    batch_size: int = Field(100, ge=1, le=1000, description="Batch size for bulk operations")
    max_retry_attempts: int = Field(3, ge=1, le=10, description="Maximum retry attempts")
    retry_delay_minutes: int = Field(5, ge=1, le=60, description="Delay between retry attempts")


class ObjectSyncConfigResponse(BaseModel):
    """Model for object sync configuration response"""
    id: int
    object_type: str
    display_name: str
    description: Optional[str]
    sync_interval_minutes: int
    is_sync_enabled: bool
    staleness_threshold_minutes: int
    priority: int
    depends_on: List[str]
    cascade_sync: bool
    batch_size: int
    max_retry_attempts: int
    retry_delay_minutes: int
    created_at: str
    updated_at: str
    last_sync: Optional[str]
    last_attempt: Optional[str]
    next_sync_time: str
    is_stale: bool

    @classmethod
    def from_orm(cls, config: ObjectSyncConfig) -> "ObjectSyncConfigResponse":
        """Create response model from ORM object"""
        return cls(
            id=config.id,
            object_type=config.object_type,
            display_name=config.display_name,
            description=config.description,
            sync_interval_minutes=config.sync_interval_minutes,
            is_sync_enabled=config.is_sync_enabled,
            staleness_threshold_minutes=config.staleness_threshold_minutes,
            priority=config.priority,
            depends_on=config.get_dependencies(),
            cascade_sync=config.cascade_sync,
            batch_size=config.batch_size,
            max_retry_attempts=config.max_retry_attempts,
            retry_delay_minutes=config.retry_delay_minutes,
            created_at=config.created_at.isoformat(),
            updated_at=config.updated_at.isoformat(),
            last_sync=config.last_sync.isoformat() if config.last_sync else None,
            last_attempt=config.last_attempt.isoformat() if config.last_attempt else None,
            next_sync_time=config.get_next_sync_time().isoformat(),
            is_stale=config.is_stale()
        )


@router.get("/", response_model=List[ObjectSyncConfigResponse])
async def get_all_sync_configs(db: Session = Depends(get_db)):
    """Get all object sync configurations"""
    try:
        service = ObjectSyncConfigService(db)
        configs = service.get_all_configs()
        
        # If no configs exist, create defaults
        if not configs:
            logger.info("No sync configurations found, creating defaults")
            service.create_default_configs()
            configs = service.get_all_configs()
        
        return [ObjectSyncConfigResponse.from_orm(config) for config in configs]
    
    except Exception as e:
        logger.error(f"Error getting sync configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync configurations: {str(e)}")


@router.get("/{object_type}", response_model=ObjectSyncConfigResponse)
async def get_sync_config(object_type: str, db: Session = Depends(get_db)):
    """Get sync configuration for specific object type"""
    try:
        service = ObjectSyncConfigService(db)
        config = service.get_config(object_type)
        
        if not config:
            raise HTTPException(status_code=404, detail=f"Sync configuration for {object_type} not found")
        
        return ObjectSyncConfigResponse.from_orm(config)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sync configuration for {object_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync configuration: {str(e)}")


@router.put("/{object_type}", response_model=ObjectSyncConfigResponse)
async def update_sync_config(
    object_type: str, 
    config_update: ObjectSyncConfigUpdate, 
    db: Session = Depends(get_db)
):
    """Update sync configuration for specific object type"""
    try:
        service = ObjectSyncConfigService(db)
        
        # Convert Pydantic model to dict, excluding None values
        update_data = config_update.dict(exclude_unset=True)
        
        config = service.update_config(object_type, update_data)
        
        if not config:
            raise HTTPException(status_code=404, detail=f"Sync configuration for {object_type} not found")
        
        return ObjectSyncConfigResponse.from_orm(config)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating sync configuration for {object_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update sync configuration: {str(e)}")


@router.post("/", response_model=ObjectSyncConfigResponse)
async def create_sync_config(config_create: ObjectSyncConfigCreate, db: Session = Depends(get_db)):
    """Create new sync configuration"""
    try:
        service = ObjectSyncConfigService(db)
        
        # Check if config already exists
        existing = service.get_config(config_create.object_type)
        if existing:
            raise HTTPException(status_code=400, detail=f"Sync configuration for {config_create.object_type} already exists")
        
        # Convert Pydantic model to dict
        config_data = config_create.dict()
        
        config = service.create_config(config_data)
        
        return ObjectSyncConfigResponse.from_orm(config)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating sync configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create sync configuration: {str(e)}")


@router.delete("/{object_type}")
async def delete_sync_config(object_type: str, db: Session = Depends(get_db)):
    """Delete sync configuration for specific object type"""
    try:
        service = ObjectSyncConfigService(db)
        
        success = service.delete_config(object_type)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Sync configuration for {object_type} not found")
        
        return {"success": True, "message": f"Sync configuration for {object_type} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting sync configuration for {object_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete sync configuration: {str(e)}")


@router.post("/{object_type}/toggle")
async def toggle_sync_enabled(object_type: str, db: Session = Depends(get_db)):
    """Toggle sync enabled status for object type"""
    try:
        service = ObjectSyncConfigService(db)
        
        config = service.toggle_sync_enabled(object_type)
        
        if not config:
            raise HTTPException(status_code=404, detail=f"Sync configuration for {object_type} not found")
        
        return {
            "success": True, 
            "message": f"Sync {'enabled' if config.is_sync_enabled else 'disabled'} for {object_type}",
            "is_sync_enabled": config.is_sync_enabled
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling sync status for {object_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle sync status: {str(e)}")


@router.get("/order/sync", response_model=List[ObjectSyncConfigResponse])
async def get_sync_order(db: Session = Depends(get_db)):
    """Get sync configurations ordered by dependency and priority"""
    try:
        service = ObjectSyncConfigService(db)
        configs = service.get_sync_order()
        
        return [ObjectSyncConfigResponse.from_orm(config) for config in configs]
    
    except Exception as e:
        logger.error(f"Error getting sync order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync order: {str(e)}")


@router.get("/summary/overview")
async def get_sync_summary(db: Session = Depends(get_db)):
    """Get summary of all sync configurations"""
    try:
        service = ObjectSyncConfigService(db)
        summary = service.get_configs_summary()
        
        return {
            "success": True,
            "data": summary
        }
    
    except Exception as e:
        logger.error(f"Error getting sync summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sync summary: {str(e)}")


@router.post("/reset")
async def reset_all_configs(db: Session = Depends(get_db)):
    """Reset all sync configurations to defaults"""
    try:
        service = ObjectSyncConfigService(db)
        count = service.reset_all_configs()
        
        return {
            "success": True,
            "message": f"Reset all sync configurations, created {count} default configurations",
            "configs_created": count
        }
    
    except Exception as e:
        logger.error(f"Error resetting sync configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to reset sync configurations: {str(e)}")


@router.post("/{object_type}/sync")
async def trigger_object_sync(object_type: str, db: Session = Depends(get_db)):
    """Trigger immediate sync for specific object type"""
    try:
        service = ObjectSyncConfigService(db)
        
        config = service.get_config(object_type)
        if not config:
            raise HTTPException(status_code=404, detail=f"Sync configuration for {object_type} not found")
        
        if not config.is_sync_enabled:
            raise HTTPException(status_code=400, detail=f"Sync is disabled for {object_type}")
        
        # TODO: Implement actual sync trigger
        # This would integrate with the existing sync services
        
        # Update last attempt timestamp
        service.update_last_sync(object_type, success=True)
        
        return {
            "success": True,
            "message": f"Sync triggered for {object_type}",
            "object_type": object_type,
            "triggered_at": datetime.utcnow().isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering sync for {object_type}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger sync: {str(e)}")
