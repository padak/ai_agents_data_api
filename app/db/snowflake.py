from functools import lru_cache
import snowflake.connector
from snowflake.connector.connection import SnowflakeConnection
from snowflake.connector.cursor import SnowflakeCursor

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

    def execute(self, query: str, params: tuple = None) -> SnowflakeCursor:
        """Execute a query and return the cursor"""
        self._ensure_connection()
        cursor = self.conn.cursor()
        if params is not None:
            if not isinstance(params, tuple):
                params = (params,)
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        return cursor

    def fetch_schema(self, table_name: str, schema_name: str) -> list:
        """Fetch table schema information"""
        cursor = self.execute(f'DESC TABLE "{schema_name}"."{table_name}"')
        
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
        count_query = f"""
            SELECT COUNT(*) 
            FROM "{schema_name}"."{table_name}"
            {f'WHERE {where_clause}' if where_clause else ''}
        """
        cursor = self.execute(count_query)
        total_rows = cursor.fetchone()[0]

        # Fetch batch
        query = f"""
            SELECT *
            FROM "{schema_name}"."{table_name}"
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
        where_clause = f'"{incremental_key}" > \'{last_value}\''
        if additional_where:
            where_clause = f"{where_clause} AND {additional_where}"

        return self.fetch_data(
            table_name=table_name,
            schema_name=schema_name,
            batch_size=batch_size,
            where_clause=where_clause
        )

    def list_tables(self, schema_name: str) -> list:
        """List all tables in the specified schema"""
        cursor = self.execute("""
            SELECT 
                table_name,
                row_count,
                bytes as size_bytes,
                last_altered as last_modified
            FROM KEBOOLA_33.information_schema.tables
            WHERE table_catalog = 'KEBOOLA_33'
            AND table_schema = ?
            ORDER BY table_name
        """, (schema_name,))
        
        return cursor.fetchall()

    def close(self):
        """Close the connection"""
        self.conn.close()