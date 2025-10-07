from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ElevationBase(BaseModel):
    """Base elevation schema"""
    logikal_id: str
    name: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    phase_id: Optional[int] = None
    thumbnail_url: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None


class ElevationCreate(ElevationBase):
    """Schema for creating an elevation"""
    pass


class ElevationResponse(ElevationBase):
    """Schema for elevation response"""
    id: int
    created_at: datetime
    updated_at: datetime
    last_sync_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    sync_status: Optional[str] = None
    # Additional fields for data browser
    image_path: Optional[str] = None
    parse_status: Optional[str] = None
    parse_error: Optional[str] = None
    data_parsed_at: Optional[datetime] = None
    has_parts_data: Optional[bool] = None
    phase_name: Optional[str] = None
    project_name: Optional[str] = None
    directory_name: Optional[str] = None
    directory_id: Optional[int] = None
    is_stale: Optional[bool] = None
    
    class Config:
        from_attributes = True


class ElevationListResponse(BaseModel):
    """Response schema for elevation list"""
    success: bool = True
    data: List[ElevationResponse]
    count: int
    last_updated: Optional[str] = None
    sync_status: Optional[str] = None
    stale_count: Optional[int] = None
