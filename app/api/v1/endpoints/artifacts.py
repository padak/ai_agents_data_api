from typing import List, Optional
from fastapi import APIRouter, Depends, Response
from fastapi.responses import StreamingResponse

from app.core.auth import get_agent_tokens
from app.schemas.artifacts import (
    ArtifactCreate,
    ArtifactResponse,
    ArtifactUpdate,
    ArtifactFilter,
)
from app.services.artifacts import ArtifactService

router = APIRouter()
artifact_service = ArtifactService()


@router.post("", response_model=ArtifactResponse)
async def create_artifact(
    artifact_data: ArtifactCreate,
    tokens: tuple[str, str] = Depends(get_agent_tokens),
) -> ArtifactResponse:
    """Create a new artifact"""
    swarm_token, _ = tokens
    return await artifact_service.create_artifact(artifact_data, swarm_token)


@router.get("", response_model=List[ArtifactResponse])
async def list_artifacts(
    type: Optional[str] = None,
    format: Optional[str] = None,
    tags: Optional[List[str]] = None,
    tokens: tuple[str, str] = Depends(get_agent_tokens),
) -> List[ArtifactResponse]:
    """List artifacts with optional filtering"""
    swarm_token, _ = tokens
    filter_params = ArtifactFilter(
        type=type,
        format=format,
        tags=tags,
    )
    return await artifact_service.list_artifacts(swarm_token, filter_params)


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: str,
    tokens: tuple[str, str] = Depends(get_agent_tokens),
) -> ArtifactResponse:
    """Get artifact metadata"""
    swarm_token, _ = tokens
    return await artifact_service.get_artifact(artifact_id, swarm_token)


@router.get("/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: str,
    tokens: tuple[str, str] = Depends(get_agent_tokens),
) -> StreamingResponse:
    """Get artifact content"""
    swarm_token, _ = tokens
    content = await artifact_service.get_artifact_content(artifact_id, swarm_token)
    
    # Get artifact metadata for content type
    artifact = await artifact_service.get_artifact(artifact_id, swarm_token)
    
    # Set appropriate content type based on format
    content_type = {
        "json": "application/json",
        "csv": "text/csv",
        "parquet": "application/octet-stream",
        "pickle": "application/octet-stream",
        "text": "text/plain",
        "binary": "application/octet-stream",
    }.get(artifact.format, "application/octet-stream")
    
    return StreamingResponse(
        iter([content]),
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{artifact.name}"'}
    )


@router.patch("/{artifact_id}", response_model=ArtifactResponse)
async def update_artifact(
    artifact_id: str,
    update_data: ArtifactUpdate,
    tokens: tuple[str, str] = Depends(get_agent_tokens),
) -> ArtifactResponse:
    """Update artifact metadata"""
    swarm_token, _ = tokens
    return await artifact_service.update_artifact(artifact_id, update_data, swarm_token)


@router.delete("/{artifact_id}")
async def delete_artifact(
    artifact_id: str,
    tokens: tuple[str, str] = Depends(get_agent_tokens),
) -> dict:
    """Delete an artifact"""
    swarm_token, _ = tokens
    await artifact_service.delete_artifact(artifact_id, swarm_token)
    return {"message": "Artifact deleted successfully"} 