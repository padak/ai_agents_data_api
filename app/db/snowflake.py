from functools import lru_cache
import snowflake.connector
from snowflake.connector.connection import SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor
import uuid
from typing import Union, List

from app.core.config import settings


def get_snowflake_connection() -> SnowflakeConnection:
    """Get a fresh Snowflake connection"""
    # Extract account identifier from the full URL
    account = settings.SNOWFLAKE_ACCOUNT
    if '.snowflakecomputing.com' in account:
        account = account.replace('.snowflakecomputing.com', '').split('//')[0]
    
    conn = snowflake.connector.connect(
        account=account,
        user=settings.SNOWFLAKE_USER,
        password=settings.SNOWFLAKE_PASSWORD,
        warehouse=settings.SNOWFLAKE_WAREHOUSE,
        database=settings.SNOWFLAKE_DATABASE,
        schema=settings.SNOWFLAKE_SCHEMA,
    )
    return conn


class SnowflakeClient:
    def __init__(self):
        self.conn = get_snowflake_connection()

    def _ensure_connection(self):
        """Ensure we have a valid connection, reconnect if needed"""
        try:
            # Try a simple query to test connection
            cursor = self.conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        except Exception:
            # Connection is invalid, create a new one
            self.conn = get_snowflake_connection()

    def execute(self, query: str, params: Union[tuple, dict, None] = None) -> SnowflakeCursor:
        """Execute a query and return the cursor"""
        self._ensure_connection()
        cursor = self.conn.cursor()
        
        if isinstance(params, tuple):
            # Convert tuple to list for Snowflake
            cursor.execute(query, list(params))
        elif isinstance(params, dict):
            # Use dictionary parameters as is
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        return cursor

    def fetch_schema(self, table_name: str, schema_name: str) -> list:
        """Fetch table schema information"""
        cursor = self.execute(
            'DESC TABLE "KEBOOLA_33"."WORKSPACE_833213390"."data"'
        )
        
        # DESC TABLE returns: name, type, kind, null?, default, primary key, unique key, check, expression, comment
        # We need to transform this to match our expected format: name, type, max_length, precision, scale, nullable
        results = []
        for row in cursor.fetchall():
            name = row[0]
            data_type = row[1]
            nullable = row[3] == 'Y'
            
            # Parse length/precision/scale from type if present
            # Example formats: VARCHAR(16777216), NUMBER(38,0)
            max_length = None
            precision = None
            scale = None
            
            if '(' in data_type:
                base_type = data_type.split('(')[0]
                specs = data_type.split('(')[1].rstrip(')').split(',')
                
                if base_type in ('VARCHAR', 'CHAR', 'TEXT'):
                    max_length = int(specs[0]) if specs else None
                elif base_type in ('NUMBER', 'DECIMAL'):
                    precision = int(specs[0]) if specs else None
                    scale = int(specs[1]) if len(specs) > 1 else 0
            
            results.append((
                name,                   # column_name
                data_type.split('(')[0],  # base data_type
                max_length,            # character_maximum_length
                precision,             # numeric_precision
                scale,                # numeric_scale
                'YES' if nullable else 'NO'  # is_nullable
            ))
        
        return results

    def fetch_table_stats(self, table_name: str, schema_name: str) -> dict:
        """Fetch table statistics"""
        cursor = self.execute("""
            SELECT 
                row_count,
                bytes
            FROM KEBOOLA_33.information_schema.tables
            WHERE table_catalog = 'KEBOOLA_33'
            AND table_name = UPPER(?)
            AND table_schema = UPPER(?)
        """, (table_name, schema_name))
        
        result = cursor.fetchone()
        return {
            "row_count": result[0] if result else 0,
            "size_bytes": result[1] if result else 0
        }

    def fetch_data(
        self,
        table_name: str,
        schema_name: str,
        batch_size: int = 10000,
        offset: int = 0,
        where_clause: str = None
    ) -> tuple[SnowflakeCursor, int]:
        """Fetch data in batches"""
        # Get total count first
        count_query = """
            SELECT COUNT(*) 
            FROM "KEBOOLA_33"."WORKSPACE_833213390"."data"
        """
        if where_clause:
            count_query += f" WHERE {where_clause}"
            
        cursor = self.execute(count_query)
        total_rows = cursor.fetchone()[0]

        # Fetch batch
        query = """
            SELECT *
            FROM "KEBOOLA_33"."WORKSPACE_833213390"."data"
        """
        if where_clause:
            query += f" WHERE {where_clause}"
        query += f" LIMIT {batch_size} OFFSET {offset}"
        
        cursor = self.execute(query)
        return cursor, total_rows

    def fetch_incremental_data(
        self,
        table_name: str,
        schema_name: str,
        incremental_key: str,
        last_value: str,
        batch_size: int = 10000,
        additional_where: str = None
    ) -> tuple[SnowflakeCursor, int]:
        """Fetch data incrementally"""
        where_clause = f'"{incremental_key}" > \'{last_value}\''
        if additional_where:
            where_clause = f"{where_clause} AND {additional_where}"

        return self.fetch_data(
            table_name=table_name,
            schema_name=schema_name,
            batch_size=batch_size,
            where_clause=where_clause
        )

    def list_tables(self, schema_name: str) -> List[tuple]:
        """List tables in schema"""
        cursor = self.execute(
            'SHOW TABLES IN SCHEMA "KEBOOLA_33"."' + schema_name + '"'
        )
        
        # SHOW TABLES returns: created_on, name, database_name, schema_name, kind, comment, cluster_by, rows, bytes, ...
        # We need: table_name, row_count, size_bytes, last_modified
        results = []
        for row in cursor.fetchall():
            results.append((
                row[1],  # name
                row[7],  # rows
                row[8],  # bytes
                row[0]   # created_on
            ))
        
        return results

    def close(self):
        """Close the connection"""
        self.conn.close()

    def create_stage(self, stage_name: str) -> None:
        """Create a temporary stage if it doesn't exist"""
        self.execute("""
            CREATE TEMPORARY STAGE IF NOT EXISTS ?
            FILE_FORMAT = (TYPE = 'PARQUET')
        """, (stage_name,))

    def export_to_stage(
        self,
        table_name: str,
        schema_name: str,
        stage_name: str,
        file_name: str,
        where_clause: str = None
    ) -> int:
        """Export table data to stage using COPY INTO"""
        query = """
            COPY INTO @?/?
            FROM (
                SELECT *
                FROM "KEBOOLA_33"."WORKSPACE_833213390"."data"
                {where_clause}
            )
            FILE_FORMAT = (TYPE = 'PARQUET')
            OVERWRITE = TRUE
            HEADER = TRUE
        """
        if where_clause:
            query = query.format(where_clause=f" WHERE {where_clause}")
        else:
            query = query.format(where_clause="")
            
        cursor = self.execute(query, (stage_name, file_name))
        result = cursor.fetchone()
        return result[0] if result else 0  # Return number of rows copied

    def get_staged_file(
        self,
        stage_name: str,
        file_name: str,
        local_path: str
    ) -> None:
        """Download staged file using GET command"""
        self.execute("""
            GET @?/?
            FILE = ?
        """, (stage_name, file_name, local_path))
        
    def cleanup_stage(self, stage_name: str) -> None:
        """Remove temporary stage"""
        self.execute("DROP STAGE IF EXISTS ?", (stage_name,))

    def fetch_data_via_stage(
        self,
        table_name: str,
        schema_name: str,
        local_path: str,
        where_clause: str = None
    ) -> tuple[str, int]:
        """Fetch data using stage and GET command"""
        try:
            # Create unique stage name
            stage_name = f"TEMP_STAGE_{uuid.uuid4().hex}"
            file_name = f"data_{uuid.uuid4().hex}.parquet"
            
            # Create stage
            self.create_stage(stage_name)
            
            # Export data to stage
            row_count = self.export_to_stage(
                table_name=table_name,
                schema_name=schema_name,
                stage_name=stage_name,
                file_name=file_name,
                where_clause=where_clause
            )
            
            # Download file
            self.get_staged_file(stage_name, file_name, local_path)
            
            return local_path, row_count
            
        finally:
            # Cleanup stage
            self.cleanup_stage(stage_name)