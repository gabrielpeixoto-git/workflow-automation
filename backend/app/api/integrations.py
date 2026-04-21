"""Integrations API routes for external services."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.deps import CurrentUser, DBSession, RequireWorkflowEdit
from app.core.logging_config import get_logger
from app.models.integration import Integration, IntegrationLog, IntegrationStatus, IntegrationType
from app.services.integration_service import IntegrationService

logger = get_logger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


# Request/Response Schemas

class SlackConfig(BaseModel):
    """Slack integration configuration."""
    webhook_url: str = Field(..., description="Slack incoming webhook URL")
    default_channel: str | None = Field(None, description="Default channel")
    username: str | None = Field(None, description="Bot username")


class SMTPConfig(BaseModel):
    """SMTP integration configuration."""
    host: str = Field(..., description="SMTP server host")
    port: int = Field(default=587, ge=1, le=65535)
    username: str = Field(..., description="SMTP username")
    password: str = Field(..., description="SMTP password")
    from_email: str = Field(..., description="From email address")
    use_tls: bool = Field(default=True)


class DiscordConfig(BaseModel):
    """Discord integration configuration."""
    webhook_url: str = Field(..., description="Discord webhook URL")
    username: str | None = Field(None, description="Bot username")
    avatar_url: str | None = Field(None, description="Bot avatar URL")


class IntegrationCreateRequest(BaseModel):
    """Create integration request."""
    name: str = Field(..., min_length=1, max_length=255)
    integration_type: str = Field(..., description="Type: slack, email_smtp, discord")
    configuration: dict = Field(default={}, description="Service-specific configuration")
    settings: dict = Field(default={}, description="Additional settings")
    is_default: bool = Field(default=False)


class IntegrationUpdateRequest(BaseModel):
    """Update integration request."""
    name: str | None = Field(None, min_length=1, max_length=255)
    configuration: dict | None = None
    settings: dict | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class IntegrationResponse(BaseModel):
    """Integration response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    integration_type: str
    status: str
    status_message: str | None
    use_count: int
    success_count: int
    error_count: int
    success_rate: float
    is_default: bool
    last_used_at: str | None
    created_at: str


class IntegrationDetailResponse(IntegrationResponse):
    """Integration detail response."""
    
    configuration: dict
    settings: dict


class IntegrationTestResponse(BaseModel):
    """Integration test response."""
    success: bool
    message: str
    details: dict | None = None


class IntegrationExecuteRequest(BaseModel):
    """Execute integration request."""
    event_type: str = Field(default="manual_trigger")
    payload: dict = Field(default={}, description="Payload for the integration")


class IntegrationExecuteResponse(BaseModel):
    """Integration execute response."""
    success: bool
    message: str
    duration_ms: float | None = None


@router.get("/types")
async def list_integration_types(
    user: CurrentUser,
) -> Any:
    """List available integration types with their schemas."""
    return {
        "types": [
            {
                "value": IntegrationType.SLACK.value,
                "label": "Slack",
                "description": "Send messages to Slack channels via webhooks",
                "icon": "slack",
                "color": "#4A154B",
                "config_schema": {
                    "webhook_url": {"type": "string", "required": True, "label": "Webhook URL"},
                    "default_channel": {"type": "string", "required": False, "label": "Default Channel"},
                    "username": {"type": "string", "required": False, "label": "Bot Username"},
                },
            },
            {
                "value": IntegrationType.EMAIL_SMTP.value,
                "label": "Email (SMTP)",
                "description": "Send emails via SMTP server",
                "icon": "mail",
                "color": "#007bff",
                "config_schema": {
                    "host": {"type": "string", "required": True, "label": "SMTP Host"},
                    "port": {"type": "integer", "required": True, "default": 587, "label": "Port"},
                    "username": {"type": "string", "required": True, "label": "Username"},
                    "password": {"type": "string", "required": True, "secret": True, "label": "Password"},
                    "from_email": {"type": "string", "required": True, "label": "From Email"},
                    "use_tls": {"type": "boolean", "required": False, "default": True, "label": "Use TLS"},
                },
            },
            {
                "value": IntegrationType.DISCORD.value,
                "label": "Discord",
                "description": "Send messages to Discord channels via webhooks",
                "icon": "discord",
                "color": "#5865F2",
                "config_schema": {
                    "webhook_url": {"type": "string", "required": True, "label": "Webhook URL"},
                    "username": {"type": "string", "required": False, "label": "Bot Username"},
                    "avatar_url": {"type": "string", "required": False, "label": "Avatar URL"},
                },
            },
        ],
    }


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    db: DBSession,
    user: CurrentUser,
    integration_type: str | None = None,
    status: str | None = None,
) -> Any:
    """List integrations for the organization."""
    integrations = await IntegrationService.get_integrations(
        db=db,
        organization_id=user.organization_id,
        integration_type=integration_type,
        status=status,
    )
    
    return [
        {
            "id": i.id,
            "name": i.name,
            "integration_type": i.integration_type,
            "status": i.status,
            "status_message": i.status_message,
            "use_count": i.use_count,
            "success_count": i.success_count,
            "error_count": i.error_count,
            "success_rate": i.success_rate,
            "is_default": i.is_default,
            "last_used_at": i.last_used_at.isoformat() if i.last_used_at else None,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in integrations
    ]


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_integration(
    data: IntegrationCreateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Create a new integration.
    
    Supported types:
    - **slack**: Slack webhooks
    - **email_smtp**: SMTP email
    - **discord**: Discord webhooks
    """
    # Validate integration type
    if data.integration_type not in [t.value for t in IntegrationType]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid integration type. Use: {', '.join(t.value for t in IntegrationType)}",
        )
    
    # Create integration
    integration = Integration(
        name=data.name,
        integration_type=data.integration_type,
        organization_id=user.organization_id,
        created_by=user.id,
        configuration=data.configuration,
        settings=data.settings,
        is_default=data.is_default,
        status=IntegrationStatus.PENDING.value,
    )
    
    db.add(integration)
    await db.commit()
    await db.refresh(integration)
    
    logger.info(
        "Integration created",
        integration_id=str(integration.id),
        integration_type=data.integration_type,
        user_id=str(user.id),
    )
    
    return {
        "id": integration.id,
        "name": integration.name,
        "integration_type": integration.integration_type,
        "status": integration.status,
        "status_message": integration.status_message,
        "use_count": integration.use_count,
        "success_count": integration.success_count,
        "error_count": integration.error_count,
        "success_rate": integration.success_rate,
        "is_default": integration.is_default,
        "last_used_at": None,
        "created_at": integration.created_at.isoformat() if integration.created_at else None,
    }


@router.get("/{integration_id}", response_model=IntegrationDetailResponse)
async def get_integration(
    integration_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get integration details."""
    integration = await IntegrationService.get_integration_by_id(
        db=db,
        integration_id=integration_id,
        organization_id=user.organization_id,
    )
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    return {
        "id": integration.id,
        "name": integration.name,
        "integration_type": integration.integration_type,
        "status": integration.status,
        "status_message": integration.status_message,
        "use_count": integration.use_count,
        "success_count": integration.success_count,
        "error_count": integration.error_count,
        "success_rate": integration.success_rate,
        "is_default": integration.is_default,
        "last_used_at": integration.last_used_at.isoformat() if integration.last_used_at else None,
        "created_at": integration.created_at.isoformat() if integration.created_at else None,
        "configuration": integration.configuration,
        "settings": integration.settings,
    }


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: UUID,
    data: IntegrationUpdateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Update integration configuration."""
    integration = await IntegrationService.get_integration_by_id(
        db=db,
        integration_id=integration_id,
        organization_id=user.organization_id,
    )
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(integration, field, value)
    
    await db.commit()
    await db.refresh(integration)
    
    logger.info(
        "Integration updated",
        integration_id=str(integration.id),
        user_id=str(user.id),
    )
    
    return {
        "id": integration.id,
        "name": integration.name,
        "integration_type": integration.integration_type,
        "status": integration.status,
        "status_message": integration.status_message,
        "use_count": integration.use_count,
        "success_count": integration.success_count,
        "error_count": integration.error_count,
        "success_rate": integration.success_rate,
        "is_default": integration.is_default,
        "last_used_at": integration.last_used_at.isoformat() if integration.last_used_at else None,
        "created_at": integration.created_at.isoformat() if integration.created_at else None,
    }


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Delete an integration."""
    integration = await IntegrationService.get_integration_by_id(
        db=db,
        integration_id=integration_id,
        organization_id=user.organization_id,
    )
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    await db.delete(integration)
    await db.commit()
    
    logger.info(
        "Integration deleted",
        integration_id=str(integration_id),
        user_id=str(user.id),
    )
    
    return {"message": "Integration deleted successfully"}


@router.post("/{integration_id}/test", response_model=IntegrationTestResponse)
async def test_integration(
    integration_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Test integration connection.
    
    Sends a test message/payload to verify the integration works.
    """
    integration = await IntegrationService.get_integration_by_id(
        db=db,
        integration_id=integration_id,
        organization_id=user.organization_id,
    )
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    # Run test
    result = await IntegrationService.test_integration(integration)
    
    # Update status based on result
    integration.record_usage(
        success=result.get("success", False),
        message=result.get("error"),
    )
    await db.commit()
    
    return {
        "success": result.get("success", False),
        "message": "Test successful" if result.get("success") else f"Test failed: {result.get('error', 'Unknown error')}",
        "details": result,
    }


@router.post("/{integration_id}/execute", response_model=IntegrationExecuteResponse)
async def execute_integration(
    integration_id: UUID,
    data: IntegrationExecuteRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Manually execute an integration.
    
    Send a custom payload to the integration.
    """
    integration = await IntegrationService.get_integration_by_id(
        db=db,
        integration_id=integration_id,
        organization_id=user.organization_id,
    )
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    # Execute
    result = await IntegrationService.execute_integration(
        db=db,
        integration=integration,
        event_type=data.event_type,
        payload=data.payload,
    )
    
    await db.commit()
    
    return {
        "success": result.get("success", False),
        "message": "Integration executed successfully" if result.get("success") else f"Execution failed: {result.get('error', 'Unknown error')}",
        "duration_ms": result.get("duration_ms"),
    }


@router.get("/{integration_id}/logs")
async def get_integration_logs(
    integration_id: UUID,
    db: DBSession,
    user: CurrentUser,
    limit: int = 50,
) -> Any:
    """Get integration execution logs."""
    integration = await IntegrationService.get_integration_by_id(
        db=db,
        integration_id=integration_id,
        organization_id=user.organization_id,
    )
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    from sqlalchemy import select
    
    result = await db.execute(
        select(IntegrationLog)
        .where(IntegrationLog.integration_id == integration_id)
        .order_by(IntegrationLog.created_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return {
        "integration_id": str(integration_id),
        "total": len(logs),
        "logs": [
            {
                "id": str(log.id),
                "event_type": log.event_type,
                "status": log.status,
                "status_code": log.status_code,
                "error_message": log.error_message,
                "duration_ms": log.duration_ms,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }
