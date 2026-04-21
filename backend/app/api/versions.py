"""Workflow versioning API routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, RequireWorkflowView, RequireWorkflowEdit
from app.core.logging_config import get_logger
from app.models.workflow import Workflow
from app.models.workflow_version import WorkflowVersion
from app.services.version_service import VersionService

logger = get_logger(__name__)
router = APIRouter()


# Request/Response Schemas

class CreateVersionRequest(BaseModel):
    """Create version request."""
    
    change_summary: str | None = Field(None, max_length=500)
    version_tag: str | None = Field(None, max_length=50, pattern=r"^[a-zA-Z0-9_\-\.]+$", examples=["v1.0", "release-2024"])


class RestoreVersionRequest(BaseModel):
    """Restore version request."""
    
    confirm: bool = Field(..., description="Must be true to confirm restoration")


class VersionResponse(BaseModel):
    """Version response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_id: UUID
    version_number: int
    version_tag: str | None
    change_summary: str | None
    created_by: UUID | None
    created_by_email: str | None
    is_restored: bool
    created_at: datetime


class VersionDetailResponse(BaseModel):
    """Version detail response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_id: UUID
    version_number: int
    version_tag: str | None
    change_summary: str | None
    created_by: UUID | None
    created_by_email: str | None
    is_restored: bool
    workflow_data: dict
    steps_data: list
    created_at: datetime


class VersionDiffResponse(BaseModel):
    """Version diff response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    from_version: int
    to_version: int
    workflow_changes: dict
    steps_added: list
    steps_removed: list
    steps_modified: list
    total_changes: int
    is_major_change: bool


@router.get("/workflows/{workflow_id}/versions", response_model=list[VersionResponse])
async def list_workflow_versions(
    workflow_id: UUID,
    db: DBSession,
    user: RequireWorkflowView,
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """List version history for a workflow."""
    # Verify workflow belongs to user
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    versions = await VersionService.get_versions(db, workflow_id, limit)
    
    # Get creator emails
    creator_ids = [v.created_by for v in versions if v.created_by]
    creators = {}
    if creator_ids:
        from app.models.user import User
        result = await db.execute(
            select(User.id, User.email).where(User.id.in_(creator_ids))
        )
        creators = {str(row[0]): row[1] for row in result.all()}
    
    return [
        {
            "id": v.id,
            "workflow_id": v.workflow_id,
            "version_number": v.version_number,
            "version_tag": v.version_tag,
            "change_summary": v.change_summary,
            "created_by": v.created_by,
            "created_by_email": creators.get(str(v.created_by), "Sistema"),
            "is_restored": v.is_restored,
            "created_at": v.created_at,
        }
        for v in versions
    ]


@router.post("/workflows/{workflow_id}/versions", response_model=VersionResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow_version(
    workflow_id: UUID,
    data: CreateVersionRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Create a new version of a workflow.
    
    Use this to manually save a version with a tag and summary.
    Versions are also created automatically on workflow updates.
    """
    # Verify workflow belongs to user
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    # Load steps
    await db.refresh(workflow, ["steps"])
    
    version = await VersionService.create_version(
        db=db,
        workflow=workflow,
        user=user,
        change_summary=data.change_summary,
        version_tag=data.version_tag,
    )
    
    return {
        "id": version.id,
        "workflow_id": version.workflow_id,
        "version_number": version.version_number,
        "version_tag": version.version_tag,
        "change_summary": version.change_summary,
        "created_by": version.created_by,
        "created_by_email": user.email,
        "is_restored": version.is_restored,
        "created_at": version.created_at,
    }


@router.get("/workflows/{workflow_id}/versions/{version_number}", response_model=VersionDetailResponse)
async def get_version_detail(
    workflow_id: UUID,
    version_number: int,
    db: DBSession,
    user: RequireWorkflowView,
) -> Any:
    """Get detailed information about a specific version."""
    # Verify workflow belongs to user
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    version = await VersionService.get_version_by_number(db, workflow_id, version_number)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found",
        )
    
    # Get creator email
    creator_email = "Sistema"
    if version.created_by:
        from app.models.user import User
        result = await db.execute(
            select(User.email).where(User.id == version.created_by)
        )
        row = result.scalar_one_or_none()
        if row:
            creator_email = row
    
    return {
        "id": version.id,
        "workflow_id": version.workflow_id,
        "version_number": version.version_number,
        "version_tag": version.version_tag,
        "change_summary": version.change_summary,
        "created_by": version.created_by,
        "created_by_email": creator_email,
        "is_restored": version.is_restored,
        "workflow_data": version.workflow_data,
        "steps_data": version.steps_data,
        "created_at": version.created_at,
    }


@router.post("/workflows/{workflow_id}/versions/{version_number}/restore", response_model=VersionResponse)
async def restore_workflow_version(
    workflow_id: UUID,
    version_number: int,
    data: RestoreVersionRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Restore workflow to a previous version.
    
    This will:
    - Restore the workflow configuration
    - Restore all steps
    - Create a new version marking it as restored
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm restoration by setting confirm=true",
        )
    
    # Verify workflow belongs to user
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    # Get version to restore
    version = await VersionService.get_version_by_number(db, workflow_id, version_number)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} not found",
        )
    
    # Restore
    restored = await VersionService.restore_version(db, workflow, version, user)
    
    # Get the new version created
    new_version = await VersionService.get_version_by_number(
        db, workflow_id, version.version_number + 1
    )
    
    return {
        "id": new_version.id,
        "workflow_id": new_version.workflow_id,
        "version_number": new_version.version_number,
        "version_tag": new_version.version_tag,
        "change_summary": new_version.change_summary,
        "created_by": new_version.created_by,
        "created_by_email": user.email,
        "is_restored": new_version.is_restored,
        "created_at": new_version.created_at,
    }


@router.get("/workflows/{workflow_id}/versions/compare")
async def compare_workflow_versions(
    workflow_id: UUID,
    from_version: int = Query(..., description="Source version number"),
    to_version: int = Query(..., description="Target version number"),
    db: DBSession = DBSession,
    user: RequireWorkflowView = RequireWorkflowView,
) -> Any:
    """Compare two versions and show differences."""
    # Verify workflow belongs to user
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    # Get versions
    v1 = await VersionService.get_version_by_number(db, workflow_id, from_version)
    v2 = await VersionService.get_version_by_number(db, workflow_id, to_version)
    
    if not v1:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {from_version} not found",
        )
    if not v2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {to_version} not found",
        )
    
    # Compare
    try:
        comparison = await VersionService.compare_versions(db, v1.id, v2.id)
        return comparison
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/versions/{version_id}", response_model=VersionDetailResponse)
async def get_version_by_id(
    version_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get version by ID."""
    version = await VersionService.get_version(db, version_id)
    
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )
    
    # Verify user has access
    if version.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Get creator email
    creator_email = "Sistema"
    if version.created_by:
        from app.models.user import User
        result = await db.execute(
            select(User.email).where(User.id == version.created_by)
        )
        row = result.scalar_one_or_none()
        if row:
            creator_email = row
    
    return {
        "id": version.id,
        "workflow_id": version.workflow_id,
        "version_number": version.version_number,
        "version_tag": version.version_tag,
        "change_summary": version.change_summary,
        "created_by": version.created_by,
        "created_by_email": creator_email,
        "is_restored": version.is_restored,
        "workflow_data": version.workflow_data,
        "steps_data": version.steps_data,
        "created_at": version.created_at,
    }
