# Backend API for AI Agent Data Access

## Refined Description of the Application

You want to build a **Backend API** that provides controlled access to **Snowflake** tables (and optionally DuckDB tables) for AI agents. These AI agents must not directly access the underlying databases. Instead, they will make authenticated requests to the API, which can run queries, return samples, and store or retrieve artefacts (data up to 50 MB).

- **Two approaches** to data access:
  1. **Direct queries** to Snowflake.
  2. **DuckDB replication**: Data can be partially or fully replicated from Snowflake to DuckDB to reduce costs and test DuckDB capabilities.

- **Authentication** requires two tokens:
  1. **Swarm Token** (shared by all agents).
  2. **Agent Token** (unique per agent).
  Both must be sent in the request header.

- **Data Profiling**: The system should allow running a profiling tool (e.g., pandas-profiling) on a sample of data and store the results for reuse.

- **Data Sampling**: Agents can request the first N rows or a random percentage sample (e.g., 0.5‰ if the table is large).

- **Analytical Queries**: Agents can submit queries (SQL or future DSL) which are run asynchronously, and the results can be retrieved by job ID or stored as an artefact.

- **Stored Artefacts** (up to 50 MB) can be shared among agents who have the same swarm token. Artefacts expire after 10 days by default, but each access extends the expiration for another 10 days.

- **Tagging & Metadata**: Agents can label and group data sources, so other agents can find relevant data by tags or descriptions.

- **Logging & Auditing**: All queries must be logged (including the full query text) to a local file.  

- **Deployment**: The system will be containerized (Docker) and deployed to a Google Cloud VM for development. Let’s Encrypt (Certbot) will provide HTTPS certificates. A CI/CD pipeline will run tests and automatically deploy updates. Eventually, the system might move to Kubernetes.

---

## Developer Documentation

### 1. Technology Stack

- **Python 3.9+** (3.11 recommended)
- **FastAPI** (for async, auto-docs, and ease of development)
- **DuckDB** (local file-based DB)
- **Snowflake** (cloud data warehouse)
- **Let’s Encrypt** (for HTTPS certificates on GCP VM)
- **CI/CD Pipeline** (e.g., GitHub Actions or GitLab CI) for testing & deployment

### 2. Architecture Diagram (High-Level)

```
          AI Agents
             |
       [HTTPS with tokens]
             |
       -----------------
       |  FastAPI App  |
       -----------------
       |   Token Mgmt  |
       |   Logging     |
       |   Endpoints   |
       |   (async)     |
       -----------------
      /        |       \
Snowflake     DuckDB   Local File Storage (for logs, etc.)
            (cached/replicated data,
             artefacts, metadata,
             config, etc.)
```

### 3. Endpoints

All requests must include:
```
Authorization: Bearer <SwarmToken>;<AgentToken>
```

#### 3.1 Management Endpoints

1. **`POST /manage/tables`**  
   - **Purpose**: Add or remove tables from the “allowed” list.  
   - **Request Body**:
     ```json
     {
       "action": "add" | "remove",
       "table_name": "string",
       "schema_name": "string"
     }
     ```
   - **Response**: Status message (success/fail).

2. **`POST /manage/tokens`**  
   - **Purpose**: Generate or revoke tokens (swarm or agent).  
   - **Request Body** (example):
     ```json
     {
       "action": "generate_swarm" | "generate_agent" | "revoke_swarm" | "revoke_agent",
       "token_id": "xyz" // used if revoking
     }
     ```
   - **Response**: For generation, returns the new token. For revocation, status message.

3. **`POST /manage/duckdb`**  
   - **Purpose**: Manage DuckDB replication.  
   - **Request Body**:
     ```json
     {
       "action": "replicate" | "delete" | "refresh",
       "table_name": "string",
       "schema_name": "string",
       "duckdb_file": "path_to_file",
       "sql_query": "SELECT * FROM my_table WHERE ..."
     }
     ```
   - **Response**: Status message.

#### 3.2 Data Access Endpoints

1. **`GET /list_data`**  
   - **Purpose**: Return all available data sources (tables, tags, metadata, etc.).  
   - **Response** (example):
     ```json
     [
       {
         "table_id": "sales_2023",
         "schema_id": "public",
         "source": "snowflake" | "duckdb",
         "tags": ["sales", "2023", "monthly"]
       },
       ...
     ]
     ```

2. **`POST /profile_data`**  
   - **Purpose**: Generate or retrieve a data profile (stats, distributions, missing values, etc.).  
   - **Request Body**:
     ```json
     {
       "table_name": "string",
       "schema_name": "string",
       "force_refresh": false
     }
     ```
   - **Response**: Profile data (JSON). If `force_refresh` is `true`, re-run profiling.

3. **`POST /sample_data`**  
   - **Purpose**: Return a sample from a table (first N rows or random sample).  
   - **Request Body**:
     ```json
     {
       "table_name": "string",
       "schema_name": "string",
       "sample_type": "first" | "random",
       "sample_size": 1000 | 0.005, // e.g., 0.005 = 0.5% sample
       "output_format": "JSON" | "CSV" | "Parquet" | "Arrow" | "Iceberg"
     }
     ```
   - **Response**: Sample data in specified format.

4. **`POST /query`** (Async)  
   - **Purpose**: Submit a SQL query for asynchronous execution.  
   - **Request Body**:
     ```json
     {
       "query": "SELECT COUNT(*) FROM my_table WHERE x > 100",
       "params": { "...": "..." },
       "output_format": "JSON" | "CSV" | "Parquet" | "Arrow" | "Iceberg"
     }
     ```
   - **Response**: A `{ job_id: "XYZ" }` to poll later.

5. **`GET /query_result/{job_id}`**  
   - **Purpose**: Poll for the async query result.  
   - **Response**:  
     - If complete: returns data or a reference to an artefact.  
     - If still processing: returns status.

#### 3.3 Artefact Endpoints

1. **`POST /artefact`**  
   - **Purpose**: Store intermediate data (up to 50 MB).  
   - **Request Body** (base64-encoded if binary):
     ```json
     {
       "artefact_content": "base64encoded...",
       "metadata": {
         "tags": ["aggregation", "model_output"]
       }
     }
     ```
   - **Response**: `{ "artefact_id": "XYZ" }`.

2. **`GET /artefact/{artefact_id}`**  
   - **Purpose**: Retrieve the artefact. Automatically extends expiration by 10 days.  
   - **Response**: The artefact (raw data or base64, depending on your design).

3. **`POST /artefact/extend/{artefact_id}`**  
   - **Purpose**: Manually extend artefact expiration.

4. **`DELETE /artefact/{artefact_id}`**  
   - **Purpose**: Delete an artefact early.

---

### 4. Security & Authentication

1. **Token Structure**  
   - **Swarm Token**: Shared by all agents in a swarm (e.g., `SWARM-abc123`).
   - **Agent Token**: Unique to each agent (e.g., `AGENT-def456`).

2. **Revocation & Management**  
   - Use `/manage/tokens` endpoint to create, revoke, or renew tokens.

3. **HTTPS**  
   - Use Certbot for Let’s Encrypt on Google Cloud VM.
   - Auto-renew certificates.

---

### 5. Logging & Auditing

- **Content**: Log the full query text, swarm/agent IDs, timestamps, etc.  
- **Destination**: Local file (e.g., `/var/log/agent_api.log`).  
- **Rotation**: Use logrotate or a similar tool to handle file size or time-based rotation.

---

### 6. Development & Testing

1. **Dev vs. Production**  
   - Separate environment variables, e.g. `.env.dev` vs. `.env.prod`.
   - Potentially separate DuckDB files for dev/production.

2. **Tests**  
   - **Unit Tests** with mocks for Snowflake and DuckDB.  
   - **Integration Tests**: Possibly spin up DuckDB locally for ephemeral testing.  
   - **CI/CD**: Automate tests, linting, coverage, and Docker image builds.

---

### 7. Deployment Details

1. **Docker**  
   - Example `Dockerfile`:
     ```dockerfile
     FROM python:3.11
     WORKDIR /app
     COPY requirements.txt /app
     RUN pip install -r requirements.txt
     COPY . /app
     CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "443"]
     ```
2. **CI/CD**  
   - Use GitHub Actions/GitLab CI to:
     1. Run tests
     2. Build Docker image
     3. Deploy to GCP VM (Dev) or to Kubernetes later

3. **Let’s Encrypt + Certbot**  
   - Install Certbot and expose port 80 for HTTP challenge or use DNS challenge.
   - Auto-renew certificates in cron or systemd timer.

---

### 8. DuckDB Maintenance

1. **File Management**  
   - Use one file per replicated table (e.g., `table_<schema>_<table_name>.duckdb`).  
   - Possibly a single “master” DuckDB for metadata/config if needed.

2. **Automated Cleanup**  
   - Periodically check for unused DuckDB files or orphaned artefacts.
   - Run VACUUM if needed.

3. **Endpoints**  
   - `/manage/duckdb` for replicate/delete/refresh.

---

### 9. Example Pseudocode

```python
# sample_data endpoint example (async or sync, simplified)

from fastapi import APIRouter, Header, HTTPException

router = APIRouter()

@router.post("/sample_data")
async def sample_data(
    table_name: str,
    schema_name: str,
    sample_type: str,
    sample_size: float,
    output_format: str = "JSON",
    authorization: str = Header(...),
):
    # 1) Parse tokens
    swarm_token, agent_token = parse_authorization_header(authorization)
    if not tokens_are_valid(swarm_token, agent_token):
        raise HTTPException(status_code=401, detail="Invalid tokens")

    # 2) Check allowed table
    if not is_table_allowed(schema_name, table_name):
        raise HTTPException(status_code=403, detail="Table not allowed")

    # 3) Build sample query (prefer DuckDB if cached)
    source = "duckdb" if duckdb_has_table(schema_name, table_name) else "snowflake"
    if sample_type == "first":
        sql = f"SELECT * FROM {schema_name}.{table_name} LIMIT {int(sample_size)}"
    else:
        # random sample
        # For DuckDB, e.g.: "SELECT * FROM ... USING SAMPLE ..."
        percentage = sample_size * 100
        sql = f"SELECT * FROM {schema_name}.{table_name} USING SAMPLE {percentage} PERC"

    # 4) Run query (async possible)
    results = await run_async_sql(sql, source=source)

    # 5) Format results
    formatted_data = convert_results(results, output_format)

    # 6) Log the query
    log_query(agent_token, swarm_token, sql)

    # 7) Return response
    return {
        "data": formatted_data
    }
```

---

### 10. Roadmap & Next Steps

1. **MVP**  
   - Token-based auth, basic endpoints for table mgmt, queries, sampling, profiling, artefacts.
   - Local logging of queries.

2. **Future Enhancements**  
   - Column-level restrictions.  
   - Full-blown asynchronous queue system (Celery/RQ).  
   - Auto-refreshing data profiles.  
   - Data masking/obfuscation for sensitive columns.

3. **Testing & CI/CD**  
   - Expand coverage with unit and integration tests.
   - Automated deployments to dev environment on GCP.

4. **Production Hardening**  
   - Move logs to a centralized system (e.g., GCP Logging).  
   - Introduce an SLA and performance scaling (Kubernetes).  
   - Additional security (e.g., secrets in GCP Secret Manager).

---

## Conclusion

This single **Markdown** document outlines the end-to-end **Backend API** design for AI agent data access. It covers:

1. **Architecture** and **Technology Stack**  
2. **Endpoints** (Management, Data Access, Artefacts)  
3. **Authentication** and **Logging**  
4. **DuckDB** replication details  
5. **Deployment** considerations (Docker, GCP, Let’s Encrypt)  
6. **Testing** and **Roadmap**  

With these guidelines, a **junior developer** (or AI agent) can confidently implement the system step by step, ensuring secure, auditable, and efficient data access for your AI swarm.

