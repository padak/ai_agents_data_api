# Snowflake to DuckDB Sync Steps

This document outlines the specific steps our application takes when performing a full sync of the "data" table from Snowflake to DuckDB.

## Prerequisites
1. Docker containers running (API, Celery workers, Redis)
2. Admin authentication token
3. Table registered in the system

## Step-by-Step Process with Implementation Details

### 1. Authentication
```bash
# Get admin token
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=padak&password=L0ktibr4da"
```
Expected response: JWT token

**Implementation Details:**
1. Request hits `app/api/v1/endpoints/auth.py`
2. Credentials are validated against environment variables (ADMIN_USERNAME, ADMIN_PASSWORD)
3. On successful validation:
   - Creates a JWT token using `jose.jwt.encode()`
   - Token payload includes: {"sub": username}
   - Signs with JWT_SECRET_KEY from environment
   - Sets expiration time (30 minutes by default)
4. Token is stored in DuckDB tokens table with:
   - token_id (UUID)
   - token (JWT string)
   - type ("admin")
   - created_at timestamp

### 2. List Available Tables
```bash
# List tables in Snowflake schema
curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390" \
  -H "Authorization: Bearer YOUR_TOKEN"
```
Expected response: List of tables with metadata (size, row count)

**Implementation Details:**
1. Request hits `app/api/v1/endpoints/sync.py:list_tables()`
2. Token validation in middleware:
   - Extracts token from Authorization header
   - Verifies JWT signature and expiration
   - Checks token exists and is not revoked in DuckDB
3. Creates Snowflake connection using environment credentials:
   ```python
   snowflake.connector.connect(
       account=settings.SNOWFLAKE_ACCOUNT,
       user=settings.SNOWFLAKE_USER,
       password=settings.SNOWFLAKE_PASSWORD,
       warehouse=settings.SNOWFLAKE_WAREHOUSE,
       database=settings.SNOWFLAKE_DATABASE,
       schema=settings.SNOWFLAKE_SCHEMA
   )
   ```
4. Executes Snowflake query:
   ```sql
   SHOW TABLES IN SCHEMA "KEBOOLA_33"."WORKSPACE_833213390"
   ```
5. Processes results to extract:
   - Table name
   - Row count
   - Size in bytes
   - Last modified timestamp

### 3. Register Table for Sync
```bash
# Register the data table
curl -X POST "http://localhost:8000/api/v1/sync/tables/register" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "data",
    "schema_name": "WORKSPACE_833213390"
  }'
```
Expected response: Table registration confirmation with table_id

**Implementation Details:**
1. Request hits `app/services/sync.py:register_table()`
2. Verifies table exists in Snowflake:
   ```python
   # Fetch schema to verify table exists
   snowflake_client.fetch_schema(table_name, schema_name)
   ```
3. Generates UUID for table_id
4. Inserts record into DuckDB allowed_tables:
   ```sql
   INSERT INTO allowed_tables (
       table_id, table_name, schema_name, 
       source, status, created_at
   ) VALUES (?, ?, ?, 'snowflake', 'active', CURRENT_TIMESTAMP)
   ```
5. Creates initial metadata record:
   ```sql
   INSERT INTO table_metadata (
       table_id, table_name, schema_name,
       source, column_count, row_count,
       size_bytes, last_updated
   ) VALUES (...)
   ```

### 4. Start Full Sync
```bash
# Start the sync process
curl -X POST "http://localhost:8000/api/v1/sync/start" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "data",
    "schema_name": "WORKSPACE_833213390",
    "strategy": "full"
  }'
```
Expected response: Sync job ID

**Implementation Details:**
1. Request hits `app/services/sync.py:start_sync()`
2. Creates sync job record:
   ```sql
   INSERT INTO sync_jobs (
       job_id, table_id, strategy, status,
       started_at
   ) VALUES (?, ?, 'full', 'pending', CURRENT_TIMESTAMP)
   ```
3. Triggers Celery task `app/tasks/sync.py:sync_table.delay()`
4. Celery worker processes the task:
   
   a. **Preparation Phase**
   - Creates unique stage name using UUID
   - Verifies DuckDB data directory exists
   - Updates job status to 'running'
   
   b. **Schema Sync**
   - Fetches Snowflake schema:
     ```sql
     DESC TABLE "KEBOOLA_33"."WORKSPACE_833213390"."data"
     ```
   - Maps Snowflake types to DuckDB types:
     - NUMBER -> DOUBLE
     - VARCHAR -> VARCHAR
     - TIMESTAMP_NTZ -> TIMESTAMP
     etc.
   - Creates/updates DuckDB table schema:
     ```sql
     CREATE TABLE IF NOT EXISTS schema_name.table_name (
         column_definitions
     )
     ```
   
   c. **Data Export from Snowflake**
   - Creates temporary stage:
     ```sql
     CREATE TEMPORARY STAGE temp_stage_uuid
     FILE_FORMAT = (TYPE = 'PARQUET')
     ```
   - Exports data to stage:
     ```sql
     COPY INTO @temp_stage_uuid/data.parquet
     FROM (SELECT * FROM schema_name.table_name)
     FILE_FORMAT = (TYPE = 'PARQUET')
     OVERWRITE = TRUE
     ```
   - Downloads Parquet file using GET command
   
   d. **Data Import to DuckDB**
   - For full sync, truncates existing data:
     ```sql
     DELETE FROM schema_name.table_name
     ```
   - Imports Parquet file:
     ```sql
     COPY schema_name.table_name FROM 'path/to/data.parquet'
     ```
   - Verifies row count matches source
   
   e. **Cleanup Phase**
   - Removes temporary stage from Snowflake
   - Deletes local Parquet file
   - Updates sync job status to 'completed'
   - Updates table metadata with new stats

### 5. Monitor Sync Progress
```bash
# Check sync status
curl -X GET "http://localhost:8000/api/v1/sync/jobs/{sync_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```
Expected response: Sync status (pending/running/completed/failed)

**Implementation Details:**
1. Request hits `app/services/sync.py:get_sync_status()`
2. Queries sync_jobs table:
   ```sql
   SELECT 
       j.job_id,
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
   WHERE j.job_id = ?
   ```
3. If job completed:
   - Returns full stats including rows processed
   - Includes any error messages if failed
4. If job running:
   - Queries Celery for task status
   - Returns progress information if available

## Verification Steps

After sync completes:

1. **Check Table Status**
```bash
# Get table sync status
curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390/data/status" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Implementation Details:**
1. Request hits `app/services/sync.py:get_table_sync_status()`
2. Queries multiple tables for comprehensive status:
   ```sql
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
   ```
3. Verifies DuckDB table exists and is accessible
4. Returns combined status information

2. **Verify Data Sample**
```bash
# Get sample from synced table
curl -X POST "http://localhost:8000/api/v1/sample_data" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "data",
    "schema_name": "WORKSPACE_833213390",
    "sample_type": "first",
    "sample_size": 10,
    "output_format": "JSON"
  }'
```

**Implementation Details:**
1. Request hits `app/services/data.py:get_data_sample()`
2. Verifies table is allowed and synced
3. Builds sample query based on type:
   ```sql
   -- For first N rows
   SELECT * FROM schema_name.table_name LIMIT ?
   
   -- For random sample
   SELECT * FROM schema_name.table_name USING SAMPLE ?
   ```
4. Executes query on DuckDB
5. Formats results based on requested output format:
   - JSON: Uses pandas to_dict()
   - CSV: Uses pandas to_csv()
   - Parquet: Uses pandas to_parquet()

## Error Handling and Recovery

The application implements several error handling mechanisms:

1. **Connection Errors**
   - Retries with exponential backoff
   - Maximum 3 retry attempts
   - Logs detailed connection errors

2. **Data Validation**
   - Verifies row counts match after sync
   - Checks data types are correctly mapped
   - Validates sample data is readable

3. **Resource Management**
   - Monitors disk space during file operations
   - Cleans up temporary files even on failure
   - Closes database connections properly

4. **State Recovery**
   - Failed jobs can be retried
   - Partial syncs can be resumed
   - Corrupted target tables can be rebuilt

## Monitoring and Logging

The application provides multiple monitoring points:

1. **API Logs**
   - Request/response details
   - Authentication attempts
   - Error messages

2. **Celery Worker Logs**
   - Task progress
   - Sync operations
   - Resource usage

3. **Flower Dashboard**
   - Task queue status
   - Worker health
   - Task history

4. **Database Logs**
   - Sync job history
   - Table status changes
   - Error records

All logs include:
- Timestamp
- Operation ID
- User/token information
- Detailed error messages
- Performance metrics 