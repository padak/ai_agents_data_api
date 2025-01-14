import uuid
from datetime import datetime
import pandas as pd
from typing import Optional, Dict, Any

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.duckdb import get_duckdb_connection
from app.db.snowflake import SnowflakeClient
from app.schemas.sync import (
    SyncRequest,
    SyncResponse,
    SyncConfig,
    TableSyncStatus,
    SyncStatus,
    SyncStrategy,
)


class SyncService:
    def __init__(self):
        self.db = get_duckdb_connection()
        self.snowflake = SnowflakeClient()
        self._init_tables()

    def _init_tables(self):
        """Initialize the required tables if they don't exist"""
        # Sync jobs table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS sync_jobs (
                sync_id VARCHAR PRIMARY KEY,
                table_id VARCHAR NOT NULL,
                strategy VARCHAR NOT NULL,
                status VARCHAR NOT NULL,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error TEXT,
                stats JSON,
                FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id)
            )
        """)

        # Table sync status
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS table_sync_status (
                table_id VARCHAR PRIMARY KEY,
                last_sync_id VARCHAR,
                last_sync_status VARCHAR,
                last_sync_at TIMESTAMP,
                last_error TEXT,
                row_count INTEGER,
                size_bytes INTEGER,
                FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id),
                FOREIGN KEY (last_sync_id) REFERENCES sync_jobs(sync_id)
            )
        """)

    async def _create_duckdb_table(
        self,
        table_name: str,
        schema_name: str,
        columns: list
    ):
        """Create or update DuckDB table schema"""
        # Map Snowflake types to DuckDB types
        type_mapping = {
            "NUMBER": "DOUBLE",
            "FLOAT": "DOUBLE",
            "VARCHAR": "VARCHAR",
            "CHAR": "VARCHAR",
            "TEXT": "VARCHAR",
            "BOOLEAN": "BOOLEAN",
            "DATE": "DATE",
            "TIMESTAMP_NTZ": "TIMESTAMP",
            "TIMESTAMP_TZ": "TIMESTAMP",
            "TIMESTAMP_LTZ": "TIMESTAMP",
        }

        # Build column definitions
        column_defs = []
        for col in columns:
            name = col[0]
            sf_type = col[1]
            nullable = col[5] == "YES"
            
            # Map type
            duck_type = type_mapping.get(sf_type, "VARCHAR")
            
            # Add length for VARCHAR if specified
            if duck_type == "VARCHAR" and col[2]:
                duck_type = f"VARCHAR({col[2]})"
            
            # Add nullable constraint
            if not nullable:
                duck_type += " NOT NULL"
            
            column_defs.append(f"{name} {duck_type}")

        # Create table
        create_query = f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.{table_name} (
                {', '.join(column_defs)}
            )
        """
        self.db.execute(create_query)

    async def _sync_batch(
        self,
        cursor: Any,
        table_name: str,
        schema_name: str,
        strategy: SyncStrategy
    ) -> Dict[str, int]:
        """Sync a batch of data from Snowflake to DuckDB"""
        # Convert Snowflake cursor to pandas DataFrame
        df = cursor.fetch_pandas_all()
        if df.empty:
            return {"rows_processed": 0}

        # For full sync, truncate first
        if strategy == SyncStrategy.FULL:
            self.db.execute(f"DELETE FROM {schema_name}.{table_name}")

        # Insert data
        self.db.register("temp_df", df)
        self.db.execute(f"""
            INSERT INTO {schema_name}.{table_name}
            SELECT * FROM temp_df
        """)

        return {"rows_processed": len(df)}

    async def start_sync(
        self,
        sync_request: SyncRequest,
        config: Optional[SyncConfig] = None
    ) -> SyncResponse:
        """Start a table synchronization"""
        config = config or SyncConfig()
        
        # Get table ID
        result = self.db.execute("""
            SELECT table_id
            FROM allowed_tables
            WHERE table_name = ? AND schema_name = ? AND status = 'active'
        """, [sync_request.table_name, sync_request.schema_name]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {sync_request.schema_name}.{sync_request.table_name} not found or not allowed"
            )

        table_id = result[0]
        sync_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        # Create sync job
        self.db.execute("""
            INSERT INTO sync_jobs (
                sync_id, table_id, strategy, status, started_at
            ) VALUES (?, ?, ?, ?, ?)
        """, [sync_id, table_id, sync_request.strategy, SyncStatus.RUNNING, started_at])

        try:
            # Get Snowflake schema
            columns = self.snowflake.fetch_schema(
                sync_request.table_name,
                sync_request.schema_name
            )

            # Create or update DuckDB table
            await self._create_duckdb_table(
                sync_request.table_name,
                sync_request.schema_name,
                columns
            )

            # Get data and sync
            if sync_request.strategy == SyncStrategy.INCREMENTAL:
                # Get last sync value
                result = self.db.execute("""
                    SELECT stats
                    FROM sync_jobs
                    WHERE table_id = ? AND status = 'completed'
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, [table_id]).fetchone()

                last_value = None
                if result and result[0]:
                    stats = result[0]
                    last_value = stats.get("last_value")

                cursor, total_rows = self.snowflake.fetch_incremental_data(
                    table_name=sync_request.table_name,
                    schema_name=sync_request.schema_name,
                    incremental_key=sync_request.incremental_key,
                    last_value=last_value,
                    batch_size=config.batch_size,
                    additional_where=sync_request.filter_condition
                )
            else:
                cursor, total_rows = self.snowflake.fetch_data(
                    table_name=sync_request.table_name,
                    schema_name=sync_request.schema_name,
                    batch_size=config.batch_size,
                    where_clause=sync_request.filter_condition
                )

            # Process data
            stats = await self._sync_batch(
                cursor,
                sync_request.table_name,
                sync_request.schema_name,
                sync_request.strategy
            )
            stats["total_rows"] = total_rows

            # Update sync status
            completed_at = datetime.utcnow()
            self.db.execute("""
                UPDATE sync_jobs
                SET status = ?, completed_at = ?, stats = ?
                WHERE sync_id = ?
            """, [SyncStatus.COMPLETED, completed_at, stats, sync_id])

            # Update table sync status
            table_stats = self.snowflake.fetch_table_stats(
                sync_request.table_name,
                sync_request.schema_name
            )
            self.db.execute("""
                INSERT INTO table_sync_status (
                    table_id, last_sync_id, last_sync_status,
                    last_sync_at, row_count, size_bytes
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (table_id) DO UPDATE SET
                    last_sync_id = excluded.last_sync_id,
                    last_sync_status = excluded.last_sync_status,
                    last_sync_at = excluded.last_sync_at,
                    row_count = excluded.row_count,
                    size_bytes = excluded.size_bytes
            """, [
                table_id, sync_id, SyncStatus.COMPLETED,
                completed_at, table_stats["row_count"],
                table_stats["size_bytes"]
            ])

            return SyncResponse(
                sync_id=sync_id,
                table_name=sync_request.table_name,
                schema_name=sync_request.schema_name,
                strategy=sync_request.strategy,
                status=SyncStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                stats=stats
            )

        except Exception as e:
            error_msg = str(e)
            self.db.execute("""
                UPDATE sync_jobs
                SET status = ?, completed_at = ?, error = ?
                WHERE sync_id = ?
            """, [SyncStatus.FAILED, datetime.utcnow(), error_msg, sync_id])

            self.db.execute("""
                UPDATE table_sync_status
                SET last_sync_status = ?, last_error = ?
                WHERE table_id = ?
            """, [SyncStatus.FAILED, error_msg, table_id])

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Sync failed: {error_msg}"
            )

    async def get_sync_status(self, sync_id: str) -> SyncResponse:
        """Get the status of a sync job"""
        result = self.db.execute("""
            SELECT 
                j.sync_id,
                t.table_name,
                t.schema_name,
                j.strategy,
                j.status,
                j.started_at,
                j.completed_at,
                j.error,
                j.stats
            FROM sync_jobs j
            JOIN allowed_tables t ON j.table_id = t.table_id
            WHERE j.sync_id = ?
        """, [sync_id]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sync job {sync_id} not found"
            )

        return SyncResponse(
            sync_id=result[0],
            table_name=result[1],
            schema_name=result[2],
            strategy=result[3],
            status=result[4],
            started_at=result[5],
            completed_at=result[6],
            error=result[7],
            stats=result[8]
        )

    async def get_table_sync_status(
        self, table_name: str, schema_name: str
    ) -> TableSyncStatus:
        """Get sync status for a table"""
        result = self.db.execute("""
            SELECT 
                t.table_id,
                t.table_name,
                t.schema_name,
                s.last_sync_id,
                s.last_sync_status,
                s.last_sync_at,
                s.last_error,
                s.row_count,
                s.size_bytes
            FROM allowed_tables t
            LEFT JOIN table_sync_status s ON t.table_id = s.table_id
            WHERE t.table_name = ? AND t.schema_name = ?
        """, [table_name, schema_name]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Table {schema_name}.{table_name} not found"
            )

        return TableSyncStatus(
            table_id=result[0],
            table_name=result[1],
            schema_name=result[2],
            last_sync_id=result[3],
            last_sync_status=result[4],
            last_sync_at=result[5],
            last_error=result[6],
            row_count=result[7] or 0,
            size_bytes=result[8] or 0
        ) 