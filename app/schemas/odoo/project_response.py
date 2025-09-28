from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class OdooElevationResponse(BaseModel):
    """Simplified elevation response for Odoo"""
    id: str
    name: str
    description: Optional[str] = None
    phase_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class OdooPhaseResponse(BaseModel):
    """Simplified phase response for Odoo"""
    id: str
    name: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    status: Optional[str] = None
    elevations_count: int = 0
    elevations: List[OdooElevationResponse] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


class OdooProjectResponse(BaseModel):
    """Simplified project response for Odoo"""
    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    phases_count: int = 0
    total_elevations: int = 0
    phases: List[OdooPhaseResponse] = []
    created_at: datetime
    
    class Config:
        from_attributes = True


class OdooProjectSummaryResponse(BaseModel):
    """Summary response for project list"""
    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    phases_count: int = 0
    total_elevations: int = 0
    created_at: datetime
    
    class Config:
        from_attributes = True


class OdooProjectListResponse(BaseModel):
    """Response for project list"""
    projects: List[OdooProjectSummaryResponse]
    count: int
    summary: dict


class OdooProjectCompleteResponse(BaseModel):
    """Complete project response with all phases and elevations"""
    project: OdooProjectResponse
    phases_with_elevations: List[dict]
    summary: dict


class OdooSearchResponse(BaseModel):
    """Search results response"""
    results: List[OdooProjectSummaryResponse]
    query: str
    count: int


class OdooStatsResponse(BaseModel):
    """Statistics response"""
    total_projects: int
    total_phases: int
    total_elevations: int
    projects: List[dict]
