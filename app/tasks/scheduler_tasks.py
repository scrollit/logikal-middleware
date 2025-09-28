from celery import current_task
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from celery_app import celery_app
from core.database import get_db
from services.smart_sync_service import SmartSyncService

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.scheduler_tasks.hourly_smart_sync")
def hourly_smart_sync(self) -> Dict:
    """
    Scheduled task to perform hourly smart sync of stale projects.
    This task runs automatically every hour via Celery Beat.
    """
    task_id = self.request.id
    logger.info(f"Starting hourly smart sync task {task_id}")
    
    try:
        # Check if background sync is enabled
        if not _is_background_sync_enabled():
            logger.info(f"Background sync is disabled, skipping hourly sync task {task_id}")
            return {
                "success": True,
                "skipped": True,
                "reason": "Background sync is disabled",
                "task_id": task_id,
                "scheduled_at": datetime.utcnow().isoformat()
            }
        
        # Get database session
        db = next(get_db())
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": "Starting hourly smart sync",
                "task_id": task_id
            }
        )
        
        # Initialize sync service
        sync_service = SmartSyncService(db)
        
        # Get sync status summary to find stale projects
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 20,
                "total": 100,
                "status": "Analyzing sync status"
            }
        )
        
        summary = sync_service.get_sync_status_summary()
        stale_projects_count = summary["summary"]["stale_projects"]
        
        if stale_projects_count == 0:
            logger.info(f"No stale projects found, skipping sync task {task_id}")
            return {
                "success": True,
                "skipped": True,
                "reason": "No stale projects found",
                "task_id": task_id,
                "stale_projects_count": 0,
                "scheduled_at": datetime.utcnow().isoformat()
            }
        
        # Get all projects and check which ones need syncing
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 40,
                "total": 100,
                "status": f"Found {stale_projects_count} stale projects, checking individual status"
            }
        )
        
        from models.project import Project
        projects = db.query(Project).all()
        stale_project_ids = []
        
        for project in projects:
            if sync_service.is_project_stale(project):
                stale_project_ids.append(project.logikal_id)
        
        if not stale_project_ids:
            logger.info(f"No projects actually need syncing after individual check, skipping sync task {task_id}")
            return {
                "success": True,
                "skipped": True,
                "reason": "No projects actually need syncing",
                "task_id": task_id,
                "checked_projects": len(projects),
                "scheduled_at": datetime.utcnow().isoformat()
            }
        
        # Trigger batch sync for stale projects
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 60,
                "total": 100,
                "status": f"Triggering batch sync for {len(stale_project_ids)} stale projects"
            }
        )
        
        # Import here to avoid circular imports
        from tasks.sync_tasks import batch_sync_projects_task
        
        # Start batch sync as a separate task
        batch_task = batch_sync_projects_task.delay(stale_project_ids, force_sync=False)
        
        # Wait for batch sync to complete (with timeout)
        try:
            batch_result = batch_task.get(timeout=1800)  # 30 minutes timeout
        except Exception as e:
            logger.error(f"Batch sync task failed during hourly sync: {str(e)}")
            batch_result = {
                "success": False,
                "error": str(e)
            }
        
        # Final status update
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 100,
                "total": 100,
                "status": "Hourly smart sync completed"
            }
        )
        
        result = {
            "success": True,
            "task_id": task_id,
            "stale_projects_found": len(stale_project_ids),
            "batch_sync_task_id": batch_task.id,
            "batch_sync_result": batch_result,
            "scheduled_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Hourly smart sync task {task_id} completed: {len(stale_project_ids)} projects processed")
        return result
        
    except Exception as exc:
        logger.error(f"Hourly smart sync task {task_id} failed: {str(exc)}")
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


@celery_app.task(bind=True, name="tasks.scheduler_tasks.cleanup_old_tasks")
def cleanup_old_tasks(self) -> Dict:
    """
    Scheduled task to clean up old completed tasks and logs.
    Runs daily to prevent database bloat.
    """
    task_id = self.request.id
    logger.info(f"Starting cleanup task {task_id}")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Clean up old sync logs (older than 30 days)
        from models.sync_log import SyncLog
        cutoff_date = datetime.utcnow() - timedelta(days=30)
        
        old_logs = db.query(SyncLog).filter(SyncLog.created_at < cutoff_date).all()
        old_logs_count = len(old_logs)
        
        for log in old_logs:
            db.delete(log)
        
        db.commit()
        
        result = {
            "success": True,
            "task_id": task_id,
            "cleaned_up_logs": old_logs_count,
            "cutoff_date": cutoff_date.isoformat(),
            "completed_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Cleanup task {task_id} completed: {old_logs_count} old logs removed")
        return result
        
    except Exception as exc:
        logger.error(f"Cleanup task {task_id} failed: {str(exc)}")
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


@celery_app.task(bind=True, name="tasks.scheduler_tasks.system_health_monitor")
def system_health_monitor(self) -> Dict:
    """
    Scheduled task to monitor system health and send alerts if needed.
    Runs every 15 minutes.
    """
    task_id = self.request.id
    logger.info(f"Starting system health monitor task {task_id}")
    
    try:
        # Import here to avoid circular imports
        from tasks.sync_tasks import health_check_task
        
        # Run health check
        health_result = health_check_task.delay().get()
        
        # Check for issues and log warnings
        if not health_result.get("success", False):
            logger.warning(f"System health check failed: {health_result.get('error', 'Unknown error')}")
        
        # Check sync status
        summary = health_result.get("health_status", {}).get("summary", {})
        stale_projects = summary.get("stale_projects", 0)
        
        if stale_projects > 100:  # Threshold for warning
            logger.warning(f"High number of stale projects detected: {stale_projects}")
        
        result = {
            "success": True,
            "task_id": task_id,
            "health_check_result": health_result,
            "monitored_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"System health monitor task {task_id} completed")
        return result
        
    except Exception as exc:
        logger.error(f"System health monitor task {task_id} failed: {str(exc)}")
        self.update_state(
            state="FAILURE",
            meta={
                "error": str(exc),
                "task_id": task_id,
                "failed_at": datetime.utcnow().isoformat()
            }
        )
        raise exc


def _is_background_sync_enabled() -> bool:
    """
    Check if background sync is enabled in configuration.
    """
    try:
        from core.config import settings
        # For now, we'll use an environment variable
        # In a full implementation, this would check the database configuration
        import os
        return os.getenv("BACKGROUND_SYNC_ENABLED", "false").lower() == "true"
    except:
        return False


def _get_sync_interval() -> int:
    """
    Get the configured sync interval in seconds.
    """
    try:
        import os
        return int(os.getenv("SYNC_INTERVAL_SECONDS", "3600"))  # Default: 1 hour
    except:
        return 3600
