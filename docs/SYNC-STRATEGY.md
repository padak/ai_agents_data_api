# Sync Strategy for Snowflake to DuckDB

## 1. Direct Snowflake Commands

Here are the raw Snowflake commands to export the "data" table:

```sql
-- Create a temporary stage
CREATE TEMPORARY STAGE IF NOT EXISTS TEMP_EXPORT_STAGE
    FILE_FORMAT = (TYPE = 'PARQUET');

-- Export data to stage using COPY INTO
COPY INTO @TEMP_EXPORT_STAGE/data.parquet
FROM (
    SELECT *
    FROM "KEBOOLA_33"."WORKSPACE_833213390"."data"
)
FILE_FORMAT = (TYPE = 'PARQUET')
OVERWRITE = TRUE
HEADER = TRUE;

-- Get the file locally (this will prompt for a local path)
GET @TEMP_EXPORT_STAGE/data.parquet;

-- Clean up the stage when done
DROP STAGE IF EXISTS TEMP_EXPORT_STAGE;
```

## 2. Python Test Script

Here's a standalone Python script to test the export process:

```python
import snowflake.connector
import uuid
import os

def get_snowflake_connection():
    """Get a Snowflake connection"""
    return snowflake.connector.connect(
        account='keboola',  # Update this
        user='PADAK',       # Update this
        password='xxx',     # Update this
        warehouse='KEBOOLA_WORKSPACE_833213390',
        database='KEBOOLA_33',
        schema='WORKSPACE_833213390'
    )

def export_table():
    """Export the data table using stage"""
    conn = get_snowflake_connection()
    cursor = conn.cursor()
    
    try:
        # Create unique stage name to avoid conflicts
        stage_name = f"TEMP_STAGE_{uuid.uuid4().hex}"
        file_name = f"data_{uuid.uuid4().hex}.parquet"
        local_path = os.path.join(os.getcwd(), file_name)
        
        print(f"Creating temporary stage {stage_name}...")
        cursor.execute(f"""
            CREATE TEMPORARY STAGE {stage_name}
            FILE_FORMAT = (TYPE = 'PARQUET')
        """)
        
        print("Exporting data to stage...")
        cursor.execute(f"""
            COPY INTO @{stage_name}/{file_name}
            FROM (
                SELECT *
                FROM "KEBOOLA_33"."WORKSPACE_833213390"."data"
            )
            FILE_FORMAT = (TYPE = 'PARQUET')
            OVERWRITE = TRUE
            HEADER = TRUE
        """)
        
        # Get row count that was exported
        result = cursor.fetchone()
        row_count = result[0] if result else 0
        print(f"Exported {row_count} rows")
        
        print(f"Downloading file to {local_path}...")
        cursor.execute(f"""
            GET @{stage_name}/{file_name}
            FILE = '{local_path}'
        """)
        
        print("Download complete!")
        return local_path, row_count
        
    finally:
        print(f"Cleaning up stage {stage_name}...")
        cursor.execute(f"DROP STAGE IF EXISTS {stage_name}")
        cursor.close()
        conn.close()

if __name__ == "__main__":
    file_path, rows = export_table()
    print(f"\nExport complete!")
    print(f"File saved to: {file_path}")
    print(f"Total rows: {rows}")
```

## 3. Using the Test Script

1. Save the script as `test_export.py`
2. Update the connection parameters in `get_snowflake_connection()`
3. Run: `python test_export.py`

The script will:
- Create a temporary stage with a unique name
- Export the data using COPY INTO
- Download the file locally
- Clean up the stage
- Print the results

## 4. Troubleshooting

Common issues to check if the export fails:
1. Connection parameters - ensure account, user, password are correct
2. Permissions - ensure your user has access to:
   - Create temporary stages
   - Select from the data table
   - Use COPY INTO command
   - Use GET command
3. Warehouse - ensure it's running and you have access
4. Local filesystem - ensure you have write permissions

## 5. Next Steps

After confirming the export works:
1. Test reading the Parquet file into DuckDB
2. Implement proper error handling
3. Add progress tracking
4. Implement incremental sync logic if needed 