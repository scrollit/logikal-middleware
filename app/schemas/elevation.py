from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class ElevationBase(BaseModel):
    """Base elevation schema"""
    logikal_id: str
    name: str
    description: Optional[str] = None
    project_id: Optional[int] = None
    phase_id: Optional[str] = None
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
    
    class Config:
        from_attributes = True


class ElevationListResponse(BaseModel):
    """Response schema for elevation list"""
    success: bool = True
    data: List[ElevationResponse]
    count: int
