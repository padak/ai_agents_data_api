from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from app.api.deps import get_current_admin_user
from app.schemas.sync import SyncRequest, SyncResponse, SyncConfig, TableSyncStatus
from app.services.sync import SyncService
from app.tasks.sync import sync_table

router = APIRouter()
sync_service = SyncService()


@router.post("/start", response_model=SyncResponse)
async def start_sync(
    request: SyncRequest,
    config: Optional[SyncConfig] = None,
    _=Depends(get_current_admin_user)
):
    """Start a table synchronization process"""
    # Validate table access
    if not sync_service.is_table_allowed(request.table_name, request.schema_name):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Table sync not allowed"
        )

    # Create sync job
    sync_id = sync_service.create_sync_job(
        table_name=request.table_name,
        schema_name=request.schema_name,
        strategy=request.strategy,
        config=config
    )

    # Start async task
    task = sync_table.delay(
        sync_id=sync_id,
        table_name=request.table_name,
        schema_name=request.schema_name,
        strategy=request.strategy,
        incremental_key=config.incremental_key if config else None,
        filter_condition=config.filter_condition if config else None,
        batch_size=config.batch_size if config else 10000
    )

    return {
        "sync_id": sync_id,
        "task_id": task.id,
        "status": "pending"
    }


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