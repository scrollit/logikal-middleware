from pydantic import BaseModel, field_serializer
from typing import List, Optional
from datetime import datetime


class OdooBaseResponse(BaseModel):
    """Base response class with Odoo-compatible datetime serialization"""
    
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to Odoo format: YYYY-MM-DD HH:MM:SS"""
        if dt is None:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')


class OdooGlassSpecification(BaseModel):
    """Glass specification response for Odoo"""
    glass_id: str
    name: Optional[str] = None
    
    class Config:
        from_attributes = True


class OdooElevationResponse(OdooBaseResponse):
    """Enhanced elevation response for Odoo with enriched data"""
    # Existing fields (maintain backward compatibility)
    id: str
    name: str
    description: Optional[str] = None
    phase_id: Optional[str] = None
    thumbnail_url: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    depth: Optional[float] = None
    created_at: datetime
    
    # NEW: SQLite enrichment data
    auto_description: Optional[str] = None
    auto_description_short: Optional[str] = None
    width_out: Optional[float] = None
    width_unit: Optional[str] = None
    height_out: Optional[float] = None
    height_unit: Optional[str] = None
    weight_out: Optional[float] = None
    weight_unit: Optional[str] = None
    area_output: Optional[float] = None
    area_unit: Optional[str] = None
    
    # NEW: System information
    system_code: Optional[str] = None
    system_name: Optional[str] = None
    system_long_name: Optional[str] = None
    color_base_long: Optional[str] = None
    
    # NEW: Parts information
    parts_count: Optional[int] = None
    has_parts_data: bool = False
    parts_synced_at: Optional[datetime] = None
    
    # NEW: Quality metrics
    parse_status: str = "pending"
    data_quality_score: Optional[float] = None
    
    # NEW: Glass specifications
    glass_specifications: List[OdooGlassSpecification] = []
    
    # NEW: Enhanced timestamps
    last_sync_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None
    
    @field_serializer('created_at', 'updated_at', 'last_sync_date', 'last_update_date', 'parts_synced_at', check_fields=False)
    def serialize_datetime_fields(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to Odoo format: YYYY-MM-DD HH:MM:SS"""
        if dt is None:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    class Config:
        from_attributes = True


class OdooPhaseResponse(OdooBaseResponse):
    """Simplified phase response for Odoo"""
    id: str
    name: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    status: Optional[str] = None
    elevations_count: int = 0
    elevations: List[OdooElevationResponse] = []
    created_at: datetime
    
    @field_serializer('created_at', check_fields=False)
    def serialize_created_at(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to Odoo format: YYYY-MM-DD HH:MM:SS"""
        if dt is None:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    class Config:
        from_attributes = True


class OdooProjectResponse(OdooBaseResponse):
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


class OdooProjectSummaryResponse(OdooBaseResponse):
    """Summary response for project list"""
    id: str
    name: str
    description: Optional[str] = None
    status: Optional[str] = None
    phases_count: int = 0
    total_elevations: int = 0
    created_at: datetime
    
    @field_serializer('created_at', check_fields=False)
    def serialize_created_at(self, dt: Optional[datetime]) -> Optional[str]:
        """Serialize datetime to Odoo format: YYYY-MM-DD HH:MM:SS"""
        if dt is None:
            return None
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    class Config:
        from_attributes = True


class OdooProjectListResponse(OdooBaseResponse):
    """Response for project list"""
    projects: List[OdooProjectSummaryResponse]
    count: int
    summary: dict


class OdooProjectCompleteResponse(OdooBaseResponse):
    """Complete project response with all phases and elevations"""
    project: OdooProjectResponse
    phases_with_elevations: List[dict]
    summary: dict


class OdooSearchResponse(OdooBaseResponse):
    """Search results response"""
    results: List[OdooProjectSummaryResponse]
    query: str
    count: int


class OdooStatsResponse(OdooBaseResponse):
    """Statistics response"""
    total_projects: int
    total_phases: int
    total_elevations: int
    projects: List[dict]
