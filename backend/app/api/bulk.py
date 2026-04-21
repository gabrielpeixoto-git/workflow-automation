"""Bulk operations API routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import DBSession, RequireWorkflowEdit, get_client_info
from app.core.logging_config import get_logger
from app.services.bulk_service import BulkAction, BulkService

logger = get_logger(__name__)
router = APIRouter(prefix="/bulk", tags=["bulk-operations"])


# Request/Response Schemas

class BulkActionRequest(BaseModel):
    """Bulk action request."""
    
    workflow_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of workflow IDs to process (max 100)"
    )
    action: BulkAction = Field(..., description="Bulk action to execute")
    tags: list[str] | None = Field(
        None,
        description="Tags to add or remove (for tag_add/tag_remove actions)"
    )
    confirm: bool = Field(
        default=False,
        description="Must be true to execute the action"
    )


class BulkPreviewRequest(BaseModel):
    """Bulk action preview request."""
    
    workflow_ids: list[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of workflow IDs to preview"
    )
    action: BulkAction = Field(..., description="Bulk action to preview")


class BulkActionResponse(BaseModel):
    """Bulk action response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    action: str
    total: int
    successful: int
    failed: int
    success_rate: str
    errors: list[dict]
    details: dict


class BulkPreviewResponse(BaseModel):
    """Bulk action preview response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    action: str
    total: int
    requested: int
    found: int
    not_found: int
    status_breakdown: dict[str, int]
    workflows: list[dict]


@router.post("/workflows/execute", response_model=BulkActionResponse)
async def execute_bulk_action(
    request: Request,
    data: BulkActionRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Execute a bulk action on multiple workflows.
    
    Available actions:
    - **activate**: Activate workflows
    - **deactivate**: Deactivate workflows  
    - **delete**: Soft delete workflows
    - **tag_add**: Add tags to workflows
    - **tag_remove**: Remove tags from workflows
    - **clone**: Clone workflows
    
    **Note**: Requires confirmation (`confirm: true`)
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must confirm by setting confirm=true",
        )
    
    # Get client info for audit
    ip_address, user_agent = await get_client_info(request)
    
    # Execute bulk action
    result = await BulkService.execute_bulk_action(
        db=db,
        user=user,
        workflow_ids=data.workflow_ids,
        action=data.action,
        ip_address=ip_address,
        user_agent=user_agent,
        tags=data.tags,
    )
    
    return result.to_dict()


@router.post("/workflows/preview", response_model=BulkPreviewResponse)
async def preview_bulk_action(
    data: BulkPreviewRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Preview a bulk action without executing it.
    
    Shows which workflows would be affected and their current status.
    Use this to verify the selection before executing.
    """
    preview = await BulkService.get_bulk_action_preview(
        db=db,
        user=user,
        workflow_ids=data.workflow_ids,
        action=data.action,
    )
    
    return preview


@router.get("/actions")
async def list_bulk_actions(
    user: RequireWorkflowEdit,
) -> Any:
    """List available bulk actions and their descriptions."""
    return {
        "actions": [
            {
                "value": BulkAction.ACTIVATE.value,
                "label": "Ativar Workflows",
                "description": "Ativa todos os workflows selecionados",
                "requires_confirmation": True,
                "dangerous": False,
            },
            {
                "value": BulkAction.DEACTIVATE.value,
                "label": "Desativar Workflows",
                "description": "Desativa todos os workflows selecionados",
                "requires_confirmation": True,
                "dangerous": False,
            },
            {
                "value": BulkAction.DELETE.value,
                "label": "Excluir Workflows",
                "description": "Exclui (soft delete) todos os workflows selecionados",
                "requires_confirmation": True,
                "dangerous": True,
            },
            {
                "value": BulkAction.TAG_ADD.value,
                "label": "Adicionar Tags",
                "description": "Adiciona tags aos workflows selecionados",
                "requires_confirmation": True,
                "dangerous": False,
                "requires_tags": True,
            },
            {
                "value": BulkAction.TAG_REMOVE.value,
                "label": "Remover Tags",
                "description": "Remove tags dos workflows selecionados",
                "requires_confirmation": True,
                "dangerous": False,
                "requires_tags": True,
            },
            {
                "value": BulkAction.CLONE.value,
                "label": "Clonar Workflows",
                "description": "Cria cópias dos workflows selecionados",
                "requires_confirmation": True,
                "dangerous": False,
            },
        ],
        "limits": {
            "max_workflows_per_operation": 100,
            "note": "Operações em massa são limitadas a 100 workflows por vez",
        },
    }
