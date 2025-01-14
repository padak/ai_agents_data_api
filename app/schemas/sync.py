from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class SyncStrategy(str, Enum):
    FULL = "full"  # Full table sync
    INCREMENTAL = "incremental"  # Sync only new/modified rows
    SNAPSHOT = "snapshot"  # Create a point-in-time snapshot


class SyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncRequest(BaseModel):
    table_name: str
    schema_name: str = Field(default="public")
    strategy: SyncStrategy = SyncStrategy.FULL
    incremental_key: Optional[str] = Field(
        default=None,
        description="Column name to use for incremental sync"
    )
    filter_condition: Optional[str] = Field(
        default=None,
        description="Optional WHERE clause for filtering data"
    )


class SyncResponse(BaseModel):
    sync_id: str
    table_name: str
    schema_name: str
    strategy: SyncStrategy
    status: SyncStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    stats: Dict[str, Any] = Field(
        default_factory=dict,
        description="Sync statistics (rows processed, etc.)"
    )


class SyncConfig(BaseModel):
    batch_size: int = Field(
        default=10000,
        description="Number of rows to process in each batch"
    )
    max_retries: int = Field(
        default=3,
        description="Maximum number of retry attempts for failed operations"
    )
    timeout_seconds: int = Field(
        default=3600,
        description="Maximum time in seconds for sync operation"
    )


class TableSyncStatus(BaseModel):
    table_id: str
    table_name: str
    schema_name: str
    last_sync_id: Optional[str] = None
    last_sync_status: Optional[SyncStatus] = None
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    row_count: int = 0
    size_bytes: int = 0 