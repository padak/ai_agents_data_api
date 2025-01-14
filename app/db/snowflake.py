from functools import lru_cache
import snowflake.connector
from snowflake.connector.connection import SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor

from app.core.config import settings


@lru_cache()
def get_snowflake_connection() -> SnowflakeConnection:
    """Get a cached Snowflake connection"""
    conn = snowflake.connector.connect(
        account=settings.SNOWFLAKE_ACCOUNT,
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

    def execute(self, query: str, params: tuple = None) -> SnowflakeCursor:
        """Execute a query and return the cursor"""
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor

    def fetch_schema(self, table_name: str, schema_name: str) -> list:
        """Fetch table schema information"""
        cursor = self.execute(f"""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                numeric_precision,
                numeric_scale,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            AND table_schema = %s
            ORDER BY ordinal_position
        """, (table_name.upper(), schema_name.upper()))
        
        return cursor.fetchall()

    def fetch_table_stats(self, table_name: str, schema_name: str) -> dict:
        """Fetch table statistics"""
        cursor = self.execute(f"""
            SELECT 
                row_count,
                bytes
            FROM information_schema.tables
            WHERE table_name = %s
            AND table_schema = %s
        """, (table_name.upper(), schema_name.upper()))
        
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
        count_query = f"""
            SELECT COUNT(*) 
            FROM {schema_name}.{table_name}
            {f'WHERE {where_clause}' if where_clause else ''}
        """
        cursor = self.execute(count_query)
        total_rows = cursor.fetchone()[0]

        # Fetch batch
        query = f"""
            SELECT *
            FROM {schema_name}.{table_name}
            {f'WHERE {where_clause}' if where_clause else ''}
            LIMIT {batch_size} OFFSET {offset}
        """
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
        where_clause = f"{incremental_key} > '{last_value}'"
        if additional_where:
            where_clause = f"{where_clause} AND {additional_where}"

        return self.fetch_data(
            table_name=table_name,
            schema_name=schema_name,
            batch_size=batch_size,
            where_clause=where_clause
        )

    def close(self):
        """Close the connection"""
        self.conn.close()