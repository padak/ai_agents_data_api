from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Dict, Any

from app.api.deps import get_current_admin_user
from app.schemas.queries import QueryRequest, QueryResponse, QueryConfig
from app.services.queries import QueryService
from app.tasks.queries import execute_query

router = APIRouter()
query_service = QueryService()


@router.post("/execute", response_model=QueryResponse)
async def execute_query_endpoint(
    request: QueryRequest,
    config: Optional[QueryConfig] = None,
    _=Depends(get_current_admin_user)
):
    """Execute a query asynchronously"""
    # Validate query access
    if not query_service.is_query_allowed(request.query):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Query not allowed"
        )

    # Create query job
    query_id = query_service.create_query_job(
        query=request.query,
        output_format=request.output_format,
        config=config
    )

    # Start async task
    task = execute_query.delay(
        query_id=query_id,
        query=request.query,
        output_format=request.output_format,
        params=config.params if config else None
    )

    return {
        "query_id": query_id,
        "task_id": task.id,
        "status": "pending"
    }


@router.get("/jobs/{query_id}", response_model=QueryResponse)
async def get_query_status(
    query_id: str,
    _=Depends(get_current_admin_user)
):
    """Get the status of a query job"""
    status = query_service.get_query_status(query_id)
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query job not found"
        )
    return status


@router.get("/jobs/{query_id}/result")
async def get_query_result(
    query_id: str,
    _=Depends(get_current_admin_user)
) -> Dict[str, Any]:
    """Get the result of a completed query job"""
    result = query_service.get_query_result(query_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query result not found"
        )
    return result 