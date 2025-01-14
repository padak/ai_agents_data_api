# AI Agents Data API

A Backend API that provides controlled access to Snowflake tables (and optionally DuckDB tables) for AI agents. This API acts as a secure intermediary between AI agents and the underlying databases, providing features for data access, sampling, and artifact management.

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
  -d "username=your_admin_username&password=your_admin_password"

# Response:
{
  "access_token": "eyJhbGciOiJ...",
  "token_type": "bearer",
  "expires_in": 1800.0
}
```

### Table Management
```bash
# List registered tables
curl -X GET "http://localhost:8000/api/v1/sync/tables" \
  -H "Authorization: Bearer your_access_token"

# Register a new table
curl -X POST "http://localhost:8000/api/v1/sync/tables/register" \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "your_table",
    "schema_name": "your_schema"
  }'

# Start table synchronization
curl -X POST "http://localhost:8000/api/v1/sync/start" \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "table_name": "your_table",
    "schema_name": "your_schema",
    "strategy": "full"
  }'

# Check sync status
curl -X GET "http://localhost:8000/api/v1/sync/jobs/{job_id}" \
  -H "Authorization: Bearer your_access_token"
```

### Query Execution
```bash
# Execute a query
curl -X POST "http://localhost:8000/api/v1/queries/execute" \
  -H "Authorization: Bearer your_access_token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "SELECT * FROM your_table LIMIT 10",
    "output_format": "csv"
  }'

# Check query status
curl -X GET "http://localhost:8000/api/v1/queries/jobs/{query_id}" \
  -H "Authorization: Bearer your_access_token"
```

For more details about the API endpoints and their parameters, please refer to the [API Documentation](docs/api.md). 