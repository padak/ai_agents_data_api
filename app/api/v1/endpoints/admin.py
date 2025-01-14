from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.core.auth import get_admin_token
from app.schemas.admin import (
    TokenResponse,
    TokenCreate,
    TableManagement,
    TableResponse,
)
from app.services.admin import AdminService

router = APIRouter()
admin_service = AdminService()


@router.post("/tokens", response_model=TokenResponse)
async def create_token(
    token_data: TokenCreate,
    _: str = Depends(get_admin_token),
) -> TokenResponse:
    """Create a new token (swarm or agent)"""
    return await admin_service.create_token(token_data)


@router.delete("/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    _: str = Depends(get_admin_token),
) -> dict:
    """Revoke an existing token"""
    await admin_service.revoke_token(token_id)
    return {"message": "Token revoked successfully"}


@router.post("/tables", response_model=TableResponse)
async def manage_table(
    table_data: TableManagement,
    _: str = Depends(get_admin_token),
) -> TableResponse:
    """Add or remove tables from the allowed list"""
    return await admin_service.manage_table(table_data)


@router.get("/tables", response_model=List[TableResponse])
async def list_tables(
    _: str = Depends(get_admin_token),
) -> List[TableResponse]:
    """List all allowed tables"""
    return await admin_service.list_tables() 