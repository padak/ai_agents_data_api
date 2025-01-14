from enum import Enum
from pydantic import BaseModel, Field


class TokenType(str, Enum):
    SWARM = "swarm"
    AGENT = "agent"


class TokenAction(str, Enum):
    GENERATE = "generate"
    REVOKE = "revoke"


class TableAction(str, Enum):
    ADD = "add"
    REMOVE = "remove"


class TokenCreate(BaseModel):
    type: TokenType
    action: TokenAction = TokenAction.GENERATE


class TokenResponse(BaseModel):
    token_id: str
    token: str
    type: TokenType
    created_at: str


class TableManagement(BaseModel):
    action: TableAction
    table_name: str
    schema_name: str = Field(default="public")


class TableResponse(BaseModel):
    table_id: str
    table_name: str
    schema_name: str
    source: str = "snowflake"
    status: str