from typing import Optional
import duckdb
from app.core.config import settings

def init_duckdb_tables(conn: Optional[duckdb.DuckDBPyConnection] = None) -> None:
    """Initialize all required DuckDB tables"""
    if conn is None:
        conn = duckdb.connect(settings.DUCKDB_PATH)

    # Create allowed_tables first since it's referenced by others
    conn.execute("""
        CREATE TABLE IF NOT EXISTS allowed_tables (
            table_id UUID PRIMARY KEY,
            table_name VARCHAR NOT NULL,
            schema_name VARCHAR NOT NULL,
            source VARCHAR NOT NULL DEFAULT 'snowflake',
            status VARCHAR NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (schema_name, table_name)
        )
    """)

    # Create sync_jobs with foreign key to allowed_tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sync_jobs (
            job_id UUID PRIMARY KEY,
            table_id UUID NOT NULL,
            strategy VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            error_message VARCHAR,
            started_at TIMESTAMP DEFAULT(CURRENT_TIMESTAMP),
            completed_at TIMESTAMP,
            rows_synced INTEGER DEFAULT(0),
            stats JSON,
            FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id)
        )
    """)

    # Create table_sync_status with foreign keys to both tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS table_sync_status (
            table_id UUID,
            job_id UUID,
            last_sync_id UUID,
            last_sync_at TIMESTAMP,
            last_sync_status VARCHAR,
            last_error_message VARCHAR,
            total_rows_synced INTEGER DEFAULT(0),
            PRIMARY KEY(table_id, job_id),
            FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id),
            FOREIGN KEY (job_id) REFERENCES sync_jobs(job_id)
        )
    """)

    # Create table_metadata with foreign key to allowed_tables
    conn.execute("""
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

    # Create table_tags with foreign key to allowed_tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS table_tags (
            table_id UUID NOT NULL,
            tag VARCHAR NOT NULL,
            PRIMARY KEY (table_id, tag),
            FOREIGN KEY (table_id) REFERENCES allowed_tables(table_id)
        )
    """)

    # Create tokens table for authentication
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token_id VARCHAR PRIMARY KEY,
            token VARCHAR NOT NULL,
            type VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            revoked_at TIMESTAMP
        )
    """)

    # Create artifacts table for storing generated files
    conn.execute("""
        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id VARCHAR PRIMARY KEY,
            name VARCHAR NOT NULL,
            type VARCHAR NOT NULL,
            format VARCHAR NOT NULL,
            size_bytes INTEGER NOT NULL,
            storage_path VARCHAR NOT NULL,
            created_at TIMESTAMP NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            metadata JSON,
            swarm_token VARCHAR NOT NULL
        )
    """)

    # Create artifact_tags with foreign key to artifacts
    conn.execute("""
        CREATE TABLE IF NOT EXISTS artifact_tags (
            artifact_id VARCHAR NOT NULL,
            tag VARCHAR NOT NULL,
            PRIMARY KEY (artifact_id, tag),
            FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
        )
    """)

    # Create query_jobs table for tracking query execution
    conn.execute("""
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