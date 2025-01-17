import logging
from celery import Celery
from celery.signals import task_failure
from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

celery_app = Celery(
    "ai_agents_data_api",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.queries",
        "app.tasks.sync",
        "app.tasks.cleanup"
    ]
)

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
        "app.tasks.cleanup.*": {"queue": "cleanup"}
    }
)

@task_failure.connect
def handle_task_failure(task_id, exc, args, kwargs, traceback, *args_, **kwargs_):
    """Log detailed information about task failures"""
    logger.error(
        f"Task {task_id} failed: {exc}\n"
        f"Args: {args}\nKwargs: {kwargs}\n"
        f"Traceback:\n{traceback}"
    ) 