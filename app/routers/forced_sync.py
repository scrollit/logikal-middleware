from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from core.database import get_db
from services.directory_sync_service import DirectorySyncService
from services.project_sync_service import ProjectSyncService

router = APIRouter(prefix="/sync/force", tags=["forced-sync"])


@router.post("/directories")
async def force_sync_directories_ui(db: Session = Depends(get_db)):
    """Force sync directories from Logikal (no authentication required for Odoo integration)"""
    try:
        from core.config_production import get_settings
        settings = get_settings()
        
        directory_sync_service = DirectorySyncService(db)
        result = await directory_sync_service.sync_directories_from_logikal(
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "directories_processed": result.get('directories_processed', 0),
                "duration_seconds": result.get('duration_seconds', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "FORCE_SYNC_DIRECTORIES_FAILED",
                    "message": "Force sync directories failed",
                    "details": result['message']
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.post("/project/{project_id}")
async def force_sync_project_ui(
    project_id: str,
    directory_id: Optional[str] = Query(None, description="Directory ID for project context"),
    db: Session = Depends(get_db)
):
    """Force sync specific project from Logikal (no authentication required for Odoo integration)"""
    try:
        from core.config_production import get_settings
        settings = get_settings()
        
        project_sync_service = ProjectSyncService(db)
        result = await project_sync_service.force_sync_project_from_logikal(
            project_id,
            directory_id,
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "project_id": project_id,
                "directory_id": directory_id,
                "phases_synced": result.get('phases_synced', 0),
                "elevations_synced": result.get('elevations_synced', 0),
                "parts_lists_synced": result.get('parts_lists_synced', 0),
                "parts_lists_failed": result.get('parts_lists_failed', 0),
                "duration_seconds": result.get('duration_seconds', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "FORCE_SYNC_PROJECT_FAILED",
                    "message": "Force sync project failed",
                    "details": result['message']
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )


@router.post("/directory/{directory_id}/projects")
async def force_sync_directory_projects_ui(
    directory_id: str,
    db: Session = Depends(get_db)
):
    """Force sync all projects in a specific directory from Logikal (no authentication required for Odoo integration)"""
    try:
        from core.config_production import get_settings
        settings = get_settings()
        
        project_sync_service = ProjectSyncService(db)
        result = await project_sync_service.force_sync_projects_for_directory(
            directory_id,
            settings.LOGIKAL_API_BASE_URL,
            settings.LOGIKAL_AUTH_USERNAME,
            settings.LOGIKAL_AUTH_PASSWORD
        )
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "directory_id": directory_id,
                "projects_synced": result.get('projects_synced', 0),
                "phases_synced": result.get('phases_synced', 0),
                "elevations_synced": result.get('elevations_synced', 0),
                "duration_seconds": result.get('duration_seconds', 0)
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "FORCE_SYNC_DIRECTORY_PROJECTS_FAILED",
                    "message": "Force sync directory projects failed",
                    "details": result['message']
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
                "details": str(e)
            }
        )
