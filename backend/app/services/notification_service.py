"""Notification service for workflow alerts."""

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.notification import (
    Notification,
    NotificationConfig,
    NotificationStatus,
    NotificationType,
)
from app.models.workflow import Workflow
from app.services.actions import execute_email_action

logger = get_logger(__name__)


class NotificationService:
    """Service for sending notifications when workflows fail or complete."""

    @staticmethod
    async def get_or_create_config(
        db: AsyncSession,
        workflow_id: UUID,
        organization_id: UUID,
    ) -> NotificationConfig:
        """Get or create notification config for a workflow."""
        result = await db.execute(
            select(NotificationConfig).where(
                NotificationConfig.workflow_id == workflow_id,
            )
        )
        config = result.scalar_one_or_none()
        
        if not config:
            config = NotificationConfig(
                workflow_id=workflow_id,
                organization_id=organization_id,
                notify_on_failure=True,
                notify_on_success=False,
                email_recipients=[],
            )
            db.add(config)
            await db.commit()
            await db.refresh(config)
            logger.info(
                "Created notification config for workflow",
                extra={"workflow_id": str(workflow_id)}
            )
        
        return config

    @staticmethod
    async def update_config(
        db: AsyncSession,
        workflow_id: UUID,
        notify_on_failure: bool | None = None,
        notify_on_success: bool | None = None,
        notify_on_retry: bool | None = None,
        email_recipients: list[str] | None = None,
        slack_webhook_url: str | None = None,
        custom_webhook_url: str | None = None,
        cooldown_minutes: int | None = None,
    ) -> NotificationConfig:
        """Update notification configuration."""
        result = await db.execute(
            select(NotificationConfig).where(
                NotificationConfig.workflow_id == workflow_id,
            )
        )
        config = result.scalar_one_or_none()
        
        if not config:
            raise ValueError(f"Notification config not found for workflow {workflow_id}")
        
        if notify_on_failure is not None:
            config.notify_on_failure = notify_on_failure
        if notify_on_success is not None:
            config.notify_on_success = notify_on_success
        if notify_on_retry is not None:
            config.notify_on_retry = notify_on_retry
        if email_recipients is not None:
            config.email_recipients = email_recipients
        if slack_webhook_url is not None:
            config.slack_webhook_url = slack_webhook_url
        if custom_webhook_url is not None:
            config.custom_webhook_url = custom_webhook_url
        if cooldown_minutes is not None:
            config.cooldown_minutes = cooldown_minutes
        
        await db.commit()
        await db.refresh(config)
        
        logger.info(
            "Updated notification config",
            extra={"workflow_id": str(workflow_id)}
        )
        
        return config

    @staticmethod
    async def should_send_notification(
        db: AsyncSession,
        config: NotificationConfig,
        event_type: str,
    ) -> bool:
        """Check if notification should be sent based on config and cooldown."""
        # Check if notification type is enabled
        if event_type == "failure" and not config.notify_on_failure:
            return False
        if event_type == "success" and not config.notify_on_success:
            return False
        if event_type == "retry" and not config.notify_on_retry:
            return False
        
        # Check cooldown period
        if config.last_notification_at:
            cooldown_ends = config.last_notification_at + timedelta(
                minutes=config.cooldown_minutes
            )
            if datetime.utcnow() < cooldown_ends:
                logger.debug(
                    "Skipping notification due to cooldown",
                    extra={
                        "workflow_id": str(config.workflow_id),
                        "cooldown_until": cooldown_ends.isoformat(),
                    }
                )
                return False
        
        return True

    @staticmethod
    async def send_failure_notification(
        db: AsyncSession,
        workflow: Workflow,
        execution_id: UUID,
        error_message: str,
        recipient_email: str,
    ) -> Notification:
        """Send email notification for workflow failure."""
        # Create notification record
        notification = Notification(
            workflow_id=workflow.id,
            execution_id=execution_id,
            organization_id=workflow.organization_id,
            notification_type=NotificationType.EMAIL,
            status=NotificationStatus.PENDING,
            subject=f"❌ Workflow Falhou: {workflow.name}",
            message=NotificationService._format_failure_message(
                workflow, error_message
            ),
            recipient=recipient_email,
            event_type="failure",
            event_data={
                "workflow_name": workflow.name,
                "workflow_slug": workflow.slug,
                "error_message": error_message,
                "execution_id": str(execution_id),
            },
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)
        
        # Try to send email
        try:
            await execute_email_action(
                to=recipient_email,
                subject=notification.subject,
                body=notification.message,
                cc=None,
                bcc=None,
            )
            
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            await db.commit()
            
            logger.info(
                "Failure notification sent",
                extra={
                    "notification_id": str(notification.id),
                    "workflow_id": str(workflow.id),
                    "recipient": recipient_email,
                }
            )
            
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            await db.commit()
            
            logger.error(
                "Failed to send notification",
                extra={
                    "notification_id": str(notification.id),
                    "error": str(e),
                }
            )
        
        return notification

    @staticmethod
    async def notify_workflow_failure(
        db: AsyncSession,
        workflow: Workflow,
        execution_id: UUID,
        error_message: str,
    ) -> list[Notification]:
        """Send notifications to all configured recipients when workflow fails."""
        config = await NotificationService.get_or_create_config(
            db, workflow.id, workflow.organization_id
        )
        
        # Check if we should send notification
        if not await NotificationService.should_send_notification(db, config, "failure"):
            logger.debug(
                "Skipping failure notification",
                extra={"workflow_id": str(workflow.id)}
            )
            return []
        
        notifications = []
        
        # Send to configured email recipients
        for email in config.email_recipients:
            try:
                notification = await NotificationService.send_failure_notification(
                    db, workflow, execution_id, error_message, email
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(
                    "Error sending notification",
                    extra={
                        "workflow_id": str(workflow.id),
                        "recipient": email,
                        "error": str(e),
                    }
                )
        
        # Update last notification time
        if notifications:
            config.last_notification_at = datetime.utcnow()
            await db.commit()
        
        return notifications

    @staticmethod
    def _format_failure_message(workflow: Workflow, error_message: str) -> str:
        """Format email message for workflow failure."""
        return f"""
Olá,

O workflow "{workflow.name}" falhou durante a execução.

📋 **Detalhes do Workflow:**
- Nome: {workflow.name}
- Slug: {workflow.slug}
- Status: Falhou

❌ **Erro:**
{error_message}

🔧 **Ações Recomendadas:**
1. Verifique os logs da execução
2. Revise a configuração do workflow
3. Verifique se as dependências externas estão funcionando

Acesse o painel para mais detalhes:
http://localhost:8000/executions

---
Workflow Automation Platform
        """.strip()

    @staticmethod
    async def get_notifications(
        db: AsyncSession,
        organization_id: UUID,
        workflow_id: UUID | None = None,
        status: NotificationStatus | None = None,
        limit: int = 50,
    ) -> list[Notification]:
        """Get notification history."""
        query = select(Notification).where(
            Notification.organization_id == organization_id
        )
        
        if workflow_id:
            query = query.where(Notification.workflow_id == workflow_id)
        if status:
            query = query.where(Notification.status == status)
        
        query = query.order_by(Notification.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return list(result.scalars().all())
