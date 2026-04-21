"""Workflow templates model."""

from enum import Enum
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID as SQLUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class TemplateCategory(str, Enum):
    """Template categories."""
    
    AUTOMATION = "automation"
    NOTIFICATION = "notification"
    DATA_PROCESSING = "data_processing"
    INTEGRATION = "integration"
    CUSTOM = "custom"


class WorkflowTemplate(BaseModel):
    """Predefined workflow template.
    
    Allows users to quickly create workflows based on common patterns.
    """
    
    __tablename__ = "workflow_templates"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    # Template metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(
        String(50),
        default=TemplateCategory.AUTOMATION.value,
        nullable=False,
    )
    
    # Template content
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    steps_configuration: Mapped[list] = mapped_column(JSONB, default=list)
    default_configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Template settings
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Organization (null for global templates)
    organization_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Tags for categorization
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    
    # Icon/Color for UI
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color
    
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
    organization = relationship("Organization", back_populates="templates")
    creator = relationship("User", back_populates="created_templates")
    
    def record_usage(self) -> None:
        """Record template usage."""
        self.usage_count += 1
        self.updated_at = datetime.utcnow()


class WorkflowTemplateUsage(BaseModel):
    """Track template usage by users."""
    
    __tablename__ = "workflow_template_usages"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    template_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Customizations made
    customizations: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    
    # Relationships
    template = relationship("WorkflowTemplate")
    organization = relationship("Organization")
    user = relationship("User")
    workflow = relationship("Workflow")
