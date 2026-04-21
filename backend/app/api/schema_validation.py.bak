"""Schema validation management API routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.deps import CurrentUser, DBSession, RequireWorkflowView, RequireWorkflowEdit
from app.core.logging_config import get_logger
from app.models.schema import SchemaStatus, SchemaType, ValidationResult, WorkflowSchema
from app.models.workflow import Workflow
from app.services.schema_service import SchemaService, SchemaValidationError

logger = get_logger(__name__)
router = APIRouter(prefix="/schemas", tags=["schema-validation"])


# Request/Response Schemas

class SchemaCreateRequest(BaseModel):
    """Create schema request."""
    
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    schema_type: SchemaType = Field(default=SchemaType.JSON_SCHEMA)
    schema_definition: dict = Field(..., description="JSON Schema definition")
    is_required: bool = True
    fail_on_error: bool = True


class SchemaUpdateRequest(BaseModel):
    """Update schema request."""
    
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    schema_definition: dict | None = None
    is_required: bool | None = None
    fail_on_error: bool | None = None
    status: SchemaStatus | None = None


class SchemaResponse(BaseModel):
    """Schema response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_id: UUID
    name: str
    description: str | None
    schema_type: str
    status: str
    is_required: bool
    fail_on_error: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ValidationRequest(BaseModel):
    """Validate payload request."""
    
    payload: dict = Field(..., description="Payload to validate")


class ValidationResponse(BaseModel):
    """Validation response."""
    
    valid: bool
    result: str
    errors: list[str] | None
    error_message: str | None
    validation_duration_ms: float | None


class WorkflowValidationResponse(BaseModel):
    """Workflow validation response."""
    
    valid: bool
    result: str
    failed_required: bool
    schema_validations: list[dict]


from datetime import datetime


@router.get("/workflows/{workflow_id}", response_model=list[SchemaResponse])
async def list_workflow_schemas(
    workflow_id: UUID,
    db: DBSession,
    user: RequireWorkflowView,
    status: SchemaStatus | None = Query(None),
) -> Any:
    """List schemas for a workflow."""
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
    
    schemas = await SchemaService.get_schemas_by_workflow(db, workflow_id, status)
    
    return [
        {
            "id": s.id,
            "workflow_id": s.workflow_id,
            "name": s.name,
            "description": s.description,
            "schema_type": s.schema_type.value,
            "status": s.status.value,
            "is_required": s.is_required,
            "fail_on_error": s.fail_on_error,
            "version": s.version,
            "created_at": s.created_at,
            "updated_at": s.updated_at,
        }
        for s in schemas
    ]


@router.post("/workflows/{workflow_id}", response_model=SchemaResponse, status_code=status.HTTP_201_CREATED)
async def create_schema(
    workflow_id: UUID,
    data: SchemaCreateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Create a new schema for workflow validation."""
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
    
    try:
        schema = await SchemaService.create_schema(
            db=db,
            workflow=workflow,
            name=data.name,
            schema_definition=data.schema_definition,
            schema_type=data.schema_type,
            description=data.description,
            is_required=data.is_required,
            fail_on_error=data.fail_on_error,
        )
        
        return {
            "id": schema.id,
            "workflow_id": schema.workflow_id,
            "name": schema.name,
            "description": schema.description,
            "schema_type": schema.schema_type.value,
            "status": schema.status.value,
            "is_required": schema.is_required,
            "fail_on_error": schema.fail_on_error,
            "version": schema.version,
            "created_at": schema.created_at,
            "updated_at": schema.updated_at,
        }
        
    except SchemaValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/{schema_id}", response_model=SchemaResponse)
async def get_schema(
    schema_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get schema by ID."""
    result = await db.execute(
        select(WorkflowSchema).where(
            WorkflowSchema.id == schema_id,
            WorkflowSchema.organization_id == user.organization_id,
        )
    )
    schema = result.scalar_one_or_none()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found",
        )
    
    return {
        "id": schema.id,
        "workflow_id": schema.workflow_id,
        "name": schema.name,
        "description": schema.description,
        "schema_type": schema.schema_type.value,
        "status": schema.status.value,
        "is_required": schema.is_required,
        "fail_on_error": schema.fail_on_error,
        "version": schema.version,
        "created_at": schema.created_at,
        "updated_at": schema.updated_at,
    }


@router.put("/{schema_id}", response_model=SchemaResponse)
async def update_schema(
    schema_id: UUID,
    data: SchemaUpdateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Update schema (creates new version)."""
    result = await db.execute(
        select(WorkflowSchema).where(
            WorkflowSchema.id == schema_id,
            WorkflowSchema.organization_id == user.organization_id,
        )
    )
    schema = result.scalar_one_or_none()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found",
        )
    
    updated = await SchemaService.update_schema(
        db=db,
        schema=schema,
        name=data.name,
        schema_definition=data.schema_definition,
        description=data.description,
        is_required=data.is_required,
        fail_on_error=data.fail_on_error,
        status=data.status,
    )
    
    return {
        "id": updated.id,
        "workflow_id": updated.workflow_id,
        "name": updated.name,
        "description": updated.description,
        "schema_type": updated.schema_type.value,
        "status": updated.status.value,
        "is_required": updated.is_required,
        "fail_on_error": updated.fail_on_error,
        "version": updated.version,
        "created_at": updated.created_at,
        "updated_at": updated.updated_at,
    }


@router.delete("/{schema_id}")
async def delete_schema(
    schema_id: UUID,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> dict:
    """Delete schema (marks as deprecated)."""
    result = await db.execute(
        select(WorkflowSchema).where(
            WorkflowSchema.id == schema_id,
            WorkflowSchema.organization_id == user.organization_id,
        )
    )
    schema = result.scalar_one_or_none()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found",
        )
    
    await SchemaService.delete_schema(db, schema)
    
    return {"message": "Schema deprecated successfully"}


@router.post("/{schema_id}/validate", response_model=ValidationResponse)
async def validate_payload(
    schema_id: UUID,
    data: ValidationRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Validate a payload against a schema."""
    result = await db.execute(
        select(WorkflowSchema).where(
            WorkflowSchema.id == schema_id,
            WorkflowSchema.organization_id == user.organization_id,
        )
    )
    schema = result.scalar_one_or_none()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found",
        )
    
    validation = await SchemaService.validate_payload(db, schema, data.payload)
    
    return validation


@router.post("/workflows/{workflow_id}/validate", response_model=WorkflowValidationResponse)
async def validate_workflow_payload(
    workflow_id: UUID,
    data: ValidationRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Validate payload against all active schemas for a workflow."""
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
    
    validation = await SchemaService.validate_workflow_payload(
        db, workflow, data.payload
    )
    
    return validation


@router.get("/{schema_id}/logs")
async def get_validation_logs(
    schema_id: UUID,
    db: DBSession,
    user: CurrentUser,
    result: ValidationResult | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """Get validation logs for a schema."""
    # Verify schema belongs to user
    schema_result = await db.execute(
        select(WorkflowSchema).where(
            WorkflowSchema.id == schema_id,
            WorkflowSchema.organization_id == user.organization_id,
        )
    )
    schema = schema_result.scalar_one_or_none()
    
    if not schema:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schema not found",
        )
    
    from app.models.schema import SchemaValidationLog
    
    query = select(SchemaValidationLog).where(
        SchemaValidationLog.schema_id == schema_id
    )
    
    if result:
        query = query.where(SchemaValidationLog.result == result)
    
    query = query.order_by(SchemaValidationLog.validated_at.desc()).limit(limit)
    
    logs_result = await db.execute(query)
    logs = logs_result.scalars().all()
    
    return [
        {
            "id": log.id,
            "result": log.result.value,
            "payload": log.payload,
            "errors": log.errors,
            "error_message": log.error_message,
            "validated_at": log.validated_at,
            "validation_duration_ms": log.validation_duration_ms,
        }
        for log in logs
    ]
