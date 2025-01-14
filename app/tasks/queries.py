import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

import pandas as pd
from celery import Task
from celery.exceptions import MaxRetriesExceededError
from duckdb import OperationalError, ProgrammingError

from app.core.celery import celery_app
from app.db.duckdb import get_duckdb_connection
from app.schemas.data import OutputFormat, QueryStatus


class QueryTask(Task):
    _db = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_duckdb_connection()
        return self._db

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        query_id = kwargs.get('query_id') or args[0]
        
        error_msg = f"Task failed: {str(exc)}"
        if isinstance(exc, MaxRetriesExceededError):
            error_msg = f"Max retries exceeded: {str(exc.__cause__)}"

        try:
            self.db.execute("""
                UPDATE query_jobs
                SET status = ?, completed_at = ?, error = ?
                WHERE job_id = ?
            """, [QueryStatus.FAILED, datetime.utcnow(), error_msg, query_id])
        except Exception:
            pass  # Don't raise new exceptions in failure handler


@celery_app.task(
    bind=True,
    base=QueryTask,
    autoretry_for=(OperationalError, ProgrammingError),
    retry_kwargs={'max_retries': 2},
    retry_backoff=True,
    retry_backoff_max=300,  # Max delay of 5 minutes
    retry_jitter=True
)
def execute_query(
    self,
    query_id: str,
    query: str,
    output_format: str,
    params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Execute a query asynchronously"""
    try:
        # Update status to running
        self.db.execute("""
            UPDATE query_jobs
            SET status = ?, started_at = ?, retries = ?
            WHERE job_id = ?
        """, [QueryStatus.RUNNING, datetime.utcnow(), self.request.retries, query_id])

        # Execute query
        result = self.db.execute(query).df()
        
        # Save result based on format
        output_dir = Path("./data/query_results")
        output_dir.mkdir(exist_ok=True)
        
        file_name = f"query_{query_id}"
        if output_format == OutputFormat.CSV:
            file_path = output_dir / f"{file_name}.csv"
            result.to_csv(file_path, index=False)
        elif output_format == OutputFormat.PARQUET:
            file_path = output_dir / f"{file_name}.parquet"
            result.to_parquet(file_path, index=False)
        else:  # JSON
            file_path = output_dir / f"{file_name}.json"
            result.to_json(file_path, orient="records")

        # Update job status
        stats = {
            "row_count": len(result),
            "column_count": len(result.columns),
            "file_size": file_path.stat().st_size,
        }
        
        self.db.execute("""
            UPDATE query_jobs
            SET status = ?, completed_at = ?, result_path = ?, stats = ?
            WHERE job_id = ?
        """, [
            QueryStatus.COMPLETED,
            datetime.utcnow(),
            str(file_path),
            json.dumps(stats),
            query_id
        ])

        return {
            "status": QueryStatus.COMPLETED,
            "result_path": str(file_path),
            "stats": stats
        }

    except (OperationalError, ProgrammingError) as e:
        # These exceptions will trigger automatic retry
        raise

    except Exception as e:
        error_msg = str(e)
        self.db.execute("""
            UPDATE query_jobs
            SET status = ?, completed_at = ?, error = ?
            WHERE job_id = ?
        """, [QueryStatus.FAILED, datetime.utcnow(), error_msg, query_id])
        
        return {
            "status": QueryStatus.FAILED,
            "error": error_msg
        }


@celery_app.task(
    bind=True,
    base=QueryTask,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 1},
    retry_backoff=True
)
def cleanup_old_results(self, max_age_hours: int = 24) -> Dict[str, int]:
    """Clean up old query results"""
    try:
        # Find old results
        cutoff = datetime.utcnow() - pd.Timedelta(hours=max_age_hours)
        results = self.db.execute("""
            SELECT job_id, result_path
            FROM query_jobs
            WHERE completed_at < ?
            AND result_path IS NOT NULL
        """, [cutoff]).fetchall()

        deleted_count = 0
        for job_id, result_path in results:
            path = Path(result_path)
            if path.exists():
                path.unlink()
                deleted_count += 1

        return {
            "deleted_count": deleted_count,
            "processed_count": len(results)
        }

    except Exception as e:
        return {
            "error": str(e),
            "deleted_count": 0,
            "processed_count": 0
        } 