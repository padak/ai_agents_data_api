import json
from datetime import datetime
from typing import Dict, Any, Optional

from celery import Task

from app.core.celery import celery_app
from app.db.duckdb import get_duckdb_connection
from app.db.snowflake import SnowflakeClient
from app.schemas.sync import SyncStatus, SyncStrategy


class SyncTask(Task):
    _db = None
    _snowflake = None

    @property
    def db(self):
        if self._db is None:
            self._db = get_duckdb_connection()
        return self._db

    @property
    def snowflake(self):
        if self._snowflake is None:
            self._snowflake = SnowflakeClient()
        return self._snowflake


@celery_app.task(bind=True, base=SyncTask)
def sync_table(
    self,
    sync_id: str,
    table_name: str,
    schema_name: str,
    strategy: str,
    incremental_key: Optional[str] = None,
    filter_condition: Optional[str] = None,
    batch_size: int = 10000
) -> Dict[str, Any]:
    """Synchronize data from Snowflake to DuckDB"""
    try:
        # Update status to running
        self.db.execute("""
            UPDATE sync_jobs
            SET status = ?, started_at = ?
            WHERE sync_id = ?
        """, [SyncStatus.RUNNING, datetime.utcnow(), sync_id])

        # Get Snowflake schema
        columns = self.snowflake.fetch_schema(table_name, schema_name)

        # Create or update DuckDB table
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

        # Get data and sync
        if strategy == SyncStrategy.INCREMENTAL:
            # Get last sync value
            result = self.db.execute("""
                SELECT stats
                FROM sync_jobs
                WHERE table_id = (
                    SELECT table_id
                    FROM allowed_tables
                    WHERE table_name = ?
                    AND schema_name = ?
                )
                AND status = 'completed'
                ORDER BY completed_at DESC
                LIMIT 1
            """, [table_name, schema_name]).fetchone()

            last_value = None
            if result and result[0]:
                stats = json.loads(result[0])
                last_value = stats.get("last_value")

            cursor, total_rows = self.snowflake.fetch_incremental_data(
                table_name=table_name,
                schema_name=schema_name,
                incremental_key=incremental_key,
                last_value=last_value,
                batch_size=batch_size,
                additional_where=filter_condition
            )
        else:
            cursor, total_rows = self.snowflake.fetch_data(
                table_name=table_name,
                schema_name=schema_name,
                batch_size=batch_size,
                where_clause=filter_condition
            )

        # Process data
        df = cursor.fetch_pandas_all()
        if not df.empty:
            # For full sync, truncate first
            if strategy == SyncStrategy.FULL:
                self.db.execute(f"DELETE FROM {schema_name}.{table_name}")

            # Insert data
            self.db.register("temp_df", df)
            self.db.execute(f"""
                INSERT INTO {schema_name}.{table_name}
                SELECT * FROM temp_df
            """)

        # Get table stats
        table_stats = self.snowflake.fetch_table_stats(table_name, schema_name)
        
        # Update sync status
        stats = {
            "rows_processed": len(df),
            "total_rows": total_rows,
            "table_stats": table_stats
        }

        if strategy == SyncStrategy.INCREMENTAL and incremental_key and not df.empty:
            stats["last_value"] = str(df[incremental_key].max())

        completed_at = datetime.utcnow()
        self.db.execute("""
            UPDATE sync_jobs
            SET status = ?, completed_at = ?, stats = ?
            WHERE sync_id = ?
        """, [SyncStatus.COMPLETED, completed_at, json.dumps(stats), sync_id])

        # Update table sync status
        self.db.execute("""
            UPDATE table_sync_status
            SET last_sync_id = ?,
                last_sync_status = ?,
                last_sync_at = ?,
                row_count = ?,
                size_bytes = ?
            WHERE table_id = (
                SELECT table_id
                FROM allowed_tables
                WHERE table_name = ?
                AND schema_name = ?
            )
        """, [
            sync_id,
            SyncStatus.COMPLETED,
            completed_at,
            table_stats["row_count"],
            table_stats["size_bytes"],
            table_name,
            schema_name
        ])

        return {
            "status": SyncStatus.COMPLETED,
            "stats": stats
        }

    except Exception as e:
        error_msg = str(e)
        self.db.execute("""
            UPDATE sync_jobs
            SET status = ?, completed_at = ?, error = ?
            WHERE sync_id = ?
        """, [SyncStatus.FAILED, datetime.utcnow(), error_msg, sync_id])

        # Update table sync status
        self.db.execute("""
            UPDATE table_sync_status
            SET last_sync_status = ?, last_error = ?
            WHERE table_id = (
                SELECT table_id
                FROM allowed_tables
                WHERE table_name = ?
                AND schema_name = ?
            )
        """, [SyncStatus.FAILED, error_msg, table_name, schema_name])

        return {
            "status": SyncStatus.FAILED,
            "error": error_msg
        } 