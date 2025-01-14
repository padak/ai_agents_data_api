from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field, conint, confloat


class SampleType(str, Enum):
    FIRST = "first"
    RANDOM = "random"


class OutputFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"


class DataSampleRequest(BaseModel):
    table_name: str
    schema_name: str = Field(default="public")
    sample_type: SampleType
    sample_size: Any = Field(  # Can be int for FIRST or float for RANDOM
        description="Number of rows for FIRST type, percentage (0-1) for RANDOM type"
    )
    output_format: OutputFormat = OutputFormat.JSON


class QueryRequest(BaseModel):
    query: str
    params: Optional[Dict[str, Any]] = None
    output_format: OutputFormat = OutputFormat.JSON


class QueryResponse(BaseModel):
    job_id: str
    status: str = "pending"
    result_url: Optional[str] = None


class QueryStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class QueryStatusResponse(BaseModel):
    job_id: str
    status: QueryStatus
    result_url: Optional[str] = None
    error: Optional[str] = None


class TableMetadata(BaseModel):
    table_id: str
    table_name: str
    schema_name: str
    source: str
    column_count: int
    row_count: int
    size_bytes: int
    last_updated: str
    tags: List[str] = []
    description: Optional[str] = None


class ProfileRequest(BaseModel):
    table_name: str
    schema_name: str = Field(default="public")
    force_refresh: bool = False
    sample_size: Optional[confloat(gt=0, le=1)] = Field(
        default=1.0,
        description="Percentage of data to profile (0-1)"
    ) 