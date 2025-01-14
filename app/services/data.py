import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import duckdb
import pandas as pd
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.duckdb import get_duckdb_connection
from app.schemas.data import (
    DataSampleRequest,
    QueryRequest,
    QueryResponse,
    QueryStatusResponse,
    TableMetadata,
    ProfileRequest,
    QueryStatus,
    SampleType,
    OutputFormat,
)


class DataService:
    def __init__(self):
        self.db = get_duckdb_connection()
        self._init_tables()

    def _init_tables(self):
        """Initialize the required tables if they don't exist"""
        # Query jobs table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS query_jobs (
                job_id VARCHAR PRIMARY KEY,
                query TEXT NOT NULL,
                status VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error TEXT,
                result_path TEXT
            )
        """)

        # Table metadata
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS table_metadata (
                table_id UUID PRIMARY KEY,
                table_name VARCHAR NOT NULL,
                schema_name VARCHAR NOT NULL,
                source VARCHAR NOT NULL,
                column_count INTEGER NOT NULL,
                row_count INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                last_updated TIMESTAMP NOT NULL,
                description TEXT,
                FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id)
            )
        """)

        # Table tags
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS table_tags (
                table_id UUID NOT NULL,
                tag VARCHAR NOT NULL,
                PRIMARY KEY (table_id, tag),
                FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id)
            )
        """)

    async def get_table_metadata(self, table_name: str, schema_name: str) -> TableMetadata:
        """Get metadata for a specific table"""
        result = self.db.execute("""
            SELECT 
                t.table_id,
                t.table_name,
                t.schema_name,
                t.source,
                m.column_count,
                m.row_count,
                m.size_bytes,
                m.last_updated,
                m.description,
                array_agg(tt.tag) as tags
            FROM allowed_tables t
            LEFT JOIN table_metadata m ON t.table_id = m.table_id
            LEFT JOIN table_tags tt ON t.table_id = tt.table_id
            WHERE t.table_name = ? 
            AND t.schema_name = ?
            AND t.status = 'active'
            GROUP BY t.table_id, m.column_count, m.row_count, m.size_bytes, 
                     m.last_updated, m.description
        """, [table_name, schema_name]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {schema_name}.{table_name} not found or not allowed"
            )

        return TableMetadata(
            table_id=result[0],
            table_name=result[1],
            schema_name=result[2],
            source=result[3],
            column_count=result[4] or 0,
            row_count=result[5] or 0,
            size_bytes=result[6] or 0,
            last_updated=result[7].isoformat() if result[7] else datetime.utcnow().isoformat(),
            description=result[8],
            tags=result[9] if result[9] else []
        )

    async def get_data_sample(
        self, request: DataSampleRequest
    ) -> Union[str, Dict[str, Any]]:
        """Get a data sample from a table"""
        # Verify table is allowed
        await self.get_table_metadata(request.table_name, request.schema_name)

        # Build query based on sample type
        if request.sample_type == SampleType.FIRST:
            query = f"""
                SELECT * FROM {request.schema_name}.{request.table_name}
                LIMIT {int(request.sample_size)}
            """
        else:  # RANDOM
            query = f"""
                SELECT * FROM {request.schema_name}.{request.table_name}
                USING SAMPLE {float(request.sample_size) * 100}%
            """

        # Execute query and format output
        result = self.db.execute(query).df()
        
        if request.output_format == OutputFormat.JSON:
            return result.to_dict(orient="records")
        
        # For other formats, save to file and return path
        output_dir = Path("./data/samples")
        output_dir.mkdir(exist_ok=True)
        
        file_name = f"sample_{uuid.uuid4()}"
        if request.output_format == OutputFormat.CSV:
            file_path = output_dir / f"{file_name}.csv"
            result.to_csv(file_path, index=False)
        else:  # PARQUET
            file_path = output_dir / f"{file_name}.parquet"
            result.to_parquet(file_path, index=False)
        
        return str(file_path)

    async def submit_query(self, request: QueryRequest) -> QueryResponse:
        """Submit a query for asynchronous execution"""
        job_id = str(uuid.uuid4())
        
        # Store query job
        self.db.execute("""
            INSERT INTO query_jobs (
                job_id, query, status, created_at
            ) VALUES (?, ?, ?, ?)
        """, [job_id, request.query, QueryStatus.PENDING, datetime.utcnow()])

        # In a real application, we would trigger an async task here
        # For now, we'll execute synchronously
        try:
            self.db.execute("""
                UPDATE query_jobs
                SET status = ?, started_at = ?
                WHERE job_id = ?
            """, [QueryStatus.RUNNING, datetime.utcnow(), job_id])

            result = self.db.execute(request.query).df()
            
            # Save result based on format
            output_dir = Path("./data/query_results")
            output_dir.mkdir(exist_ok=True)
            
            file_name = f"query_{job_id}"
            if request.output_format == OutputFormat.CSV:
                file_path = output_dir / f"{file_name}.csv"
                result.to_csv(file_path, index=False)
            elif request.output_format == OutputFormat.PARQUET:
                file_path = output_dir / f"{file_name}.parquet"
                result.to_parquet(file_path, index=False)
            else:  # JSON
                file_path = output_dir / f"{file_name}.json"
                result.to_json(file_path, orient="records")

            self.db.execute("""
                UPDATE query_jobs
                SET status = ?, completed_at = ?, result_path = ?
                WHERE job_id = ?
            """, [QueryStatus.COMPLETED, datetime.utcnow(), str(file_path), job_id])

        except Exception as e:
            self.db.execute("""
                UPDATE query_jobs
                SET status = ?, error = ?, completed_at = ?
                WHERE job_id = ?
            """, [QueryStatus.FAILED, str(e), datetime.utcnow(), job_id])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query execution failed: {str(e)}"
            )

        return QueryResponse(
            job_id=job_id,
            status=QueryStatus.COMPLETED,
            result_url=str(file_path)
        )

    async def get_query_status(self, job_id: str) -> QueryStatusResponse:
        """Get the status of a query job"""
        result = self.db.execute("""
            SELECT status, error, result_path
            FROM query_jobs
            WHERE job_id = ?
        """, [job_id]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Query job {job_id} not found"
            )

        return QueryStatusResponse(
            job_id=job_id,
            status=result[0],
            error=result[1],
            result_url=result[2]
        )

    async def generate_profile(self, request: ProfileRequest) -> Dict[str, Any]:
        """Generate a profile for a table"""
        # This is a placeholder. In a real application, we would:
        # 1. Check if a recent profile exists (unless force_refresh is True)
        # 2. Use pandas-profiling or a similar tool to generate the profile
        # 3. Store the profile results
        # 4. Return the profile data or a URL to the profile report
        
        # For now, return basic statistics
        metadata = await self.get_table_metadata(request.table_name, request.schema_name)
        
        df = self.db.execute(f"""
            SELECT * FROM {request.schema_name}.{request.table_name}
            USING SAMPLE {request.sample_size * 100}%
        """).df()

        return {
            "table_info": metadata.dict(),
            "basic_stats": df.describe().to_dict(),
            "null_counts": df.isnull().sum().to_dict(),
            "sample_size": len(df),
        } 