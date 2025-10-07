from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class PhaseBase(BaseModel):
    """Base phase schema"""
    logikal_id: str
    name: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    status: Optional[str] = None


class PhaseCreate(PhaseBase):
    """Schema for creating a phase"""
    pass


class PhaseResponse(PhaseBase):
    """Schema for phase response"""
    id: int
    created_at: datetime
    updated_at: datetime
    last_sync_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None
    synced_at: Optional[datetime] = None
    sync_status: Optional[str] = None
    project_name: Optional[str] = None
    is_stale: Optional[bool] = None
    
    class Config:
        from_attributes = True


class PhaseListResponse(BaseModel):
    """Response schema for phase list"""
    success: bool = True
    data: List[PhaseResponse]
    count: int
    last_updated: Optional[str] = None
    sync_status: Optional[str] = None
    stale_count: Optional[int] = None
