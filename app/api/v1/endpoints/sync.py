from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel

from app.api.deps import get_current_admin_user
from app.schemas.sync import (
    SyncRequest,
    SyncResponse,
    SyncConfig,
    TableSyncStatus,
    TableRegistration,
    TableRegistrationResponse,
)
from app.services.sync import SyncService
from app.tasks.sync import sync_table
from app.db.snowflake import SnowflakeClient

router = APIRouter()
sync_service = SyncService()


class TableInfo(BaseModel):
    table_name: str
    row_count: int
    size_bytes: int
    last_modified: str


class SyncStartRequest(BaseModel):
    """Request model for starting a sync"""
    sync_request: SyncRequest
    config: Optional[SyncConfig] = None


@router.get(
    "/tables/{schema_name}",
    response_model=List[TableInfo],
    tags=["sync"],
    summary="List tables in schema",
    description="""
    List all tables in the specified schema.
    
    **Curl example:**
    ```shell
    curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390" \\
      -H "Authorization: Bearer your_access_token"
    ```
    """
)
async def list_tables(
    schema_name: str,
    _=Depends(get_current_admin_user)
):
    """List all tables in the specified schema."""
    client = SnowflakeClient()
    try:
        tables = client.list_tables(schema_name)
        return [
            TableInfo(
                table_name=table[0],
                row_count=table[1] or 0,
                size_bytes=table[2] or 0,
                last_modified=str(table[3]) if table[3] else None
            )
            for table in tables
        ]
    finally:
        client.close()


@router.post(
    "/tables/register",
    response_model=TableRegistrationResponse,
    tags=["sync"],
    summary="Register a table for syncing",
    description="""
    Register a table for syncing (admin only).
    
    **Curl example:**
    ```shell
    curl -X POST "http://localhost:8000/api/v1/sync/tables/register" \\
      -H "Authorization: Bearer your_access_token" \\
      -H "Content-Type: application/json" \\
      -d '{
        "table_name": "data",
        "schema_name": "WORKSPACE_833213390"
      }'
    ```
    """
)
async def register_table(
    request: TableRegistration,
    _: str = Depends(get_current_admin_user)
) -> TableRegistrationResponse:
    """Register a table for syncing."""
    result = await sync_service.register_table(request.table_name, request.schema_name)
    return TableRegistrationResponse(**result)


@router.delete(
    "/tables/{schema_name}/{table_name}",
    response_model=TableRegistrationResponse,
    tags=["sync"],
    summary="Remove a table from sync",
    description="""
    Remove a table from sync and clean up any synced data (admin only).
    
    **Parameters:**
    * **schema_name**: Name of the schema containing the table
    * **table_name**: Name of the table to remove
    
    **Returns:**
    * TableRegistrationResponse with updated status
    
    **Example:**
    ```bash
    curl -X DELETE "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390/data" \\
      -H "Authorization: Bearer your_access_token"
    ```
    """,
    responses={
        200: {
            "model": TableRegistrationResponse,
            "description": "Table successfully removed from sync"
        },
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to remove tables"},
        404: {"description": "Table not found"},
        500: {"description": "Internal server error"}
    }
)
async def remove_table(
    schema_name: str,
    table_name: str,
    _: str = Depends(get_current_admin_user)
) -> TableRegistrationResponse:
    """Remove a table from sync and clean up any synced data."""
    result = await sync_service.remove_table(table_name, schema_name)
    return TableRegistrationResponse(**result)


@router.post(
    "/start",
    response_model=SyncResponse,
    tags=["sync"],
    summary="Start table synchronization",
    description="""
    Start a table synchronization process.
    
    **Curl example:**
    ```shell
    curl -X POST "http://localhost:8000/api/v1/sync/start" \\
      -H "Authorization: Bearer your_access_token" \\
      -H "Content-Type: application/json" \\
      -d '{
        "sync_request": {
          "table_name": "data",
          "schema_name": "WORKSPACE_833213390",
          "strategy": "full"
        }
      }'
    ```
    """
)
async def start_sync(
    request: SyncStartRequest,
    _: str = Depends(get_current_admin_user)
) -> SyncResponse:
    """Start a table synchronization."""
    try:
        return await sync_service.start_sync(request.sync_request, request.config)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        # Log the error here but don't expose internal details
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )


@router.get(
    "/jobs/{sync_id}",
    response_model=SyncResponse,
    tags=["sync"],
    summary="Get sync job status",
    description="""
    Get the status of a sync job.
    
    **Curl example:**
    ```shell
    curl -X GET "http://localhost:8000/api/v1/sync/jobs/your_sync_id" \\
      -H "Authorization: Bearer your_access_token"
    ```
    """
)
async def get_sync_status(
    sync_id: str,
    _: str = Depends(get_current_admin_user)
) -> SyncResponse:
    """Get the status of a sync job."""
    return await sync_service.get_sync_status(sync_id)


@router.get(
    "/tables/{schema_name}/{table_name}/status",
    response_model=TableSyncStatus,
    tags=["sync"],
    summary="Get table sync status",
    description="""
    Get the sync status for a specific table.
    
    **Curl example:**
    ```shell
    curl -X GET "http://localhost:8000/api/v1/sync/tables/WORKSPACE_833213390/data/status" \\
      -H "Authorization: Bearer your_access_token"
    ```
    """
)
async def get_table_sync_status(
    schema_name: str,
    table_name: str,
    _: str = Depends(get_current_admin_user)
) -> TableSyncStatus:
    """Get sync status for a table."""
    return await sync_service.get_table_sync_status(table_name, schema_name) 