from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


class SyncStatusResponse(BaseModel):
    """Response model for sync status information"""
    project_id: str
    exists: bool
    sync_needed: bool
    project_stale: bool
    stale_phases_count: int
    stale_elevations_count: int
    total_phases: int
    total_elevations: int
    last_sync_date: Optional[datetime] = None
    last_update_date: Optional[datetime] = None
    reason: Optional[str] = None


class SyncResultResponse(BaseModel):
    """Response model for sync operation results"""
    success: bool
    synced: bool
    project_id: str
    reason: Optional[str] = None
    error: Optional[str] = None
    sync_status: Optional[SyncStatusResponse] = None
    sync_result: Optional[Dict] = None


class SyncSummaryResponse(BaseModel):
    """Response model for sync status summary"""
    summary: Dict
    generated_at: datetime


class SyncStatusSummary(BaseModel):
    """Detailed sync status summary"""
    total_projects: int
    stale_projects: int
    projects_never_synced: int
    total_phases: int
    stale_phases: int
    total_elevations: int
    stale_elevations: int


class SyncStatusSummaryResponse(BaseModel):
    """Response model for detailed sync status summary"""
    summary: SyncStatusSummary
    generated_at: datetime
