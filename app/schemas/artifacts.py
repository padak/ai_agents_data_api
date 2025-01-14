from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, conint


class ArtifactType(str, Enum):
    DATA = "data"
    MODEL = "model"
    REPORT = "report"
    OTHER = "other"


class ArtifactFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    PICKLE = "pickle"
    TEXT = "text"
    BINARY = "binary"


class ArtifactCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    type: ArtifactType
    format: ArtifactFormat
    content: str = Field(..., description="Base64 encoded content")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    expiry_days: Optional[conint(gt=0)] = Field(
        default=None,
        description="Days until expiration. If not set, uses default from settings"
    )


class ArtifactResponse(BaseModel):
    artifact_id: str
    name: str
    type: ArtifactType
    format: ArtifactFormat
    size_bytes: int
    created_at: datetime
    expires_at: datetime
    metadata: Dict[str, Any]
    tags: List[str]


class ArtifactUpdate(BaseModel):
    name: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    expiry_days: Optional[conint(gt=0)] = None


class ArtifactFilter(BaseModel):
    type: Optional[ArtifactType] = None
    format: Optional[ArtifactFormat] = None
    tags: Optional[List[str]] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None