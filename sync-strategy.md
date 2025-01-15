# Snowflake to DuckDB Sync Strategy

This document describes the strategy for syncing data from Snowflake to DuckDB, specifically for the "data" table.

## Overview

The sync process involves several steps:
1. Schema validation and table registration
2. Schema creation in DuckDB
3. Data transfer
4. Status tracking

## Detailed Process

### 1. Schema Validation and Table Registration

First, we verify the table exists in Snowflake and fetch its schema:

```sql
-- Snowflake: Fetch table schema
SELECT 
    column_name,
    data_type,
    character_maximum_length,
    numeric_precision,
    numeric_scale,
    is_nullable
FROM information_schema.columns
WHERE table_name = UPPER('data')
AND table_schema = UPPER('WORKSPACE_833213390')
ORDER BY ordinal_position
```

Then we register the table in DuckDB's metadata tables:

```sql
-- DuckDB: Register table in allowed_tables
INSERT INTO allowed_tables (
    table_id,
    table_name,
    schema_name,
    source,
    status
) VALUES (
    uuid(),
    'data',
    'WORKSPACE_833213390',
    'snowflake',
    'active'
)
```

### 2. Schema Creation in DuckDB

Based on the Snowflake schema, we create a corresponding table in DuckDB. The data types are mapped as follows:

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

```sql
-- DuckDB: Create target table with mapped schema
CREATE TABLE IF NOT EXISTS WORKSPACE_833213390.data (
    -- columns will be dynamically generated based on Snowflake schema
    -- example:
    -- id DOUBLE,
    -- name VARCHAR(255),
    -- created_at TIMESTAMP
)
```

### 3. Data Transfer

The data transfer process depends on the sync strategy (full or incremental):

#### Full Sync

```sql
-- Snowflake: Get total row count
SELECT COUNT(*) 
FROM "WORKSPACE_833213390"."data"

-- Snowflake: Fetch data in batches
SELECT *
FROM "WORKSPACE_833213390"."data"
LIMIT 10000 OFFSET 0  -- Batch size of 10,000 rows

-- DuckDB: Clear existing data
DELETE FROM WORKSPACE_833213390.data

-- DuckDB: Insert batch
INSERT INTO WORKSPACE_833213390.data
SELECT * FROM temp_df  -- temp_df is the pandas DataFrame registered in DuckDB
```

#### Incremental Sync

For incremental sync, we use a timestamp or sequential ID column:

```sql
-- Snowflake: Get last value from previous sync
SELECT stats
FROM sync_jobs
WHERE table_id = ? AND status = 'completed'
ORDER BY completed_at DESC
LIMIT 1

-- Snowflake: Fetch only new/modified data
SELECT *
FROM "WORKSPACE_833213390"."data"
WHERE "update_time" > 'last_sync_timestamp'
LIMIT 10000

-- DuckDB: Insert new data
INSERT INTO WORKSPACE_833213390.data
SELECT * FROM temp_df
```

### 4. Status Tracking

Throughout the process, we track sync status in two tables:

```sql
-- DuckDB: Create sync job
INSERT INTO sync_jobs (
    job_id,
    table_id,
    strategy,
    status,
    started_at
) VALUES (
    uuid(),
    table_id,
    'full',
    'running',
    CURRENT_TIMESTAMP
)

-- DuckDB: Update sync status on completion
UPDATE sync_jobs
SET 
    status = 'completed',
    completed_at = CURRENT_TIMESTAMP,
    stats = json_object('rows_processed', rows_count, 'total_rows', total_rows)
WHERE job_id = ?

-- DuckDB: Update table sync status
INSERT INTO table_sync_status (
    table_id,
    job_id,
    last_sync_status,
    last_sync_at,
    total_rows_synced
) VALUES (?, ?, 'completed', CURRENT_TIMESTAMP, ?)
ON CONFLICT (table_id, job_id) DO UPDATE SET
    last_sync_status = excluded.last_sync_status,
    last_sync_at = excluded.last_sync_at,
    total_rows_synced = excluded.total_rows_synced
```

## Error Handling

If any step fails:

1. The sync job status is updated to 'failed' with error details
2. The table sync status is updated to reflect the failure
3. The error is logged and returned to the API caller
4. Any partial data changes are kept (not rolled back) to allow for investigation

```sql
-- DuckDB: Update sync job on failure
UPDATE sync_jobs
SET 
    status = 'failed',
    completed_at = CURRENT_TIMESTAMP,
    error_message = ?
WHERE job_id = ?

-- DuckDB: Update table sync status on failure
UPDATE table_sync_status
SET 
    last_sync_status = 'failed',
    last_error_message = ?
WHERE table_id = ?
```

## Performance Considerations

1. Data is fetched in batches of 10,000 rows to manage memory usage
2. Pandas DataFrames are used for efficient bulk inserts
3. DuckDB's COPY command is used internally for fast data loading
4. Indexes and constraints are maintained after data load
5. The sync process is designed to be resumable in case of failure 