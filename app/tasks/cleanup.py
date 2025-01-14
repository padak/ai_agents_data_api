from datetime import datetime, timedelta
from typing import Dict, Any

from celery import Task

from app.core.celery import celery_app
from app.db.duckdb import get_duckdb_connection
from app.schemas.sync import SyncStatus


class CleanupTask(Task):
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_duckdb_connection()
        return self._db


@celery_app.task(bind=True, base=CleanupTask)
def cleanup_old_jobs(
    self,
    job_age_hours: int = 24,
    failed_job_age_hours: int = 72
) -> Dict[str, Any]:
    """Clean up old sync and query jobs"""
    try:
        now = datetime.utcnow()
        completed_cutoff = now - timedelta(hours=job_age_hours)
        failed_cutoff = now - timedelta(hours=failed_job_age_hours)

        # Clean up old sync jobs
        self.db.execute("""
            DELETE FROM sync_jobs
            WHERE (status = ? AND completed_at < ?)
            OR (status = ? AND completed_at < ?)
        """, [
            SyncStatus.COMPLETED, completed_cutoff,
            SyncStatus.FAILED, failed_cutoff
        ])

        # Clean up old query jobs
        self.db.execute("""
            DELETE FROM query_jobs
            WHERE (status = ? AND completed_at < ?)
            OR (status = ? AND completed_at < ?)
        """, [
            SyncStatus.COMPLETED, completed_cutoff,
            SyncStatus.FAILED, failed_cutoff
        ])

        # Clean up stale running jobs
        stale_cutoff = now - timedelta(hours=1)
        self.db.execute("""
            UPDATE sync_jobs
            SET status = ?, error = ?, completed_at = ?
            WHERE status = ?
            AND started_at < ?
        """, [
            SyncStatus.FAILED,
            "Job timed out",
            now,
            SyncStatus.RUNNING,
            stale_cutoff
        ])

        self.db.execute("""
            UPDATE query_jobs
            SET status = ?, error = ?, completed_at = ?
            WHERE status = ?
            AND started_at < ?
        """, [
            SyncStatus.FAILED,
            "Job timed out",
            now,
            SyncStatus.RUNNING,
            stale_cutoff
        ])

        return {
            "status": "success",
            "message": "Cleanup completed successfully"
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        } 