"""Webhook configuration model for advanced settings."""

from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID as SQLUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WebhookAuthType(str, Enum):
    """Webhook authentication types."""
    
    NONE = "none"
    HMAC = "hmac"
    BASIC = "basic"
    BEARER = "bearer"
    API_KEY = "api_key"


class WebhookConfig(BaseModel):
    """Advanced webhook configuration.
    
    Allows per-webhook customization of:
    - Timeouts and retries
    - Custom headers
    - Authentication
    - Rate limiting
    """
    
    __tablename__ = "webhook_configs"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Link to workflow
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Target URL
    target_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    
    # Retry configuration
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delays: Mapped[list[int]] = mapped_column(
        JSONB,
        default=lambda: [1, 5, 15],
    )  # seconds between retries
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    
    # Custom headers (JSON format)
    custom_headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Authentication
    auth_type: Mapped[str] = mapped_column(
        String(20),
        default=WebhookAuthType.HMAC.value,
    )
    auth_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
    )  # Additional auth config (username, api_key_name, etc.)
    
    # Rate limiting
    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=1000)
    
    # Payload filtering
    event_filter: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
    )  # Only send for these event types
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Success/failure tracking
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    
    # Relationships
    workflow = relationship("Workflow", back_populates="webhook_configs")
    organization = relationship("Organization", back_populates="webhook_configs")
    delivery_history: Mapped[list["WebhookDeliveryHistory"]] = relationship(
        "WebhookDeliveryHistory",
        back_populates="webhook_config",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 100.0
        return (self.success_count / total) * 100
    
    def record_success(self) -> None:
        """Record successful delivery."""
        self.success_count += 1
        self.last_used_at = datetime.utcnow()
        self.last_error = None
    
    def record_failure(self, error: str, status_code: int | None = None) -> None:
        """Record failed delivery."""
        self.failure_count += 1
        self.last_used_at = datetime.utcnow()
        self.last_error = error
        self.last_status_code = status_code


class WebhookDeliveryHistory(BaseModel):
    """History of webhook deliveries."""
    
    __tablename__ = "webhook_delivery_history"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    webhook_config_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("webhook_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Delivery details
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timing
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    duration_ms: Mapped[float | None] = mapped_column(Integer, nullable=True)
    
    # Response (truncated)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    
    # Relationships
    webhook_config = relationship("WebhookConfig", back_populates="delivery_history")
    organization = relationship("Organization")
