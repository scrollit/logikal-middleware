from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from core.security import get_current_client, require_permission
from services.scheduler_service import SchedulerService
from schemas.scheduler import (
    TaskStatusResponse, StartSyncResponse, ActiveTasksResponse, 
    ScheduledTasksResponse, WorkerStatsResponse, CancelTaskResponse,
    SchedulerStatusResponse, SyncJobsResponse, SchedulerConfigResponse
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scheduler", tags=["Scheduler Management"])


@router.get("/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get overall scheduler status, worker information, and active tasks.
    Requires 'admin:read' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        status_info = scheduler_service.get_scheduler_status()
        
        return SchedulerStatusResponse(**status_info)
    except Exception as e:
        logger.error(f"Error getting scheduler status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/tasks/active", response_model=ActiveTasksResponse)
async def get_active_tasks(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get information about currently active tasks.
    Requires 'admin:read' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        active_tasks = scheduler_service.get_active_tasks()
        
        return ActiveTasksResponse(**active_tasks)
    except Exception as e:
        logger.error(f"Error getting active tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Get the status of a specific task.
    Requires 'projects:read' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        task_status = scheduler_service.get_task_status(task_id)
        
        return TaskStatusResponse(**task_status)
    except Exception as e:
        logger.error(f"Error getting task status for {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/tasks/scheduled", response_model=ScheduledTasksResponse)
async def get_scheduled_tasks(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get information about scheduled tasks.
    Requires 'admin:read' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        scheduled_tasks = scheduler_service.get_scheduled_tasks()
        
        return ScheduledTasksResponse(**scheduled_tasks)
    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/workers", response_model=WorkerStatsResponse)
async def get_worker_stats(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get statistics about Celery workers.
    Requires 'admin:read' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        worker_stats = scheduler_service.get_worker_stats()
        
        return WorkerStatsResponse(**worker_stats)
    except Exception as e:
        logger.error(f"Error getting worker stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/sync/project/{project_id}", response_model=StartSyncResponse)
async def start_project_sync(
    project_id: str,
    force_sync: bool = Query(False, description="Force sync even if data appears up to date"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Start a background sync for a specific project.
    Requires 'projects:read' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        result = scheduler_service.start_project_sync(project_id, force_sync)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "SYNC_START_FAILED", "message": result["error"]}
            )
        
        return StartSyncResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting project sync for {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/sync/batch", response_model=StartSyncResponse)
async def start_batch_sync(
    project_ids: List[str],
    force_sync: bool = Query(False, description="Force sync even if data appears up to date"),
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("projects:read"))
):
    """
    Start a background batch sync for multiple projects.
    Requires 'projects:read' permission.
    """
    try:
        if not project_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_REQUEST", "message": "project_ids cannot be empty"}
            )
        
        scheduler_service = SchedulerService(db)
        result = scheduler_service.start_batch_sync(project_ids, force_sync)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "SYNC_START_FAILED", "message": result["error"]}
            )
        
        return StartSyncResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting batch sync for {len(project_ids)} projects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.post("/sync/full", response_model=StartSyncResponse)
async def start_full_sync(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Start a background full sync of all projects.
    Requires 'admin:write' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        result = scheduler_service.start_full_sync()
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "SYNC_START_FAILED", "message": result["error"]}
            )
        
        return StartSyncResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting full sync: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.delete("/tasks/{task_id}", response_model=CancelTaskResponse)
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:write"))
):
    """
    Cancel a running task.
    Requires 'admin:write' permission.
    """
    try:
        scheduler_service = SchedulerService(db)
        result = scheduler_service.cancel_task(task_id)
        
        return CancelTaskResponse(**result)
    except Exception as e:
        logger.error(f"Error cancelling task {task_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )


@router.get("/config", response_model=SchedulerConfigResponse)
async def get_scheduler_config(
    db: Session = Depends(get_db),
    current_client: dict = Depends(require_permission("admin:read"))
):
    """
    Get scheduler configuration.
    Requires 'admin:read' permission.
    """
    try:
        import os
        
        config = {
            "background_sync_enabled": os.getenv("BACKGROUND_SYNC_ENABLED", "false").lower() == "true",
            "sync_interval_seconds": int(os.getenv("SYNC_INTERVAL_SECONDS", "3600")),
            "max_concurrent_tasks": int(os.getenv("MAX_CONCURRENT_TASKS", "5")),
            "task_timeout_seconds": int(os.getenv("TASK_TIMEOUT_SECONDS", "1800")),
            "retry_attempts": int(os.getenv("RETRY_ATTEMPTS", "3")),
            "retry_delay_seconds": int(os.getenv("RETRY_DELAY_SECONDS", "60")),
            "cleanup_enabled": os.getenv("CLEANUP_ENABLED", "true").lower() == "true",
            "cleanup_interval_days": int(os.getenv("CLEANUP_INTERVAL_DAYS", "30"))
        }
        
        return SchedulerConfigResponse(**config)
    except Exception as e:
        logger.error(f"Error getting scheduler config: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INTERNAL_ERROR", "message": "Internal server error", "details": str(e)}
        )
