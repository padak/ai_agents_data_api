from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_admin_token
from app.schemas.sync import (
    SyncRequest,
    SyncResponse,
    SyncConfig,
    TableSyncStatus,
)
from app.services.sync import SyncService

router = APIRouter()
sync_service = SyncService()


@router.post("/start", response_model=SyncResponse)
async def start_sync(
    sync_request: SyncRequest,
    config: SyncConfig = None,
    _: str = Depends(get_admin_token),
) -> SyncResponse:
    """Start a table synchronization"""
    return await sync_service.start_sync(sync_request, config)


@router.get("/jobs/{sync_id}", response_model=SyncResponse)
async def get_sync_status(
    sync_id: str,
    _: str = Depends(get_admin_token),
) -> SyncResponse:
    """Get the status of a sync job"""
    return await sync_service.get_sync_status(sync_id)


@router.get("/tables/{schema_name}/{table_name}/status", response_model=TableSyncStatus)
async def get_table_sync_status(
    schema_name: str,
    table_name: str,
    _: str = Depends(get_admin_token),
) -> TableSyncStatus:
    """Get sync status for a table"""
    return await sync_service.get_table_sync_status(table_name, schema_name) 