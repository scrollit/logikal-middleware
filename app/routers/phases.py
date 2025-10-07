from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from core.database import get_db
from schemas.phase import PhaseListResponse, PhaseResponse
from models.phase import Phase
from models.project import Project
from models.directory import Directory

router = APIRouter(prefix="/phases", tags=["phases"])


@router.get("/cached", response_model=PhaseListResponse)
async def get_cached_phases(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    db: Session = Depends(get_db)
):
    """Get cached phases from middleware database with hierarchy, optionally filtered by project (no authentication required)"""
    try:
        # Get phases with their project and directory relationships
        query = db.query(Phase).options(
            joinedload(Phase.project).joinedload(Project.directory)
        )
        
        # Filter by project if specified
        if project_id is not None:
            query = query.filter(Phase.project_id == project_id)
        
        cached_phases = query.all()
        
        # Calculate stale phases
        stale_threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        stale_count = sum(1 for phase in cached_phases if phase.last_sync_date and phase.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold)
        
        # Create phase data with hierarchy information
        phase_data = []
        for phase in cached_phases:
            phase_dict = {
                "id": phase.id,
                "logikal_id": phase.logikal_id,
                "name": phase.name,
                "description": phase.description,
                "project_id": phase.project_id,
                "status": phase.status,
                "created_at": phase.created_at,
                "updated_at": phase.updated_at,
                "last_sync_date": phase.last_sync_date,
                "last_update_date": phase.last_update_date,
                "synced_at": phase.synced_at,
                "sync_status": phase.sync_status,
                "project_name": phase.project.name if phase.project else "Unknown Project",
                "directory_name": phase.project.directory.name if phase.project and phase.project.directory else "Unknown Directory",
                "directory_id": phase.project.directory.id if phase.project and phase.project.directory else None,
                "is_stale": phase.last_sync_date and phase.last_sync_date.replace(tzinfo=timezone.utc) < stale_threshold
            }
            phase_data.append(PhaseResponse(**phase_dict))
        
        # Calculate last updated timestamp
        last_updated = None
        if cached_phases:
            sync_dates = [phase.last_sync_date for phase in cached_phases if phase.last_sync_date]
            if sync_dates:
                last_updated = max(sync_dates)
        
        return PhaseListResponse(
            data=phase_data,
            count=len(cached_phases),
            last_updated=last_updated.isoformat() if last_updated else None,
            sync_status="cached",
            stale_count=stale_count
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))