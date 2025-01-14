from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    admin,
    queries,
    sync,
    tasks,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(queries.router, prefix="/queries", tags=["queries"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"]) 