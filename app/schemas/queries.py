from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class OutputFormat(str, Enum):
    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"


class QueryConfig(BaseModel):
    """Configuration for query execution"""
    output_format: OutputFormat = Field(default=OutputFormat.CSV, description="Format of the query output")
    max_rows: Optional[int] = Field(default=None, description="Maximum number of rows to return")
    timeout_seconds: Optional[int] = Field(default=None, description="Query timeout in seconds")


class QueryRequest(BaseModel):
    """Request model for executing a query"""
    query: str = Field(..., description="SQL query to execute")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Query parameters")
    config: Optional[QueryConfig] = Field(default=None, description="Query configuration")


class QueryResponse(BaseModel):
    """Response model for query execution"""
    job_id: str = Field(..., description="Unique identifier for the query job")
    status: str = Field(..., description="Status of the query job")
    result_file: Optional[str] = Field(default=None, description="Path to the result file")
    error: Optional[str] = Field(default=None, description="Error message if query failed")
    stats: Optional[Dict[str, Any]] = Field(default=None, description="Query execution statistics") 