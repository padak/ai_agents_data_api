import base64
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.duckdb import get_duckdb_connection
from app.schemas.artifacts import (
    ArtifactCreate,
    ArtifactResponse,
    ArtifactUpdate,
    ArtifactFilter,
)


class ArtifactService:
    def __init__(self):
        self.db = get_duckdb_connection()
        self._init_tables()
        self.artifacts_dir = Path("./data/artifacts")
        self.artifacts_dir.mkdir(exist_ok=True)

    def _init_tables(self):
        """Initialize the required tables if they don't exist"""
        # Artifacts table
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id VARCHAR PRIMARY KEY,
                name VARCHAR NOT NULL,
                type VARCHAR NOT NULL,
                format VARCHAR NOT NULL,
                size_bytes INTEGER NOT NULL,
                storage_path VARCHAR NOT NULL,
                created_at TIMESTAMP NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                metadata JSON,
                swarm_token VARCHAR NOT NULL
            )
        """)

        # Artifact tags
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS artifact_tags (
                artifact_id VARCHAR NOT NULL,
                tag VARCHAR NOT NULL,
                PRIMARY KEY (artifact_id, tag),
                FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
            )
        """)

    async def create_artifact(
        self, artifact_data: ArtifactCreate, swarm_token: str
    ) -> ArtifactResponse:
        """Create a new artifact"""
        # Decode and validate content
        try:
            content = base64.b64decode(artifact_data.content)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid base64 encoded content"
            )

        # Check size limit
        size_bytes = len(content)
        if size_bytes > settings.ARTIFACT_MAX_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Artifact size exceeds limit of {settings.ARTIFACT_MAX_SIZE_MB}MB"
            )

        # Generate artifact ID and prepare storage
        artifact_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        expires_at = created_at + timedelta(
            days=artifact_data.expiry_days or settings.ARTIFACT_EXPIRY_DAYS
        )

        # Store the artifact content
        storage_path = self.artifacts_dir / f"{artifact_id}.{artifact_data.format}"
        storage_path.write_bytes(content)

        # Store artifact metadata
        self.db.execute("""
            INSERT INTO artifacts (
                artifact_id, name, type, format, size_bytes,
                storage_path, created_at, expires_at, metadata, swarm_token
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            artifact_id, artifact_data.name, artifact_data.type, artifact_data.format,
            size_bytes, str(storage_path), created_at, expires_at,
            json.dumps(artifact_data.metadata), swarm_token
        ])

        # Store tags
        if artifact_data.tags:
            self.db.executemany(
                "INSERT INTO artifact_tags (artifact_id, tag) VALUES (?, ?)",
                [(artifact_id, tag) for tag in artifact_data.tags]
            )

        return await self.get_artifact(artifact_id, swarm_token)

    async def get_artifact(self, artifact_id: str, swarm_token: str) -> ArtifactResponse:
        """Get artifact metadata"""
        result = self.db.execute("""
            SELECT 
                a.artifact_id,
                a.name,
                a.type,
                a.format,
                a.size_bytes,
                a.created_at,
                a.expires_at,
                a.metadata,
                array_agg(t.tag) as tags
            FROM artifacts a
            LEFT JOIN artifact_tags t ON a.artifact_id = t.artifact_id
            WHERE a.artifact_id = ? AND a.swarm_token = ?
            GROUP BY a.artifact_id, a.name, a.type, a.format,
                     a.size_bytes, a.created_at, a.expires_at, a.metadata
        """, [artifact_id, swarm_token]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact {artifact_id} not found"
            )

        return ArtifactResponse(
            artifact_id=result[0],
            name=result[1],
            type=result[2],
            format=result[3],
            size_bytes=result[4],
            created_at=result[5],
            expires_at=result[6],
            metadata=json.loads(result[7]) if result[7] else {},
            tags=result[8] if result[8] else []
        )

    async def get_artifact_content(self, artifact_id: str, swarm_token: str) -> bytes:
        """Get artifact content"""
        result = self.db.execute("""
            SELECT storage_path
            FROM artifacts
            WHERE artifact_id = ? AND swarm_token = ?
        """, [artifact_id, swarm_token]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact {artifact_id} not found"
            )

        storage_path = Path(result[0])
        if not storage_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact {artifact_id} content not found"
            )

        # Update expiration on access
        new_expires_at = datetime.utcnow() + timedelta(days=settings.ARTIFACT_EXPIRY_DAYS)
        self.db.execute("""
            UPDATE artifacts
            SET expires_at = ?
            WHERE artifact_id = ?
        """, [new_expires_at, artifact_id])

        return storage_path.read_bytes()

    async def update_artifact(
        self, artifact_id: str, update_data: ArtifactUpdate, swarm_token: str
    ) -> ArtifactResponse:
        """Update artifact metadata"""
        # Check if artifact exists
        await self.get_artifact(artifact_id, swarm_token)

        # Build update query
        updates = []
        params = []
        if update_data.name is not None:
            updates.append("name = ?")
            params.append(update_data.name)
        if update_data.metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(update_data.metadata))
        if update_data.expiry_days is not None:
            updates.append("expires_at = ?")
            params.append(
                datetime.utcnow() + timedelta(days=update_data.expiry_days)
            )

        if updates:
            params.extend([artifact_id, swarm_token])
            self.db.execute(f"""
                UPDATE artifacts
                SET {", ".join(updates)}
                WHERE artifact_id = ? AND swarm_token = ?
            """, params)

        # Update tags if provided
        if update_data.tags is not None:
            self.db.execute(
                "DELETE FROM artifact_tags WHERE artifact_id = ?",
                [artifact_id]
            )
            if update_data.tags:
                self.db.executemany(
                    "INSERT INTO artifact_tags (artifact_id, tag) VALUES (?, ?)",
                    [(artifact_id, tag) for tag in update_data.tags]
                )

        return await self.get_artifact(artifact_id, swarm_token)

    async def delete_artifact(self, artifact_id: str, swarm_token: str):
        """Delete an artifact"""
        result = self.db.execute("""
            SELECT storage_path
            FROM artifacts
            WHERE artifact_id = ? AND swarm_token = ?
        """, [artifact_id, swarm_token]).fetchone()

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Artifact {artifact_id} not found"
            )

        # Delete the file
        storage_path = Path(result[0])
        if storage_path.exists():
            storage_path.unlink()

        # Delete from database
        self.db.execute("DELETE FROM artifact_tags WHERE artifact_id = ?", [artifact_id])
        self.db.execute("DELETE FROM artifacts WHERE artifact_id = ?", [artifact_id])

    async def list_artifacts(
        self, swarm_token: str, filter_params: Optional[ArtifactFilter] = None
    ) -> List[ArtifactResponse]:
        """List artifacts with optional filtering"""
        query = """
            SELECT 
                a.artifact_id,
                a.name,
                a.type,
                a.format,
                a.size_bytes,
                a.created_at,
                a.expires_at,
                a.metadata,
                array_agg(t.tag) as tags
            FROM artifacts a
            LEFT JOIN artifact_tags t ON a.artifact_id = t.artifact_id
            WHERE a.swarm_token = ?
        """
        params = [swarm_token]

        if filter_params:
            if filter_params.type:
                query += " AND a.type = ?"
                params.append(filter_params.type)
            if filter_params.format:
                query += " AND a.format = ?"
                params.append(filter_params.format)
            if filter_params.created_after:
                query += " AND a.created_at >= ?"
                params.append(filter_params.created_after)
            if filter_params.created_before:
                query += " AND a.created_at <= ?"
                params.append(filter_params.created_before)
            if filter_params.min_size:
                query += " AND a.size_bytes >= ?"
                params.append(filter_params.min_size)
            if filter_params.max_size:
                query += " AND a.size_bytes <= ?"
                params.append(filter_params.max_size)

        query += """
            GROUP BY a.artifact_id, a.name, a.type, a.format,
                     a.size_bytes, a.created_at, a.expires_at, a.metadata
            ORDER BY a.created_at DESC
        """

        results = self.db.execute(query, params).fetchall()

        artifacts = []
        for row in results:
            # Filter by tags if specified
            if filter_params and filter_params.tags:
                row_tags = row[8] if row[8] else []
                if not all(tag in row_tags for tag in filter_params.tags):
                    continue

            artifacts.append(ArtifactResponse(
                artifact_id=row[0],
                name=row[1],
                type=row[2],
                format=row[3],
                size_bytes=row[4],
                created_at=row[5],
                expires_at=row[6],
                metadata=json.loads(row[7]) if row[7] else {},
                tags=row[8] if row[8] else []
            ))

        return artifacts

    async def cleanup_expired(self):
        """Clean up expired artifacts"""
        expired = self.db.execute("""
            SELECT artifact_id, storage_path
            FROM artifacts
            WHERE expires_at < ?
        """, [datetime.utcnow()]).fetchall()

        for artifact_id, storage_path in expired:
            # Delete file if exists
            path = Path(storage_path)
            if path.exists():
                path.unlink()

            # Delete from database
            self.db.execute(
                "DELETE FROM artifact_tags WHERE artifact_id = ?",
                [artifact_id]
            )
            self.db.execute(
                "DELETE FROM artifacts WHERE artifact_id = ?",
                [artifact_id]
            ) 