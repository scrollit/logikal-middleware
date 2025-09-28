from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime


class TaskStatusResponse(BaseModel):
    """Response model for task status information"""
    task_id: str
    status: str
    current: Optional[int] = None
    total: Optional[int] = None
    message: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    meta: Optional[Dict] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None


class StartSyncResponse(BaseModel):
    """Response model for starting sync operations"""
    success: bool
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    project_ids: Optional[List[str]] = None
    project_count: Optional[int] = None
    sync_type: Optional[str] = None
    force_sync: Optional[bool] = None
    started_at: str
    error: Optional[str] = None


class ActiveTaskInfo(BaseModel):
    """Information about an active task"""
    id: str
    name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    type: str
    hostname: str
    time_start: float
    worker: Optional[str] = None


class ScheduledTaskInfo(BaseModel):
    """Information about a scheduled task"""
    id: str
    name: str
    args: List[Any]
    kwargs: Dict[str, Any]
    eta: Optional[str] = None
    expires: Optional[str] = None
    worker: Optional[str] = None


class WorkerInfo(BaseModel):
    """Information about a Celery worker"""
    name: str
    status: str
    stats: Dict[str, Any]


class ActiveTasksResponse(BaseModel):
    """Response model for active tasks information"""
    active_tasks: List[ActiveTaskInfo]
    total_active: int
    checked_at: datetime


class ScheduledTasksResponse(BaseModel):
    """Response model for scheduled tasks information"""
    scheduled_tasks: List[ScheduledTaskInfo]
    total_scheduled: int
    checked_at: datetime


class WorkerStatsResponse(BaseModel):
    """Response model for worker statistics"""
    workers: List[WorkerInfo]
    total_workers: int
    checked_at: datetime


class CancelTaskResponse(BaseModel):
    """Response model for task cancellation"""
    success: bool
    task_id: str
    cancelled_at: Optional[datetime] = None
    error: Optional[str] = None


class SchedulerStatusResponse(BaseModel):
    """Response model for overall scheduler status"""
    scheduler_enabled: bool
    beat_schedule: Dict[str, Any]
    worker_stats: WorkerStatsResponse
    active_tasks: ActiveTasksResponse
    background_sync_enabled: bool
    sync_interval_seconds: int
    checked_at: datetime


class SyncJobInfo(BaseModel):
    """Information about a sync job"""
    task_id: str
    project_id: Optional[str] = None
    project_ids: Optional[List[str]] = None
    sync_type: str  # "project", "batch", "full", "hourly"
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    progress: Optional[Dict] = None
    result: Optional[Dict] = None
    error: Optional[str] = None


class SyncJobsResponse(BaseModel):
    """Response model for sync jobs information"""
    jobs: List[SyncJobInfo]
    total_jobs: int
    active_jobs: int
    completed_jobs: int
    failed_jobs: int


class SchedulerConfigResponse(BaseModel):
    """Response model for scheduler configuration"""
    background_sync_enabled: bool
    sync_interval_seconds: int
    max_concurrent_tasks: int
    task_timeout_seconds: int
    retry_attempts: int
    retry_delay_seconds: int
    cleanup_enabled: bool
    cleanup_interval_days: int
