# AI Agents Data API

A Backend API that provides controlled access to Snowflake tables (and optionally DuckDB tables) for AI agents. This API acts as a secure intermediary between AI agents and the underlying databases, providing features for data access, sampling, and artifact management.

## Documentation

Detailed documentation can be found in the `DOCS` folder:
- [Instructions](DOCS/INSTRUCTIONS.md) - Comprehensive guide for the API implementation
- [Sync Strategy](DOCS/SYNC-STRATEGY.md) - Technical details of Snowflake to DuckDB replication
- [Plan](DOCS/PLAN.md) - Development roadmap and milestones
- [Todo](DOCS/TODO.md) - Current development tasks and progress

## Features

- Secure authentication with Swarm and Agent tokens
- Data access through DuckDB with Snowflake synchronization
- Data sampling and profiling capabilities
- Artifact storage and sharing (up to 50MB)
- Support for CSV and Parquet export formats
- Comprehensive logging and auditing
- Asynchronous task processing with Celery
- Task monitoring with Flower dashboard

## Requirements

- Python 3.11+
- Poetry for dependency management
- Docker and Docker Compose
- Access to Snowflake database

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/padak/ai_agents_data_api.git
cd ai_agents_data_api
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run with Docker Compose:
```bash
docker compose up --build
```

This will start all services:
- FastAPI application (http://localhost:8000)
- Celery workers for async tasks
- Celery Beat for scheduled tasks
- Flower dashboard (http://localhost:5555)
- Redis for message broker

Alternatively, for development without Docker:

1. Install dependencies:
```bash
poetry install
```

2. Run the development server:
```bash
poetry run uvicorn app.main:app --reload
```

## Testing the API

1. Access the API documentation:
   - Open http://localhost:8000/docs in your browser
   - You'll see all available endpoints with interactive documentation

2. Test Query Endpoints:
   ```bash
   # Example: Execute a query
   curl -X POST "http://localhost:8000/api/v1/queries/" \
     -H "Content-Type: application/json" \
     -d '{"query": "SELECT * FROM my_table LIMIT 10", "output_format": "CSV"}'
   
   # Check query status
   curl "http://localhost:8000/api/v1/queries/{job_id}"
   ```

3. Test Sync Operations:
   ```bash
   # Start table sync
   curl -X POST "http://localhost:8000/api/v1/sync/start" \
     -H "Content-Type: application/json" \
     -d '{"table_name": "my_table", "schema_name": "my_schema", "strategy": "FULL"}'
   
   # Check sync status
   curl "http://localhost:8000/api/v1/sync/jobs/{sync_id}"
   ```

## Monitoring Tasks

1. Access Flower Dashboard:
   - Open http://localhost:5555 in your browser
   - Monitor active workers, task history, and success rates
   - View detailed task information and results

2. Scheduled Tasks:
   - Query result cleanup: Runs daily to remove old query results
   - Table sync status updates: Runs hourly to update sync statistics
   - Configure schedules in `app/tasks/celery_app.py`

## Development

For detailed development instructions and documentation, please refer to the [Development Guide](docs/development.md).

## License

MIT License - see the [LICENSE](LICENSE) file for details 

## API Usage Examples

### Authentication

```bash
# Get admin token
curl -X POST "http://localhost:8000/api/v1/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin_test_password"
```

### Sync Operations

1. List Tables in Schema:
```bash
curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390" \
  -H "Authorization: Bearer your_access_token"
```

2. Register a Table:
```bash
curl -X POST "http://localhost:8000/api/v1/sync/tables/register" \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "data",
    "schema_name": "WORKSPACE_833213390"
  }'
```

3. Remove a Table:
```bash
curl -X DELETE "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390/data" \
  -H "Authorization: Bearer your_access_token"
```

4. Start Table Sync:
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

5. Check Sync Job Status:
```bash
curl -X GET "http://localhost:8000/api/v1/sync/jobs/your_sync_id" \
  -H "Authorization: Bearer your_access_token"
```

6. Check Table Sync Status:
```bash
curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390/data/status" \
  -H "Authorization: Bearer your_access_token"
```

For more details about the API endpoints and their parameters, please refer to the [API Documentation](docs/api.md). 