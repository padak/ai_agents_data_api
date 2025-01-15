from typing import List
import uuid
from datetime import datetime

from app.core.auth import create_token
from app.db.duckdb import get_duckdb_connection
from app.db.init import init_duckdb_tables
from app.schemas.admin import (
    TokenCreate,
    TokenResponse,
    TableManagement,
    TableResponse,
    TableAction,
)


class AdminService:
    def __init__(self):
        self.db = get_duckdb_connection()
        init_duckdb_tables(self.db)

    async def create_token(self, token_data: TokenCreate) -> TokenResponse:
        """Create a new token"""
        token_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        # Create JWT token with type and ID
        token = create_token({
            "sub": token_id,
            "type": token_data.type,
        })

        # Store in database
        self.db.execute("""
            INSERT INTO tokens (token_id, token, type, created_at)
            VALUES (?, ?, ?, ?)
        """, [token_id, token, token_data.type, created_at])

        return TokenResponse(
            token_id=token_id,
            token=token,
            type=token_data.type,
            created_at=created_at.isoformat(),
        )

    async def revoke_token(self, token_id: str):
        """Revoke an existing token"""
        self.db.execute("""
            UPDATE tokens
            SET revoked_at = ?
            WHERE token_id = ? AND revoked_at IS NULL
        """, [datetime.utcnow(), token_id])

    async def manage_table(self, table_data: TableManagement) -> TableResponse:
        """Add or remove a table from the allowed list"""
        table_id = str(uuid.uuid4())
        
        if table_data.action == TableAction.ADD:
            self.db.execute("""
                INSERT INTO allowed_tables (
                    table_id, table_name, schema_name, source, status
                )
                VALUES (?, ?, ?, 'snowflake', 'active')
            """, [table_id, table_data.table_name, table_data.schema_name])
            status = "active"
        else:
            self.db.execute("""
                UPDATE allowed_tables
                SET status = 'inactive'
                WHERE table_name = ? AND schema_name = ?
            """, [table_data.table_name, table_data.schema_name])
            status = "inactive"

        return TableResponse(
            table_id=table_id,
            table_name=table_data.table_name,
            schema_name=table_data.schema_name,
            status=status,
        )

    async def list_tables(self) -> List[TableResponse]:
        """List all allowed tables"""
        result = self.db.execute("""
            SELECT table_id, table_name, schema_name, source, status
            FROM allowed_tables
            WHERE status = 'active'
        """).fetchall()

        return [
            TableResponse(
                table_id=row[0],
                table_name=row[1],
                schema_name=row[2],
                source=row[3],
                status=row[4],
            )
            for row in result
        ] 