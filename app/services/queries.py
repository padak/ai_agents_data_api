from typing import Optional, Dict, Any
import uuid
import datetime
import pandas as pd
import duckdb
from app.core.config import settings
from app.schemas.queries import OutputFormat, QueryConfig, QueryResponse
import json
import os

class QueryService:
    def __init__(self):
        self._duckdb = None

    @property
    def duckdb(self):
        if self._duckdb is None:
            import duckdb
            from app.core.config import settings
            self._duckdb = duckdb.connect(settings.DUCKDB_PATH)
            self._init_tables()
        return self._duckdb

    def _init_tables(self):
        """Initialize required tables for query management"""
        self.duckdb.execute("""
            CREATE TABLE IF NOT EXISTS query_jobs (
                job_id VARCHAR PRIMARY KEY,
                query TEXT NOT NULL,
                params JSON,
                status VARCHAR NOT NULL,
                result_file VARCHAR,
                error TEXT,
                stats JSON,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL
            )
        """)

    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None, config: Optional[QueryConfig] = None) -> str:
        """Execute a query and return the job ID"""
        job_id = str(uuid.uuid4())
        config = config or QueryConfig()
        
        try:
            # Start query execution
            self.duckdb.execute("""
                INSERT INTO query_jobs (job_id, query, params, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [job_id, query, json.dumps(params), "RUNNING", datetime.utcnow(), datetime.utcnow()])

            # Execute query
            result = self.duckdb.execute(query, params).df()
            
            # Save results
            output_file = f"data/query_results/{job_id}"
            if config.output_format == OutputFormat.CSV:
                result.to_csv(f"{output_file}.csv", index=False)
                output_file = f"{output_file}.csv"
            elif config.output_format == OutputFormat.PARQUET:
                result.to_parquet(f"{output_file}.parquet")
                output_file = f"{output_file}.parquet"
            else:
                result.to_json(f"{output_file}.json", orient="records")
                output_file = f"{output_file}.json"

            # Update job status
            stats = {
                "row_count": len(result),
                "column_count": len(result.columns),
                "file_size": os.path.getsize(output_file)
            }
            self.duckdb.execute("""
                UPDATE query_jobs
                SET status = ?, result_file = ?, stats = ?, updated_at = ?
                WHERE job_id = ?
            """, ["COMPLETED", output_file, json.dumps(stats), datetime.utcnow(), job_id])

            return job_id

        except Exception as e:
            # Update job status with error
            self.duckdb.execute("""
                UPDATE query_jobs
                SET status = ?, error = ?, updated_at = ?
                WHERE job_id = ?
            """, ["FAILED", str(e), datetime.utcnow(), job_id])
            raise

    async def get_job_status(self, job_id: str) -> QueryResponse:
        """Get the status of a query job"""
        result = self.duckdb.execute("""
            SELECT job_id, query, params, status, result_file, error, stats, created_at, updated_at
            FROM query_jobs
            WHERE job_id = ?
        """, [job_id]).fetchone()

        if not result:
            raise ValueError(f"Query job {job_id} not found")

        return QueryResponse(
            job_id=result[0],
            query=result[1],
            params=json.loads(result[2]) if result[2] else None,
            status=result[3],
            result_file=result[4],
            error=result[5],
            stats=json.loads(result[6]) if result[6] else None,
            created_at=result[7],
            updated_at=result[8]
        ) 