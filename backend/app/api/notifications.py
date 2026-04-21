"""Notification API routes."""

from datetime import datetime
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.api.schemas import NotificationConfigUpdate
from app.core.deps import CurrentUser, DBSession, RequireAdmin
from app.core.logging_config import get_logger
from app.models.notification import Notification, NotificationConfig, NotificationStatus
from app.services.notification_service import NotificationService

logger = get_logger(__name__)
router = APIRouter()


# Response schemas defined locally to avoid circular imports
class NotificationResponse(BaseModel):
    """Notification response schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_id: UUID
    execution_id: UUID | None
    notification_type: str
    status: str
    subject: str
    recipient: str
    event_type: str
    sent_at: datetime | None
    error_message: str | None
    created_at: datetime


class NotificationConfigResponse(BaseModel):
    """Notification config response schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    workflow_id: UUID
    notify_on_failure: bool
    notify_on_success: bool
    notify_on_retry: bool
    email_recipients: List[str]
    slack_webhook_url: str | None
    custom_webhook_url: str | None
    cooldown_minutes: int
    last_notification_at: datetime | None
    created_at: datetime
    updated_at: datetime


@router.get("/notifications", response_model=list[NotificationResponse])
async def list_notifications(
    db: DBSession,
    user: CurrentUser,
    workflow_id: UUID | None = Query(None, description="Filter by workflow ID"),
    status: NotificationStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
) -> Any:
    """List notification history for the current user's organization.
    
    Returns a list of notifications sent for workflow failures and other events.
    """
    notifications = await NotificationService.get_notifications(
        db=db,
        organization_id=user.organization_id,
        workflow_id=workflow_id,
        status=status,
        limit=limit,
    )
    
    return [
        {
            "id": n.id,
            "workflow_id": n.workflow_id,
            "execution_id": n.execution_id,
            "notification_type": n.notification_type.value,
            "status": n.status.value,
            "subject": n.subject,
            "recipient": n.recipient,
            "event_type": n.event_type,
            "sent_at": n.sent_at,
            "error_message": n.error_message,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


@router.get("/workflows/{workflow_id}/notifications/config", response_model=NotificationConfigResponse)
async def get_notification_config(
    workflow_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get notification configuration for a workflow.
    
    Returns the current notification settings including:
    - Whether to notify on failure/success/retry
    - Email recipients
    - Cooldown settings
    """
    # Verify workflow belongs to user's organization
    from app.models.workflow import Workflow
    
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
    
    config = await NotificationService.get_or_create_config(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    
    return {
        "id": config.id,
        "workflow_id": config.workflow_id,
        "notify_on_failure": config.notify_on_failure,
        "notify_on_success": config.notify_on_success,
        "notify_on_retry": config.notify_on_retry,
        "email_recipients": config.email_recipients,
        "slack_webhook_url": config.slack_webhook_url,
        "custom_webhook_url": config.custom_webhook_url,
        "cooldown_minutes": config.cooldown_minutes,
        "last_notification_at": config.last_notification_at,
        "created_at": config.created_at,
        "updated_at": config.updated_at,
    }


@router.put("/workflows/{workflow_id}/notifications/config", response_model=NotificationConfigResponse)
async def update_notification_config(
    workflow_id: UUID,
    data: NotificationConfigUpdate,
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Update notification configuration for a workflow.
    
    Allows configuring:
    - Email notifications on failure/success/retry
    - List of email recipients
    - Cooldown period between notifications
    - Slack webhook (future)
    - Custom webhook URL (future)
    """
    # Verify workflow belongs to user's organization
    from app.models.workflow import Workflow
    
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
        config = await NotificationService.update_config(
            db=db,
            workflow_id=workflow_id,
            notify_on_failure=data.notify_on_failure,
            notify_on_success=data.notify_on_success,
            notify_on_retry=data.notify_on_retry,
            email_recipients=data.email_recipients,
            slack_webhook_url=data.slack_webhook_url,
            custom_webhook_url=data.custom_webhook_url,
            cooldown_minutes=data.cooldown_minutes,
        )
        
        logger.info(
            "Notification config updated",
            extra={
                "workflow_id": str(workflow_id),
                "user_id": str(user.id),
            }
        )
        
        return {
            "id": config.id,
            "workflow_id": config.workflow_id,
            "notify_on_failure": config.notify_on_failure,
            "notify_on_success": config.notify_on_success,
            "notify_on_retry": config.notify_on_retry,
            "email_recipients": config.email_recipients,
            "slack_webhook_url": config.slack_webhook_url,
            "custom_webhook_url": config.custom_webhook_url,
            "cooldown_minutes": config.cooldown_minutes,
            "last_notification_at": config.last_notification_at,
            "created_at": config.created_at,
            "updated_at": config.updated_at,
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.post("/workflows/{workflow_id}/notifications/test")
async def test_notification(
    workflow_id: UUID,
    db: DBSession,
    user: CurrentUser,
) -> dict:
    """Send a test notification to verify configuration.
    
    This endpoint sends a test email to all configured recipients
    to verify the notification system is working correctly.
    """
    from app.models.workflow import Workflow
    
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
    
    config = await NotificationService.get_or_create_config(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    
    if not config.email_recipients:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email recipients configured",
        )
    
    # Send test notification
    try:
        from app.services.actions import execute_email_action
        
        test_notifications = []
        for email in config.email_recipients:
            notification = await NotificationService.send_failure_notification(
                db=db,
                workflow=workflow,
                execution_id=workflow_id,  # Using workflow_id as placeholder
                error_message="This is a TEST notification to verify your email configuration.",
                recipient_email=email,
            )
            test_notifications.append(notification)
        
        return {
            "message": "Test notifications sent",
            "recipients": config.email_recipients,
            "notification_ids": [str(n.id) for n in test_notifications],
        }
        
    except Exception as e:
        logger.error(
            "Failed to send test notification",
            extra={
                "workflow_id": str(workflow_id),
                "error": str(e),
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}",
        )
