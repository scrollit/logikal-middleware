from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from core.security import get_current_client, require_permission
from services.smart_sync_service import SmartSyncService
from schemas.sync_status import SyncStatusResponse, SyncResultResponse, SyncStatusSummaryResponse
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync-status", tags=["Smart Sync Status"])


@router.get("/project/{project_id}", response_model=SyncStatusResponse)
async def get_project_sync_status(
    project_id: str,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Get sync status for a specific project.
    Shows whether the project and its phases/elevations need syncing.
    Requires 'projects:read' permission.
    """
    try:
        sync_service = SmartSyncService(db)
        sync_status = sync_service.check_project_sync_needed(project_id)
        
        return SyncStatusResponse(**sync_status)
    except Exception as e:
        logger.error(f"Error getting sync status for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/project/{project_id}/sync", response_model=SyncResultResponse)
async def sync_project_if_needed(
    project_id: str,
    force_sync: bool = Query(False, description="Force sync even if data appears up to date"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Perform smart sync for a project if needed.
    Only syncs if data is stale or if force_sync is True.
    Implements cascading sync logic.
    Requires 'projects:read' permission.
    """
    try:
        sync_service = SmartSyncService(db)
        sync_result = sync_service.sync_project_if_needed(project_id, force_sync=force_sync)
        
        return SyncResultResponse(**sync_result)
    except Exception as e:
        logger.error(f"Error syncing project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/summary", response_model=SyncStatusSummaryResponse)
async def get_sync_status_summary(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get a summary of sync status for all projects, phases, and elevations.
    Shows counts of stale data across the entire system.
    Requires 'admin:read' permission.
    """
    try:
        sync_service = SmartSyncService(db)
        summary = sync_service.get_sync_status_summary()
        
        return SyncStatusSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Error getting sync status summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/project/{project_id}/mark-updated")
async def mark_project_as_updated(
    project_id: str,
    update_date: Optional[str] = Query(None, description="ISO datetime string for update date (defaults to now)"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Mark a project as having been updated in Logikal.
    This simulates receiving updated data from Logikal.
    Requires 'admin:write' permission.
    """
    try:
        from datetime import datetime
        update_dt = None
        if update_date:
            update_dt = datetime.fromisoformat(update_date.replace('Z', '+00:00'))
        
        sync_service = SmartSyncService(db)
        success = sync_service.mark_project_as_updated(project_id, update_dt)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PROJECT_NOT_FOUND", "message": f"Project {project_id} not found"}
            )
        
        return {
            "success": True,
            "message": f"Project {project_id} marked as updated",
            "update_date": update_dt or datetime.utcnow()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DATE", "message": "Invalid date format", "details": str(e)}
        )
    except Exception as e:
        logger.error(f"Error marking project {project_id} as updated: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )
