# TODO List

## In Progress
- Debugging Snowflake to DuckDB sync process
  - Created sync-strategy.md with direct Snowflake commands and test script
  - Testing export process using stages and COPY INTO command
  - Need to verify Parquet file transfer and DuckDB import
  - Need to implement and test incremental sync logic

## Completed
- Set up FastAPI project structure
- Implemented authentication with JWT
- Added Snowflake connection handling
- Added DuckDB integration
- Created basic sync endpoints
- Added table registration functionality
- Implemented Docker containerization
- Added Redis and Celery for async tasks

## Next Up
- Implement proper error handling for sync process
- Add progress tracking for large table syncs
- Add data validation between source and target
- Implement cleanup procedures for failed syncs
- Add monitoring and logging improvements
- Create admin dashboard for sync status
- Add support for multiple sync strategies
- Implement rate limiting and quotas 