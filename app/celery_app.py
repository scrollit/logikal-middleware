from celery import Celery
from core.config import settings
import os

# Create Celery instance
celery_app = Celery(
    "logikal_middleware",
    broker=f"redis://{os.getenv('REDIS_HOST', 'logikal-redis')}:{os.getenv('REDIS_PORT', '6379')}/0",
    backend=f"redis://{os.getenv('REDIS_HOST', 'logikal-redis')}:{os.getenv('REDIS_PORT', '6379')}/0",
    include=[
        "tasks.sync_tasks",
        "tasks.scheduler_tasks",
        "tasks.sqlite_parser_tasks"
    ]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    # Result backend settings
    result_expires=3600,  # 1 hour
    # Task routing
    task_routes={
        "tasks.sync_tasks.*": {"queue": "sync"},
        "tasks.scheduler_tasks.*": {"queue": "scheduler"},
        "tasks.sqlite_parser_tasks.*": {"queue": "sqlite_parser"},
    },
    # Periodic task settings
    beat_schedule={
        # Disabled scheduled sync - syncs should be triggered manually only
        # "hourly-smart-sync": {
        #     "task": "tasks.scheduler_tasks.hourly_smart_sync",
        #     "schedule": 3600.0,  # Every hour
        #     "options": {"queue": "scheduler"}
        # },
    },
    beat_schedule_filename="/tmp/celerybeat-schedule",
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Optional: Configure task result backend settings
celery_app.conf.result_backend_transport_options = {
    "master_name": "mymaster",
}

if __name__ == "__main__":
    celery_app.start()
