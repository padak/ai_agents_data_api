from fastapi import APIRouter

from app.api.v1.endpoints import admin, data, artifacts

api_router = APIRouter()

api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(data.router, prefix="/data", tags=["data"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"]) 