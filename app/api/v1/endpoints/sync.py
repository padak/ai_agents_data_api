from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from pydantic import BaseModel

from app.api.deps import get_current_admin_user
from app.schemas.sync import SyncRequest, SyncResponse, SyncConfig, TableSyncStatus, TableRegistration, TableRegistrationResponse
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


@router.get("/tables/{schema_name}", response_model=List[TableInfo])
async def list_tables(
    schema_name: str,
    _=Depends(get_current_admin_user)
):
    """List all tables in the specified schema"""
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


@router.post("/tables/register", response_model=TableRegistrationResponse)
async def register_table(
    request: TableRegistration,
    _: str = Depends(get_current_admin_user)
) -> TableRegistrationResponse:
    """Register a table for syncing (admin only)"""
    result = await sync_service.register_table(request.table_name, request.schema_name)
    return TableRegistrationResponse(**result)


@router.post("/start", response_model=SyncResponse)
async def start_sync(
    request: SyncRequest,
    config: SyncConfig = None,
    _: str = Depends(get_current_admin_user)
) -> SyncResponse:
    """Start a table synchronization"""
    return await sync_service.start_sync(request, config)


@router.get("/jobs/{sync_id}", response_model=SyncResponse)
async def get_sync_status(
    sync_id: str,
    _=Depends(get_current_admin_user)
):
    """Get the status of a sync job"""
    status = sync_service.get_sync_status(sync_id)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync job not found"
        )
    return status


@router.get("/tables/{schema_name}/{table_name}/status", response_model=TableSyncStatus)
async def get_table_sync_status(
    schema_name: str,
    table_name: str,
    _=Depends(get_current_admin_user)
):
    """Get sync status for a specific table"""
    if not sync_service.is_table_allowed(table_name, schema_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Table sync not allowed"
        )

    status = sync_service.get_table_sync_status(table_name, schema_name)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Table sync status not found"
        )
    return status 