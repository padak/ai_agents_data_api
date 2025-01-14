from fastapi import APIRouter

from app.api.v1.endpoints import (
    queries,
    sync,
)

api_router = APIRouter()
api_router.include_router(queries.router, prefix="/queries", tags=["queries"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"]) 