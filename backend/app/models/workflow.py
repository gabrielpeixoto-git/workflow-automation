"""Workflow and WorkflowStep models."""

import enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.execution import WorkflowExecution
    from app.models.notification import Notification, NotificationConfig
    from app.models.organization import Organization


class WorkflowStatus(str, enum.Enum):
    """Workflow status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"
    ARCHIVED = "archived"


class StepType(str, enum.Enum):
    """Step types."""

    TRIGGER = "trigger"
    ACTION = "action"


class TriggerType(str, enum.Enum):
    """Trigger types."""

    WEBHOOK = "webhook"
    SCHEDULED = "scheduled"
    MANUAL = "manual"
    FILE_UPLOAD = "file_upload"


class ActionType(str, enum.Enum):
    """Action types."""

    HTTP_REQUEST = "http_request"
    SEND_EMAIL = "send_email"
    WRITE_DATABASE = "write_database"
    TRANSFORM_PAYLOAD = "transform_payload"
    EXPORT_CSV = "export_csv"
    EXPORT_PDF = "export_pdf"
    NOTIFY = "notify"
    SEND_SLACK = "send_slack"
    SEND_DISCORD = "send_discord"


class Workflow(BaseModel):
    """Workflow definition model."""

    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "slug",
            name="uq_workflow_org_slug"
        ),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[WorkflowStatus] = mapped_column(
        String(20),
        default=WorkflowStatus.DRAFT,
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[str] = mapped_column(
        String(30),
        default="manual",
        nullable=False,
        index=True,
    )
    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Multi-tenant
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="workflows",
        lazy="joined",
    )
    steps: Mapped[list["WorkflowStep"]] = relationship(
        "WorkflowStep",
        back_populates="workflow",
        lazy="selectin",
        order_by="WorkflowStep.order",
        cascade="all, delete-orphan",
    )
    executions: Mapped[list["WorkflowExecution"]] = relationship(
        "WorkflowExecution",
        back_populates="workflow",
        lazy="selectin",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    notification_config: Mapped["NotificationConfig"] = relationship(
        "NotificationConfig",
        back_populates="workflow",
        lazy="joined",
        uselist=False,
        cascade="all, delete-orphan",
    )
    schemas: Mapped[list["WorkflowSchema"]] = relationship(
        "WorkflowSchema",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    schema_validation_logs: Mapped[list["SchemaValidationLog"]] = relationship(
        "SchemaValidationLog",
        back_populates="workflow",
        lazy="selectin",
    )
    versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion",
        back_populates="workflow",
        lazy="selectin",
        order_by="WorkflowVersion.version_number.desc()",
        cascade="all, delete-orphan",
    )
    webhook_configs: Mapped[list["WebhookConfig"]] = relationship(
        "WebhookConfig",
        back_populates="workflow",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Workflow {self.slug} v{self.version}>"


class WorkflowStep(BaseModel):
    """Workflow step (trigger or action)."""

    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id", "order",
            name="uq_step_workflow_order"
        ),
    )

    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[StepType] = mapped_column(String(20), nullable=False)

    # Trigger or Action specific
    trigger_type: Mapped[TriggerType | None] = mapped_column(
        String(30),
        nullable=True,
    )
    action_type: Mapped[ActionType | None] = mapped_column(
        String(30),
        nullable=True,
    )

    # Configuration
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Retry configuration
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_delay: Mapped[int] = mapped_column(Integer, default=60, nullable=False)  # seconds

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow",
        back_populates="steps",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<WorkflowStep {self.name} ({self.step_type})>"
