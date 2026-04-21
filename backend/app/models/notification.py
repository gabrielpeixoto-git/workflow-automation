"""Notification models for workflow alerts."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NotificationType(str, Enum):
    """Types of notifications."""
    
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    SMS = "sms"


class NotificationStatus(str, Enum):
    """Status of notification delivery."""
    
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRYING = "retrying"


class Notification(BaseModel):
    """Notification model for workflow alerts.
    
    Stores all notifications sent when workflows fail or complete.
    """
    
    __tablename__ = "notifications"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Relationships
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    execution_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Notification content
    notification_type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType),
        nullable=False,
        default=NotificationType.EMAIL,
    )
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus),
        nullable=False,
        default=NotificationStatus.PENDING,
    )
    
    # Content
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    event_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    
    # Delivery tracking
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    # Relationships
    workflow = relationship("Workflow", back_populates="notifications")
    execution = relationship("WorkflowExecution", back_populates="notifications")
    organization = relationship("Organization", back_populates="notifications")


class NotificationConfig(BaseModel):
    """Notification configuration per workflow.
    
    Allows users to configure which events trigger notifications
    and where to send them.
    """
    
    __tablename__ = "notification_configs"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Relationships
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Notification settings
    notify_on_failure: Mapped[bool] = mapped_column(default=True)
    notify_on_success: Mapped[bool] = mapped_column(default=False)
    notify_on_retry: Mapped[bool] = mapped_column(default=True)
    
    # Recipients
    email_recipients: Mapped[list[str]] = mapped_column(JSONB, default=list)
    slack_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Cooldown (minimum minutes between notifications)
    cooldown_minutes: Mapped[int] = mapped_column(default=15)
    last_notification_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    
    # Relationships
    workflow = relationship("Workflow", back_populates="notification_config")
    organization = relationship("Organization", back_populates="notification_configs")
