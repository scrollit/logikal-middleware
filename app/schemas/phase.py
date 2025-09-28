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
    
    class Config:
        from_attributes = True


class PhaseListResponse(BaseModel):
    """Response schema for phase list"""
    success: bool = True
    data: List[PhaseResponse]
    count: int
