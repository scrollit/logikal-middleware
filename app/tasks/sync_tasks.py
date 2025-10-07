from celery import current_task
from celery.exceptions import Retry
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime
import asyncio
import logging
import traceback

from celery_app import celery_app
from core.database import get_db
from services.smart_sync_service import SmartSyncService
from services.project_sync_service import ProjectSyncService
from services.phase_sync_service import PhaseSyncService
from services.elevation_sync_service import ElevationSyncService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.sync_tasks.sync_project_task")
def sync_project_task(self, project_id: str, force_sync: bool = False) -> Dict:
    """
    Background task to sync a specific project from Logikal.
    """
    task_id = self.request.id
    logger.info(f"Starting sync task {task_id} for project {project_id}")
    
    try:
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": f"Starting sync for project {project_id}",
                "project_id": project_id
            }
        )
        
        # Get database session
        db = next(get_db())
        
        # Initialize sync service
        sync_service = SmartSyncService(db)
        
        # Check if sync is needed
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "status": "Checking sync status",
                "project_id": project_id
            }
        )
        
        sync_status = sync_service.check_project_sync_needed(project_id)
        
        if not sync_status["exists"]:
            raise ValueError(f"Project {project_id} not found")
        
        if not force_sync and not sync_status["sync_needed"]:
            return {
                "success": True,
                "synced": False,
                "reason": "Data is up to date",
                "project_id": project_id,
                "task_id": task_id
            }
        
        # Perform the sync
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 30,
                "total": 100,
                "status": "Syncing project data",
                "project_id": project_id
            }
        )
        
        sync_result = sync_service._perform_project_sync(project_id)
        
        # Update final status
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 100,
                "total": 100,
                "status": "Sync completed successfully",
                "project_id": project_id
            }
        )
        
        result = {
            "success": True,
            "synced": True,
            "project_id": project_id,
            "task_id": task_id,
            "sync_result": sync_result,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Sync task {task_id} completed successfully for project {project_id}")
        return result
        
    except Exception as exc:
        logger.error(f"Sync task {task_id} failed for project {project_id}: {str(exc)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Update task state with error
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(exc),
                "project_id": project_id,
                "task_id": task_id,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        
        # Retry logic for certain types of errors with improved handling
        if isinstance(exc, (ConnectionError, TimeoutError)) and self.request.retries < 3:
            retry_count = self.request.retries + 1
            countdown = min(60 * (2 ** self.request.retries), 300)  # Max 5 minutes
            logger.info(f"Retrying sync task {task_id} for project {project_id} (attempt {retry_count}/{3}) in {countdown}s")
            raise self.retry(countdown=countdown)
        
        raise exc
    
    finally:
        # Close database session
        if 'db' in locals():
            db.close()


@celery_app.task(bind=True, name="tasks.sync_tasks.batch_sync_projects_task")
async def batch_sync_projects_task(self, project_ids: List[str], force_sync: bool = False) -> Dict:
    """
    Background task to sync multiple projects in batch.
    """
    task_id = self.request.id
    logger.info(f"Starting batch sync task {task_id} for {len(project_ids)} projects")
    
    try:
        results = []
        total_projects = len(project_ids)
        
        # Process projects with concurrency control (2 workers max)
        MAX_CONCURRENT_WORKERS = 2
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_WORKERS)
        
        async def sync_project_with_semaphore(project_id, index):
            """Sync a single project with semaphore protection"""
            async with semaphore:
                # Update progress
                progress = int((index / total_projects) * 100)
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "current": progress,
                        "total": 100,
                        "status": f"Syncing project {index+1}/{total_projects}: {project_id}",
                        "project_id": project_id,
                        "completed": index,
                        "total_projects": total_projects
                    }
                )
                
                # Sync individual project
                try:
                    project_result = sync_project_task.delay(project_id, force_sync).get()
                    return {
                        "project_id": project_id,
                        "success": True,
                        "result": project_result
                    }
                except Exception as e:
                    logger.error(f"Failed to sync project {project_id}: {str(e)}")
                    return {
                        "project_id": project_id,
                        "success": False,
                        "error": str(e)
                    }
        
        # Create tasks for all projects
        tasks = [sync_project_with_semaphore(project_id, i) for i, project_id in enumerate(project_ids)]
        
        # Process all projects concurrently
        logger.info(f"Launching {len(tasks)} concurrent project sync tasks with {MAX_CONCURRENT_WORKERS} worker limit")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Task {i} failed with exception: {str(result)}")
                processed_results.append({
                    "project_id": project_ids[i],
                    "success": False,
                    "error": str(result)
                })
            else:
                processed_results.append(result)
        
        results = processed_results
        
        # Final result
        successful_syncs = sum(1 for r in results if r["success"])
        
        result = {
            "success": True,
            "task_id": task_id,
            "total_projects": total_projects,
            "successful_syncs": successful_syncs,
            "failed_syncs": total_projects - successful_syncs,
            "results": results,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Batch sync task {task_id} completed: {successful_syncs}/{total_projects} successful")
        return result
        
    except Exception as exc:
        logger.error(f"Batch sync task {task_id} failed: {str(exc)}")
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(exc),
                "task_id": task_id,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        raise exc


@celery_app.task(bind=True, name="tasks.sync_tasks.full_sync_task")
def full_sync_task(self) -> Dict:
    """
    Background task to perform a full sync of all projects.
    """
    task_id = self.request.id
    logger.info(f"Starting full sync task {task_id}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Get all projects
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": "Fetching all projects"
            }
        )
        
        from models.project import Project
        projects = db.query(Project).all()
        project_ids = [p.logikal_id for p in projects]
        
        if not project_ids:
            return {
                "success": True,
                "message": "No projects found to sync",
                "task_id": task_id,
                "completed_at": datetime.utcnow().isoformat()
            }
        
        # Perform batch sync
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "status": f"Starting batch sync of {len(project_ids)} projects"
            }
        )
        
        batch_result = batch_sync_projects_task.delay(project_ids, force_sync=True).get()
        
        result = {
            "success": True,
            "task_id": task_id,
            "message": f"Full sync completed: {batch_result['successful_syncs']}/{batch_result['total_projects']} projects synced",
            "batch_result": batch_result,
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Full sync task {task_id} completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"Full sync task {task_id} failed: {str(exc)}")
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(exc),
                "task_id": task_id,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        raise exc
    
    finally:
        if 'db' in locals():
            db.close()


@celery_app.task(bind=True, name="tasks.sync_tasks.health_check_task")
def health_check_task(self) -> Dict:
    """
    Background task to check system health and sync status.
    """
    task_id = self.request.id
    logger.info(f"Starting health check task {task_id}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Initialize sync service
        sync_service = SmartSyncService(db)
        
        # Get sync status summary
        summary = sync_service.get_sync_status_summary()
        
        # Check system health
        health_status = {
            "database": "healthy",
            "redis": "healthy",  # Could add actual Redis check here
            "sync_system": "healthy",
            "summary": summary["summary"]
        }
        
        result = {
            "success": True,
            "task_id": task_id,
            "health_status": health_status,
            "checked_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Health check task {task_id} completed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"Health check task {task_id} failed: {str(exc)}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(exc),
            "failed_at": datetime.utcnow().isoformat()
        }
    
    finally:
        if 'db' in locals():
            db.close()
