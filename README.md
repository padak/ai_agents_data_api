# AI Agents Data API

A Backend API that provides controlled access to Snowflake tables (and optionally DuckDB tables) for AI agents. This API acts as a secure intermediary between AI agents and the underlying databases, providing features for data access, sampling, and artifact management.

## Features

- Secure authentication with Swarm and Agent tokens
- Data access through DuckDB with Snowflake synchronization
- Data sampling and profiling capabilities
- Artifact storage and sharing (up to 50MB)
- Support for CSV and Parquet export formats
- Comprehensive logging and auditing

## Requirements

- Python 3.11+
- Poetry for dependency management
- Docker (for containerization)
- Access to Snowflake database

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/padak/ai_agents_data_api.git
cd ai_agents_data_api
```

2. Install dependencies using Poetry:
```bash
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. Run the development server:
```bash
poetry run uvicorn app.main:app --reload
```

## Development

For detailed development instructions and documentation, please refer to the [Development Guide](docs/development.md).

## License

MIT License - see the [LICENSE](LICENSE) file for details 