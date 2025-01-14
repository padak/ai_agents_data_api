from typing import Any, Dict, List, Union

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_agent_tokens
from app.schemas.data import (
    DataSampleRequest,
    QueryRequest,
    QueryResponse,
    QueryStatusResponse,
    TableMetadata,
    ProfileRequest,
)
from app.services.data import DataService

router = APIRouter()
data_service = DataService()


@router.get("/tables/{schema_name}/{table_name}/metadata", response_model=TableMetadata)
async def get_table_metadata(
    schema_name: str,
    table_name: str,
    _: tuple[str, str] = Depends(get_agent_tokens),
) -> TableMetadata:
    """Get metadata for a specific table"""
    return await data_service.get_table_metadata(table_name, schema_name)


@router.post("/sample")
async def get_data_sample(
    request: DataSampleRequest,
    _: tuple[str, str] = Depends(get_agent_tokens),
) -> Union[str, Dict[str, Any]]:
    """Get a sample of data from a table"""
    return await data_service.get_data_sample(request)


@router.post("/query", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    _: tuple[str, str] = Depends(get_agent_tokens),
) -> QueryResponse:
    """Submit a query for execution"""
    return await data_service.submit_query(request)


@router.get("/query/{job_id}", response_model=QueryStatusResponse)
async def get_query_status(
    job_id: str,
    _: tuple[str, str] = Depends(get_agent_tokens),
) -> QueryStatusResponse:
    """Get the status of a query job"""
    return await data_service.get_query_status(job_id)


@router.post("/profile")
async def generate_profile(
    request: ProfileRequest,
    _: tuple[str, str] = Depends(get_agent_tokens),
) -> Dict[str, Any]:
    """Generate a profile for a table"""
    return await data_service.generate_profile(request) 