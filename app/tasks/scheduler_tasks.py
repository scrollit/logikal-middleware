from celery import current_task
from sqlalchemy.orm import Session
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import logging

from celery_app import celery_app
from core.database import get_db
from services.smart_sync_service import SmartSyncService
from services.object_sync_config_service import ObjectSyncConfigService

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


@celery_app.task(bind=True, name="tasks.scheduler_tasks.smart_sync_scheduler")
def smart_sync_scheduler(self) -> Dict:
    """
    Smart sync scheduler that respects admin panel sync intervals.
    This task runs every 5 minutes and checks which objects need syncing
    based on their individual intervals configured in the admin panel.
    """
    task_id = self.request.id
    logger.info(f"Starting smart sync scheduler task {task_id}")
    
    try:
        # Check if background sync is enabled
        if not _is_background_sync_enabled():
            logger.info(f"Background sync is disabled, skipping smart sync scheduler task {task_id}")
            return {
                "success": True,
                "skipped": True,
                "reason": "Background sync is disabled",
                "task_id": task_id,
                "scheduled_at": datetime.utcnow().isoformat()
            }
        
        # Get database session
        db = next(get_db())
        
        # Initialize services
        config_service = ObjectSyncConfigService(db)
        sync_service = SmartSyncService(db)
        
        # Update task status
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": "Checking sync configurations",
                "task_id": task_id
            }
        )
        
        # Get all sync configurations
        configs = config_service.get_all_configs()
        enabled_configs = [config for config in configs if config.is_sync_enabled]
        
        logger.info(f"Found {len(enabled_configs)} enabled sync configurations")
        
        sync_results = []
        objects_to_sync = []
        
        # Check each object type for sync needs
        for config in enabled_configs:
            try:
                # Check if this object type needs syncing
                needs_sync = _should_sync_object_type(config, db)
                
                if needs_sync:
                    objects_to_sync.append({
                        "object_type": config.object_type,
                        "display_name": config.display_name,
                        "priority": config.priority,
                        "sync_interval_minutes": config.sync_interval_minutes
                    })
                    
                    logger.info(f"Object type '{config.object_type}' needs syncing (interval: {config.sync_interval_minutes} minutes)")
                
            except Exception as e:
                logger.error(f"Error checking sync status for {config.object_type}: {str(e)}")
                continue
        
        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 50,
                "total": 100,
                "status": f"Found {len(objects_to_sync)} objects to sync",
                "task_id": task_id
            }
        )
        
        # Sort by priority (1 = highest priority)
        objects_to_sync.sort(key=lambda x: x["priority"])
        
        # Trigger syncs for objects that need it
        for obj_info in objects_to_sync:
            try:
                sync_result = _trigger_object_sync(obj_info["object_type"], db)
                sync_results.append({
                    "object_type": obj_info["object_type"],
                    "display_name": obj_info["display_name"],
                    "success": sync_result.get("success", False),
                    "message": sync_result.get("message", "Unknown"),
                    "triggered_at": datetime.utcnow().isoformat()
                })
                
                logger.info(f"Triggered sync for {obj_info['object_type']}: {sync_result.get('message', 'Unknown')}")
                
            except Exception as e:
                logger.error(f"Error triggering sync for {obj_info['object_type']}: {str(e)}")
                sync_results.append({
                    "object_type": obj_info["object_type"],
                    "display_name": obj_info["display_name"],
                    "success": False,
                    "message": f"Error: {str(e)}",
                    "triggered_at": datetime.utcnow().isoformat()
                })
        
        # Update final status
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 100,
                "total": 100,
                "status": f"Completed sync check for {len(objects_to_sync)} objects",
                "task_id": task_id
            }
        )
        
        successful_syncs = len([r for r in sync_results if r["success"]])
        
        logger.info(f"Smart sync scheduler completed: {successful_syncs}/{len(sync_results)} syncs triggered successfully")
        
        return {
            "success": True,
            "task_id": task_id,
            "objects_checked": len(enabled_configs),
            "objects_synced": len(objects_to_sync),
            "successful_syncs": successful_syncs,
            "sync_results": sync_results,
            "completed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Smart sync scheduler task {task_id} failed: {str(e)}")
        return {
            "success": False,
            "task_id": task_id,
            "error": str(e),
            "failed_at": datetime.utcnow().isoformat()
        }
    finally:
        db.close()


def _should_sync_object_type(config, db: Session) -> bool:
    """
    Check if an object type should be synced based on its configuration and last sync time.
    """
    try:
        # Check if enough time has passed since last sync
        if config.last_sync:
            time_since_last_sync = datetime.utcnow() - config.last_sync.replace(tzinfo=None)
            interval_seconds = config.sync_interval_minutes * 60
            
            if time_since_last_sync.total_seconds() < interval_seconds:
                return False  # Not enough time has passed
        
        # For objects that have never been synced, always sync
        if not config.last_sync:
            return True
        
        # Additional checks could be added here (e.g., staleness detection)
        return True
        
    except Exception as e:
        logger.error(f"Error checking sync status for {config.object_type}: {str(e)}")
        return False


def _trigger_object_sync(object_type: str, db: Session) -> Dict:
    """
    Trigger sync for a specific object type.
    """
    try:
        # Import sync tasks dynamically to avoid circular imports
        if object_type == "directory":
            # Use full sync task for directories
            from tasks.sync_tasks import full_sync_task
            task = full_sync_task.delay()
            return {"success": True, "message": f"Directory sync task triggered", "task_id": task.id}
        
        elif object_type == "project":
            # Use batch sync projects task
            from tasks.sync_tasks import batch_sync_projects_task
            task = batch_sync_projects_task.delay()
            return {"success": True, "message": f"Project sync task triggered", "task_id": task.id}
        
        elif object_type == "phase":
            # Use batch sync projects task (phases are synced with projects)
            from tasks.sync_tasks import batch_sync_projects_task
            task = batch_sync_projects_task.delay()
            return {"success": True, "message": f"Phase sync task triggered", "task_id": task.id}
        
        elif object_type == "elevation":
            # Use batch sync projects task (elevations are synced with projects)
            from tasks.sync_tasks import batch_sync_projects_task
            task = batch_sync_projects_task.delay()
            return {"success": True, "message": f"Elevation sync task triggered", "task_id": task.id}
        
        elif object_type == "elevation_glass":
            # Use batch sync projects task (elevation glass is synced with projects)
            from tasks.sync_tasks import batch_sync_projects_task
            task = batch_sync_projects_task.delay()
            return {"success": True, "message": f"Elevation glass sync task triggered", "task_id": task.id}
        
        elif object_type == "sqlite_parser":
            from tasks.sqlite_parser_tasks import trigger_parsing_for_new_files_task
            task = trigger_parsing_for_new_files_task.delay()
            return {"success": True, "message": f"SQLite parser task triggered", "task_id": task.id}
        
        elif object_type == "parsing_errors":
            # Parsing errors are handled by the parser, no separate task needed
            return {"success": True, "message": f"Parsing errors monitoring (handled by parser)", "task_id": None}
        
        else:
            return {"success": False, "message": f"Unknown object type: {object_type}"}
            
    except Exception as e:
        logger.error(f"Error triggering sync for {object_type}: {str(e)}")
        return {"success": False, "message": f"Error: {str(e)}"}
