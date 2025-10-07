from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ProjectBase(BaseModel):
    """Base project schema"""
    logikal_id: str
    name: str
    description: Optional[str] = None
    directory_id: Optional[int] = None
    status: Optional[str] = None


class ProjectCreate(ProjectBase):
    """Schema for creating a project"""
    pass


class ProjectResponse(ProjectBase):
    """Schema for project response"""
    id: int
    created_at: datetime
    updated_at: datetime
    last_sync_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None
    directory_name: Optional[str] = None
    is_stale: Optional[bool] = None
    
    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Response schema for project list"""
    success: bool = True
    data: List[ProjectResponse]
    count: int
    last_updated: Optional[str] = None
    sync_status: Optional[str] = None
    stale_count: Optional[int] = None
