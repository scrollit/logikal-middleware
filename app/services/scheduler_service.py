from sqlalchemy.orm import Session
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from celery_app import celery_app
from tasks.sync_tasks import sync_project_task, batch_sync_projects_task, full_sync_task
from tasks.scheduler_tasks import hourly_smart_sync, cleanup_old_tasks, system_health_monitor
import logging

logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Service for managing background sync scheduling and job monitoring.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_task_status(self, task_id: str) -> Dict:
        """
        Get the status of a Celery task.
        """
        try:
            result = celery_app.AsyncResult(task_id)
            
            if result.state == "PENDING":
                return {
                    "task_id": task_id,
                    "status": "PENDING",
                    "message": "Task is waiting to be processed"
                }
            elif result.state == "PROGRESS":
                return {
                    "task_id": task_id,
                    "status": "PROGRESS",
                    "current": result.info.get("current", 0),
                    "total": result.info.get("total", 100),
                    "message": result.info.get("status", "Processing..."),
                    "meta": result.info
                }
            elif result.state == "SUCCESS":
                return {
                    "task_id": task_id,
                    "status": "SUCCESS",
                    "result": result.result,
                    "completed_at": result.result.get("completed_at") if isinstance(result.result, dict) else None
                }
            elif result.state == "FAILURE":
                return {
                    "task_id": task_id,
                    "status": "FAILURE",
                    "error": str(result.info),
                    "failed_at": result.result.get("failed_at") if isinstance(result.result, dict) else None
                }
            else:
                return {
                    "task_id": task_id,
                    "status": result.state,
                    "info": result.info
                }
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {str(e)}")
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": str(e)
            }

    def start_project_sync(self, project_id: str, force_sync: bool = False) -> Dict:
        """
        Start a background sync for a specific project.
        """
        try:
            task = sync_project_task.delay(project_id, force_sync)
            return {
                "success": True,
                "task_id": task.id,
                "project_id": project_id,
                "force_sync": force_sync,
                "started_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error starting project sync for {project_id}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "project_id": project_id
            }

    def start_batch_sync(self, project_ids: List[str], force_sync: bool = False) -> Dict:
        """
        Start a background batch sync for multiple projects.
        """
        try:
            task = batch_sync_projects_task.delay(project_ids, force_sync)
            return {
                "success": True,
                "task_id": task.id,
                "project_ids": project_ids,
                "project_count": len(project_ids),
                "force_sync": force_sync,
                "started_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error starting batch sync for {len(project_ids)} projects: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "project_count": len(project_ids)
            }

    def start_full_sync(self) -> Dict:
        """
        Start a background full sync of all projects.
        """
        try:
            task = full_sync_task.delay()
            return {
                "success": True,
                "task_id": task.id,
                "sync_type": "full",
                "started_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error starting full sync: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_active_tasks(self) -> Dict:
        """
        Get information about currently active tasks.
        """
        try:
            # Get active tasks from Celery
            inspect = celery_app.control.inspect()
            active_tasks = inspect.active()
            
            if not active_tasks:
                return {
                    "active_tasks": [],
                    "total_active": 0,
                    "checked_at": datetime.utcnow().isoformat()
                }
            
            # Flatten the results (Celery returns per-worker dict)
            all_active_tasks = []
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    task["worker"] = worker
                    all_active_tasks.append(task)
            
            return {
                "active_tasks": all_active_tasks,
                "total_active": len(all_active_tasks),
                "checked_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting active tasks: {str(e)}")
            return {
                "active_tasks": [],
                "total_active": 0,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

    def get_scheduled_tasks(self) -> Dict:
        """
        Get information about scheduled tasks.
        """
        try:
            inspect = celery_app.control.inspect()
            scheduled_tasks = inspect.scheduled()
            
            if not scheduled_tasks:
                return {
                    "scheduled_tasks": [],
                    "total_scheduled": 0,
                    "checked_at": datetime.utcnow().isoformat()
                }
            
            # Flatten the results
            all_scheduled_tasks = []
            for worker, tasks in scheduled_tasks.items():
                for task in tasks:
                    task["worker"] = worker
                    all_scheduled_tasks.append(task)
            
            return {
                "scheduled_tasks": all_scheduled_tasks,
                "total_scheduled": len(all_scheduled_tasks),
                "checked_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting scheduled tasks: {str(e)}")
            return {
                "scheduled_tasks": [],
                "total_scheduled": 0,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

    def get_worker_stats(self) -> Dict:
        """
        Get statistics about Celery workers.
        """
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if not stats:
                return {
                    "workers": [],
                    "total_workers": 0,
                    "checked_at": datetime.utcnow().isoformat()
                }
            
            worker_list = []
            for worker_name, worker_stats in stats.items():
                worker_info = {
                    "name": worker_name,
                    "status": "online",
                    "stats": worker_stats
                }
                worker_list.append(worker_info)
            
            return {
                "workers": worker_list,
                "total_workers": len(worker_list),
                "checked_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting worker stats: {str(e)}")
            return {
                "workers": [],
                "total_workers": 0,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

    def cancel_task(self, task_id: str) -> Dict:
        """
        Cancel a running task.
        """
        try:
            celery_app.control.revoke(task_id, terminate=True)
            return {
                "success": True,
                "task_id": task_id,
                "cancelled_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error cancelling task {task_id}: {str(e)}")
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e)
            }

    def get_scheduler_status(self) -> Dict:
        """
        Get overall scheduler status and configuration.
        """
        try:
            # Get beat schedule (periodic tasks)
            beat_schedule = celery_app.conf.beat_schedule
            
            # Get worker stats
            worker_stats = self.get_worker_stats()
            
            # Get active tasks
            active_tasks = self.get_active_tasks()
            
            return {
                "scheduler_enabled": True,
                "beat_schedule": beat_schedule,
                "worker_stats": worker_stats,
                "active_tasks": active_tasks,
                "background_sync_enabled": self._is_background_sync_enabled(),
                "sync_interval_seconds": self._get_sync_interval(),
                "checked_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting scheduler status: {str(e)}")
            return {
                "scheduler_enabled": False,
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

    def _is_background_sync_enabled(self) -> bool:
        """
        Check if background sync is enabled.
        """
        try:
            import os
            return os.getenv("BACKGROUND_SYNC_ENABLED", "false").lower() == "true"
        except:
            return False

    def _get_sync_interval(self) -> int:
        """
        Get the configured sync interval in seconds.
        """
        try:
            import os
            return int(os.getenv("SYNC_INTERVAL_SECONDS", "3600"))
        except:
            return 3600
