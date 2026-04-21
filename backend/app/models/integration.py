"""Integration models for external services."""

from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID as SQLUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class IntegrationType(str, Enum):
    """Available integration types."""
    
    SLACK = "slack"
    EMAIL_SMTP = "email_smtp"
    DISCORD = "discord"


class IntegrationStatus(str, Enum):
    """Integration connection status."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"


class Integration(BaseModel):
    """External service integration configuration.
    
    Supports Slack, Email (SMTP), Discord, and other services.
    """
    
    __tablename__ = "integrations"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Integration metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    integration_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    
    # Organization
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Configuration (encrypted sensitive data)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Settings (non-sensitive)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20),
        default=IntegrationStatus.PENDING.value,
    )
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Usage tracking
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Default settings for this integration
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    
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
    organization = relationship("Organization", back_populates="integrations")
    creator = relationship("User", back_populates="integrations")
    logs: Mapped[list["IntegrationLog"]] = relationship(
        "IntegrationLog",
        back_populates="integration",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="IntegrationLog.created_at.desc()",
    )
    
    def record_usage(self, success: bool = True, message: str | None = None) -> None:
        """Record integration usage."""
        self.last_used_at = datetime.utcnow()
        self.use_count += 1
        
        if success:
            self.success_count += 1
            if self.status != IntegrationStatus.ACTIVE.value:
                self.status = IntegrationStatus.ACTIVE.value
                self.status_message = None
        else:
            self.error_count += 1
            self.status = IntegrationStatus.ERROR.value
            self.status_message = message or "Integration failed"
        
        self.updated_at = datetime.utcnow()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.use_count == 0:
            return 100.0
        return (self.success_count / self.use_count) * 100


class IntegrationLog(BaseModel):
    """Log of integration usage."""
    
    __tablename__ = "integration_logs"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    integration_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("integrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # success, failed
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Timing
    duration_ms: Mapped[float | None] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    
    # Relationships
    integration = relationship("Integration", back_populates="logs")
    organization = relationship("Organization")
