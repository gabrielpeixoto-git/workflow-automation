"""Webhook configuration API routes."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.core.deps import CurrentUser, DBSession, RequireWorkflowEdit
from app.core.logging_config import get_logger
from app.models.webhook_config import WebhookAuthType, WebhookConfig, WebhookDeliveryHistory
from app.services.webhook_enhanced_service import EnhancedWebhookService, WebhookDeliveryStatus

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook-configs", tags=["webhook-configs"])
webhook_service = EnhancedWebhookService()


# Request/Response Schemas

class WebhookConfigCreateRequest(BaseModel):
    """Create webhook configuration request."""
    
    workflow_id: UUID = Field(..., description="Associated workflow ID")
    target_url: HttpUrl = Field(..., description="Target webhook URL")
    
    # Retry settings
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delays: list[int] = Field(default=[1, 5, 15], max_length=5)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    
    # Headers and auth
    custom_headers: dict = Field(default={})
    auth_type: str = Field(default=WebhookAuthType.HMAC.value)
    auth_secret: str | None = Field(None, max_length=500)
    auth_config: dict = Field(default={})
    
    # Rate limiting
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    rate_limit_per_hour: int = Field(default=1000, ge=1, le=10000)
    
    # Filtering
    event_filter: list[str] = Field(default=[])


class WebhookConfigUpdateRequest(BaseModel):
    """Update webhook configuration request."""
    
    target_url: HttpUrl | None = None
    max_retries: int | None = Field(None, ge=0, le=10)
    retry_delays: list[int] | None = Field(None, max_length=5)
    timeout_seconds: int | None = Field(None, ge=1, le=300)
    custom_headers: dict | None = None
    auth_type: str | None = None
    auth_secret: str | None = Field(None, max_length=500)
    auth_config: dict | None = None
    rate_limit_per_minute: int | None = Field(None, ge=1, le=1000)
    rate_limit_per_hour: int | None = Field(None, ge=1, le=10000)
    event_filter: list[str] | None = None
    is_active: bool | None = None


class WebhookConfigResponse(BaseModel):
    """Webhook configuration response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_id: UUID
    target_url: str
    max_retries: int
    retry_delays: list[int]
    timeout_seconds: int
    auth_type: str
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    event_filter: list[str]
    is_active: bool
    success_count: int
    failure_count: int
    success_rate: float
    last_error: str | None
    last_status_code: int | None
    created_at: str


class WebhookTestRequest(BaseModel):
    """Test webhook request."""
    
    payload: dict = Field(default={"test": True, "message": "Hello from Automation Platform"})


class WebhookTestResponse(BaseModel):
    """Test webhook response."""
    
    success: bool
    delivery_id: UUID
    status: str
    attempts: int
    duration_ms: float
    message: str


@router.get("", response_model=list[WebhookConfigResponse])
async def list_webhook_configs(
    db: DBSession,
    user: CurrentUser,
    workflow_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
) -> Any:
    """List webhook configurations.
    
    Filter by workflow or active status.
    """
    from sqlalchemy import select
    
    query = select(WebhookConfig).where(
        WebhookConfig.organization_id == user.organization_id,
    )
    
    if workflow_id:
        query = query.where(WebhookConfig.workflow_id == workflow_id)
    
    if is_active is not None:
        query = query.where(WebhookConfig.is_active == is_active)
    
    query = query.order_by(WebhookConfig.created_at.desc())
    
    result = await db.execute(query)
    configs = result.scalars().all()
    
    return [
        {
            "id": c.id,
            "workflow_id": c.workflow_id,
            "target_url": c.target_url,
            "max_retries": c.max_retries,
            "retry_delays": c.retry_delays,
            "timeout_seconds": c.timeout_seconds,
            "auth_type": c.auth_type,
            "rate_limit_per_minute": c.rate_limit_per_minute,
            "rate_limit_per_hour": c.rate_limit_per_hour,
            "event_filter": c.event_filter or [],
            "is_active": c.is_active,
            "success_count": c.success_count,
            "failure_count": c.failure_count,
            "success_rate": c.success_rate,
            "last_error": c.last_error,
            "last_status_code": c.last_status_code,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in configs
    ]


@router.post("", response_model=WebhookConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_webhook_config(
    data: WebhookConfigCreateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Create a new webhook configuration.
    
    Configure advanced webhook settings including retries, timeouts,
    custom headers, and authentication.
    """
    # Verify workflow belongs to user
    from sqlalchemy import select
    from app.models.workflow import Workflow
    
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == data.workflow_id,
            Workflow.organization_id == user.organization_id,
        )
    )
    workflow = result.scalar_one_or_none()
    
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    # Create config
    config = WebhookConfig(
        workflow_id=data.workflow_id,
        organization_id=user.organization_id,
        target_url=str(data.target_url),
        max_retries=data.max_retries,
        retry_delays=data.retry_delays,
        timeout_seconds=data.timeout_seconds,
        custom_headers=data.custom_headers,
        auth_type=data.auth_type,
        auth_secret=data.auth_secret,
        auth_config=data.auth_config,
        rate_limit_per_minute=data.rate_limit_per_minute,
        rate_limit_per_hour=data.rate_limit_per_hour,
        event_filter=data.event_filter,
        is_active=True,
    )
    
    db.add(config)
    await db.commit()
    await db.refresh(config)
    
    logger.info(
        "Webhook config created",
        config_id=str(config.id),
        workflow_id=str(data.workflow_id),
        user_id=str(user.id),
    )
    
    return {
        "id": config.id,
        "workflow_id": config.workflow_id,
        "target_url": config.target_url,
        "max_retries": config.max_retries,
        "retry_delays": config.retry_delays,
        "timeout_seconds": config.timeout_seconds,
        "auth_type": config.auth_type,
        "rate_limit_per_minute": config.rate_limit_per_minute,
        "rate_limit_per_hour": config.rate_limit_per_hour,
        "event_filter": config.event_filter or [],
        "is_active": config.is_active,
        "success_count": config.success_count,
        "failure_count": config.failure_count,
        "success_rate": config.success_rate,
        "last_error": config.last_error,
        "last_status_code": config.last_status_code,
        "created_at": config.created_at.isoformat() if config.created_at else None,
    }


@router.get("/{config_id}", response_model=WebhookConfigResponse)
async def get_webhook_config(
    config_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get webhook configuration details."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == config_id,
            WebhookConfig.organization_id == user.organization_id,
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook configuration not found",
        )
    
    return {
        "id": config.id,
        "workflow_id": config.workflow_id,
        "target_url": config.target_url,
        "max_retries": config.max_retries,
        "retry_delays": config.retry_delays,
        "timeout_seconds": config.timeout_seconds,
        "auth_type": config.auth_type,
        "rate_limit_per_minute": config.rate_limit_per_minute,
        "rate_limit_per_hour": config.rate_limit_per_hour,
        "event_filter": config.event_filter or [],
        "is_active": config.is_active,
        "success_count": config.success_count,
        "failure_count": config.failure_count,
        "success_rate": config.success_rate,
        "last_error": config.last_error,
        "last_status_code": config.last_status_code,
        "created_at": config.created_at.isoformat() if config.created_at else None,
    }


@router.put("/{config_id}", response_model=WebhookConfigResponse)
async def update_webhook_config(
    config_id: UUID,
    data: WebhookConfigUpdateRequest,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Update webhook configuration."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == config_id,
            WebhookConfig.organization_id == user.organization_id,
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook configuration not found",
        )
    
    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    if "target_url" in update_data and update_data["target_url"]:
        update_data["target_url"] = str(update_data["target_url"])
    
    for field, value in update_data.items():
        setattr(config, field, value)
    
    await db.commit()
    await db.refresh(config)
    
    logger.info(
        "Webhook config updated",
        config_id=str(config.id),
        user_id=str(user.id),
    )
    
    return {
        "id": config.id,
        "workflow_id": config.workflow_id,
        "target_url": config.target_url,
        "max_retries": config.max_retries,
        "retry_delays": config.retry_delays,
        "timeout_seconds": config.timeout_seconds,
        "auth_type": config.auth_type,
        "rate_limit_per_minute": config.rate_limit_per_minute,
        "rate_limit_per_hour": config.rate_limit_per_hour,
        "event_filter": config.event_filter or [],
        "is_active": config.is_active,
        "success_count": config.success_count,
        "failure_count": config.failure_count,
        "success_rate": config.success_rate,
        "last_error": config.last_error,
        "last_status_code": config.last_status_code,
        "created_at": config.created_at.isoformat() if config.created_at else None,
    }


@router.delete("/{config_id}")
async def delete_webhook_config(
    config_id: UUID,
    db: DBSession,
    user: RequireWorkflowEdit,
) -> Any:
    """Delete webhook configuration."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == config_id,
            WebhookConfig.organization_id == user.organization_id,
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook configuration not found",
        )
    
    await db.delete(config)
    await db.commit()
    
    logger.info(
        "Webhook config deleted",
        config_id=str(config_id),
        user_id=str(user.id),
    )
    
    return {"message": "Webhook configuration deleted"}


@router.post("/{config_id}/test", response_model=WebhookTestResponse)
async def test_webhook_config(
    config_id: UUID,
    data: WebhookTestRequest,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Test webhook configuration with a sample payload.
    
    Sends a test webhook and returns delivery details including
    retry attempts and response information.
    """
    from sqlalchemy import select
    
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == config_id,
            WebhookConfig.organization_id == user.organization_id,
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook configuration not found",
        )
    
    # Build custom headers
    headers = config.custom_headers.copy()
    
    # Add auth header based on type
    if config.auth_type == WebhookAuthType.BEARER.value and config.auth_secret:
        headers["Authorization"] = f"Bearer {config.auth_secret}"
    elif config.auth_type == WebhookAuthType.API_KEY.value and config.auth_config:
        key_name = config.auth_config.get("key_name", "X-API-Key")
        headers[key_name] = config.auth_secret
    
    # Send test webhook using enhanced service
    from app.services.webhook_enhanced_service import WebhookRetryConfig
    
    retry_config = WebhookRetryConfig(
        max_retries=config.max_retries,
        retry_delays=config.retry_delays,
        timeout=config.timeout_seconds,
    )
    
    delivery_log = await webhook_service.send_webhook(
        webhook_url=config.target_url,
        payload=data.payload,
        headers=headers if headers else None,
        secret=config.auth_secret if config.auth_type == WebhookAuthType.HMAC.value else None,
        retry_config=retry_config,
        webhook_id=str(config.id),
    )
    
    # Update config stats based on result
    if delivery_log.final_status == WebhookDeliveryStatus.SUCCESS:
        config.record_success()
    else:
        last_error = delivery_log.attempts[-1].error_message if delivery_log.attempts else "Unknown error"
        config.record_failure(
            error=last_error or "Delivery failed",
            status_code=delivery_log.attempts[-1].status_code if delivery_log.attempts else None,
        )
    
    await db.commit()
    
    return {
        "success": delivery_log.final_status == WebhookDeliveryStatus.SUCCESS,
        "delivery_id": delivery_log.delivery_id,
        "status": delivery_log.final_status.value,
        "attempts": len(delivery_log.attempts),
        "duration_ms": sum(a.duration_ms or 0 for a in delivery_log.attempts),
        "message": "Test webhook delivered successfully" if delivery_log.final_status == WebhookDeliveryStatus.SUCCESS else "Test webhook failed",
    }


@router.get("/{config_id}/delivery-history")
async def get_delivery_history(
    config_id: UUID,
    db: DBSession,
    user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """Get delivery history for a webhook configuration."""
    from sqlalchemy import select
    
    result = await db.execute(
        select(WebhookConfig).where(
            WebhookConfig.id == config_id,
            WebhookConfig.organization_id == user.organization_id,
        )
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook configuration not found",
        )
    
    # Get delivery history from database
    result = await db.execute(
        select(WebhookDeliveryHistory)
        .where(WebhookDeliveryHistory.webhook_config_id == config_id)
        .order_by(WebhookDeliveryHistory.created_at.desc())
        .limit(limit)
    )
    history = result.scalars().all()
    
    return {
        "webhook_config_id": str(config_id),
        "total_records": len(history),
        "history": [
            {
                "id": str(h.id),
                "event_type": h.event_type,
                "status": h.status,
                "status_code": h.status_code,
                "error_message": h.error_message,
                "attempts": h.attempts,
                "duration_ms": h.duration_ms,
                "created_at": h.created_at.isoformat() if h.created_at else None,
            }
            for h in history
        ],
    }


@router.get("/auth-types/list")
async def list_auth_types(
    user: CurrentUser,
) -> Any:
    """List available webhook authentication types."""
    return {
        "auth_types": [
            {
                "value": WebhookAuthType.NONE.value,
                "label": "No Authentication",
                "description": "No authentication required",
            },
            {
                "value": WebhookAuthType.HMAC.value,
                "label": "HMAC Signature",
                "description": "HMAC SHA256 signature in X-Webhook-Signature header",
            },
            {
                "value": WebhookAuthType.BASIC.value,
                "label": "Basic Auth",
                "description": "HTTP Basic Authentication",
            },
            {
                "value": WebhookAuthType.BEARER.value,
                "label": "Bearer Token",
                "description": "Bearer token in Authorization header",
            },
            {
                "value": WebhookAuthType.API_KEY.value,
                "label": "API Key",
                "description": "Custom API key header",
            },
        ],
    }
