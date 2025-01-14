import os
from pathlib import Path
import duckdb
from functools import lru_cache

from app.core.config import settings

# Ensure data directory exists
data_dir = Path("./data")
data_dir.mkdir(exist_ok=True)


@lru_cache()
def get_duckdb_connection() -> duckdb.DuckDBPyConnection:
    """Get a cached DuckDB connection"""
    conn = duckdb.connect(str(Path(settings.DUCKDB_PATH)))
    return conn 