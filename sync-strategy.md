# Snowflake to DuckDB Sync Process

This document outlines the step-by-step process for syncing data from Snowflake to DuckDB.

## Prerequisites

1. Environment variables must be set in `.env`:
   - Snowflake connection details (account, user, password, warehouse, database, schema)
   - DuckDB path and data directory
   - Admin credentials for API access

2. Docker containers must be running:
   ```bash
   docker compose up -d
   ```

## Step 1: Authentication

1. Obtain an access token:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/auth/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=padak&password=L0ktibr4da"
   ```

## Step 2: List Available Tables

1. List tables in your Snowflake schema:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390" \
     -H "Authorization: Bearer your_access_token"
   ```

   This will return a list of tables with their statistics:
   ```json
   [
     {
       "table_name": "data",
       "row_count": 1000,
       "size_bytes": 51200,
       "last_modified": "2024-01-15 12:00:00"
     }
   ]
   ```

## Step 3: Register a Table

1. Register a table for syncing:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/sync/tables/register" \
     -H "Authorization: Bearer your_access_token" \
     -H "Content-Type: application/json" \
     -d '{
       "table_name": "data",
       "schema_name": "WORKSPACE_833213390"
     }'
   ```

   This will:
   - Verify the table exists in Snowflake
   - Create an entry in DuckDB's `allowed_tables`
   - Return a registration response:
   ```json
   {
     "table_id": "uuid",
     "table_name": "data",
     "schema_name": "WORKSPACE_833213390",
     "status": "active"
   }
   ```

## Step 4: Start the Sync Process

1. Initiate a full table sync:
   ```bash
   curl -X POST "http://localhost:8000/api/v1/sync/start" \
     -H "Authorization: Bearer your_access_token" \
     -H "Content-Type: application/json" \
     -d '{
       "table_name": "data",
       "schema_name": "WORKSPACE_833213390",
       "strategy": "full"
     }'
   ```

   For incremental sync, add incremental key:
   ```json
   {
     "table_name": "data",
     "schema_name": "WORKSPACE_833213390",
     "strategy": "incremental",
     "incremental_key": "updated_at"
   }
   ```

## What Happens During Sync

1. **Schema Validation**:
   - Fetches schema from Snowflake using DESC TABLE:
     ```sql
     DESC TABLE "WORKSPACE_833213390"."data"
     ```
   - Parses the output to extract:
     - Column name
     - Data type (with precision/scale for numeric types)
     - Nullability
     - Character length for string types

2. **Table Creation**:
   - Creates DuckDB table with mapped schema
   - Data types are mapped as follows:
     - NUMBER -> DOUBLE
     - FLOAT -> DOUBLE
     - VARCHAR -> VARCHAR
     - CHAR -> VARCHAR
     - TEXT -> VARCHAR
     - BOOLEAN -> BOOLEAN
     - DATE -> DATE
     - TIMESTAMP_NTZ -> TIMESTAMP
     - TIMESTAMP_TZ -> TIMESTAMP
     - TIMESTAMP_LTZ -> TIMESTAMP

3. **Data Transfer**:
   - For full sync:
     1. Count total rows in Snowflake:
        ```sql
        SELECT COUNT(*) 
        FROM "WORKSPACE_833213390"."data"
        ```
     
     2. Clear existing data in DuckDB:
        ```sql
        DELETE FROM WORKSPACE_833213390.data
        ```
     
     3. Fetch data in batches (default 10,000 rows per batch):
        ```sql
        SELECT *
        FROM "WORKSPACE_833213390"."data"
        LIMIT 10000 OFFSET 0
        ```
     
     4. Convert Snowflake cursor to pandas DataFrame
     
     5. Register DataFrame in DuckDB:
        ```sql
        -- The DataFrame is registered as a temporary table 'temp_df'
        INSERT INTO WORKSPACE_833213390.data
        SELECT * FROM temp_df
        ```

   - For incremental sync:
     1. Get last synced value from previous successful sync:
        ```sql
        SELECT stats
        FROM sync_jobs
        WHERE table_id = ? 
        AND status = 'completed'
        ORDER BY completed_at DESC
        LIMIT 1
        ```
     
     2. Extract last_value from stats JSON (e.g., last timestamp or ID)
     
     3. Fetch only new/modified data:
        ```sql
        SELECT *
        FROM "WORKSPACE_833213390"."data"
        WHERE "incremental_key" > 'last_value'
        LIMIT 10000
        ```
     
     4. Convert and insert data same as full sync

   - Additional Features:
     - Optional WHERE clause filtering:
       ```sql
       -- If filter_condition is provided:
       SELECT *
       FROM "WORKSPACE_833213390"."data"
       WHERE filter_condition
       LIMIT 10000
       ```
     
     - Progress tracking:
       - Total rows to process is known from initial count
       - Batch processing allows progress monitoring
       - Stats are updated in sync_jobs table:
         ```json
         {
           "rows_processed": 10000,
           "total_rows": 50000,
           "table_stats": {
             "row_count": 50000,
             "size_bytes": 1048576
           }
         }
         ```

     - Error recovery:
       - Each batch is processed independently
       - Failed jobs can be retried
       - Sync status and progress are preserved

4. **Status Tracking**:
   - Updates sync job status in `sync_jobs` table
   - Updates table sync status in `table_sync_status`
   - Records statistics like row count and size

## Error Handling

If sync fails:
1. Job status is updated to 'failed'
2. Error message is recorded
3. Table sync status is updated
4. API returns error details

## Monitoring

1. Check sync job status:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/sync/status/{sync_id}" \
     -H "Authorization: Bearer your_access_token"
   ```

2. View table sync history:
   ```bash
   curl -X GET "http://localhost:8000/api/v1/sync/tables/status/{table_id}" \
     -H "Authorization: Bearer your_access_token"
   ```

## Cleanup

To remove a table from sync:
```bash
curl -X DELETE "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390/data" \
  -H "Authorization: Bearer your_access_token"
```

This will:
1. Mark the table as inactive in `allowed_tables`
2. Preserve sync history for auditing 