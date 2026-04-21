"""Workflow templates API routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import CurrentUser, DBSession, RequireWorkflowEdit
from app.core.logging_config import get_logger
from app.models.template import TemplateCategory, WorkflowTemplate
from app.services.template_service import TemplateService

logger = get_logger(__name__)
router = APIRouter(prefix="/templates", tags=["templates"])


# Request/Response Schemas

class TemplateCreateRequest(BaseModel):
    """Create template from workflow request."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    category: str = Field(default=TemplateCategory.CUSTOM.value)
    workflow_id: UUID = Field(..., description="Workflow ID to use as template")


class TemplateUseRequest(BaseModel):
    """Use template to create workflow request."""
    
    name: str | None = Field(None, min_length=1, max_length=255)
    customizations: dict | None = Field(
        None,
        description="Custom values for template placeholders"
    )


class TemplateResponse(BaseModel):
    """Template response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    slug: str
    name: str
    description: str | None
    category: str
    trigger_type: str | None
    icon: str | None
    color: str | None
    tags: list[str]
    is_builtin: bool
    usage_count: int
    created_at: str


class TemplateDetailResponse(TemplateResponse):
    """Template detail response with steps."""
    
    steps_configuration: list[dict]
    default_configuration: dict


class WorkflowFromTemplateResponse(BaseModel):
    """Workflow created from template response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    slug: str
    status: str
    message: str


@router.get("", response_model=list[TemplateResponse])
async def list_templates(
    db: DBSession,
    user: CurrentUser,
    category: str | None = Query(None),
    search: str | None = Query(None),
    include_builtin: bool = Query(True),
) -> Any:
    """List available workflow templates.
    
    Returns both built-in templates and custom templates for the organization.
    """
    templates = await TemplateService.get_templates(
        db=db,
        organization_id=user.organization_id,
        category=category,
        search=search,
        include_builtin=include_builtin,
    )
    
    return [
        {
            "id": t.id,
            "slug": t.slug,
            "name": t.name,
            "description": t.description,
            "category": t.category,
            "trigger_type": t.trigger_type,
            "icon": t.icon,
            "color": t.color,
            "tags": t.tags or [],
            "is_builtin": t.is_builtin,
            "usage_count": t.usage_count,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in templates
    ]


@router.get("/categories")
async def list_template_categories(
    user: CurrentUser,
) -> Any:
    """List available template categories."""
    return {
        "categories": [
            {
                "value": c.value,
                "label": c.value.replace("_", " ").title(),
            }
            for c in TemplateCategory
        ],
    }


@router.get("/{template_id}", response_model=TemplateDetailResponse)
async def get_template(
    template_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get template details including steps configuration."""
    template = await TemplateService.get_template_by_id(db, template_id)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    
    # Check access (built-in or organization template)
    if not template.is_builtin and template.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return {
        "id": template.id,
        "slug": template.slug,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "trigger_type": template.trigger_type,
        "icon": template.icon,
        "color": template.color,
        "tags": template.tags or [],
        "is_builtin": template.is_builtin,
        "usage_count": template.usage_count,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "steps_configuration": template.steps_configuration,
        "default_configuration": template.default_configuration,
    }


@router.post("/{template_id}/use", response_model=WorkflowFromTemplateResponse, status_code=status.HTTP_201_CREATED)
async def use_template(
    template_id: UUID,
    data: TemplateUseRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Create a workflow from a template.
    
    The workflow is created in INACTIVE status for review before activation.
    """
    template = await TemplateService.get_template_by_id(db, template_id)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    
    # Check access
    if not template.is_builtin and template.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Create workflow from template
    workflow = await TemplateService.create_workflow_from_template(
        db=db,
        template=template,
        user=user,
        name=data.name,
        customizations=data.customizations,
    )
    
    await db.commit()
    
    return {
        "id": workflow.id,
        "name": workflow.name,
        "slug": workflow.slug,
        "status": workflow.status.value if workflow.status else "unknown",
        "message": f"Workflow '{workflow.name}' created from template. Review and activate to use.",
    }


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Create a custom template from an existing workflow.
    
    Allows saving a workflow configuration as a reusable template.
    """
    template = await TemplateService.create_custom_template(
        db=db,
        user=user,
        name=data.name,
        description=data.description,
        category=data.category,
        workflow_id=data.workflow_id,
    )
    
    await db.commit()
    await db.refresh(template)
    
    return {
        "id": template.id,
        "slug": template.slug,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "trigger_type": template.trigger_type,
        "icon": template.icon,
        "color": template.color,
        "tags": template.tags or [],
        "is_builtin": template.is_builtin,
        "usage_count": template.usage_count,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }


@router.delete("/{template_id}")
async def delete_template(
    template_id: UUID,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Delete a custom template.
    
    Built-in templates cannot be deleted.
    """
    template = await TemplateService.get_template_by_id(db, template_id)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    
    # Cannot delete built-in templates
    if template.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Built-in templates cannot be deleted",
        )
    
    # Check ownership
    if template.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    # Soft delete by deactivating
    template.is_active = False
    await db.commit()
    
    return {"message": "Template deleted successfully"}


@router.get("/{template_id}/preview")
async def preview_template(
    template_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Preview what a workflow created from template would look like."""
    template = await TemplateService.get_template_by_id(db, template_id)
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )
    
    # Check access
    if not template.is_builtin and template.organization_id != user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    
    return {
        "template_name": template.name,
        "description": template.description,
        "trigger_type": template.trigger_type,
        "steps_preview": [
            {
                "name": step.get("name"),
                "type": step.get("step_type"),
                "action": step.get("action_type"),
                "order": step.get("order"),
                "has_condition": bool(step.get("condition")),
            }
            for step in template.steps_configuration
        ],
        "estimated_steps": len(template.steps_configuration),
        "tags": template.tags or [],
    }
