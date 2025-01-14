from celery import Celery
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
    }
) 