from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    "ai_agents_data_api",
    broker=f"redis://localhost:6379/0",
    backend=f"redis://localhost:6379/1",
    include=[
        "app.tasks.queries",
        "app.tasks.sync",
        "app.tasks.cleanup",
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    worker_prefetch_multiplier=1,  # One task per worker at a time
    task_routes={
        "app.tasks.queries.*": {"queue": "queries"},
        "app.tasks.sync.*": {"queue": "sync"},
        "app.tasks.cleanup.*": {"queue": "cleanup"},
    },
    # Beat schedule
    beat_schedule={
        "cleanup-old-jobs": {
            "task": "app.tasks.cleanup.cleanup_old_jobs",
            "schedule": crontab(hour="*/6"),  # Every 6 hours
            "kwargs": {
                "job_age_hours": 24,  # Keep completed jobs for 24 hours
                "failed_job_age_hours": 72,  # Keep failed jobs for 72 hours
            },
        },
        "cleanup-old-query-results": {
            "task": "app.tasks.queries.cleanup_old_results",
            "schedule": crontab(hour="*/4"),  # Every 4 hours
            "kwargs": {
                "max_age_hours": 24,  # Keep query results for 24 hours
            },
        },
        "cleanup-stale-jobs": {
            "task": "app.tasks.cleanup.cleanup_old_jobs",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "kwargs": {
                "job_age_hours": 1,  # Mark jobs as failed if running for more than 1 hour
                "failed_job_age_hours": 1,
            },
        },
    }
) 