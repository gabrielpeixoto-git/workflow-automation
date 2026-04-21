"""Workflow execution and execution log models."""

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.workflow import Workflow


class ExecutionStatus(str, enum.Enum):
    """Execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class StepStatus(str, enum.Enum):
    """Step execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowExecution(BaseModel):
    """Workflow execution instance."""

    __tablename__ = "workflow_executions"

    workflow_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    correlation_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        index=True,
    )

    # Status
    status: Mapped[ExecutionStatus] = mapped_column(
        String(20),
        default=ExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Trigger info
    trigger_type: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Celery task info
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )

    # Timing
    started_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Results
    output_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    workflow: Mapped["Workflow"] = relationship(
        "Workflow",
        back_populates="executions",
        lazy="joined",
    )
    step_logs: Mapped[list["ExecutionLog"]] = relationship(
        "ExecutionLog",
        back_populates="execution",
        lazy="selectin",
        order_by="ExecutionLog.step_order",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="execution",
        lazy="selectin",
    )
    schema_validation_logs: Mapped[list["SchemaValidationLog"]] = relationship(
        "SchemaValidationLog",
        back_populates="execution",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecution {self.correlation_id} {self.status}>"


class ExecutionLog(BaseModel):
    """Execution step log."""

    __tablename__ = "execution_logs"

    execution_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(String(255), nullable=False)
    step_type: Mapped[str] = mapped_column(String(20), nullable=False)

    # Status
    status: Mapped[StepStatus] = mapped_column(
        String(20),
        default=StepStatus.PENDING,
        nullable=False,
    )

    # Timing
    started_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Data
    input_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )
    output_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Error info
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Retry info
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    execution: Mapped["WorkflowExecution"] = relationship(
        "WorkflowExecution",
        back_populates="step_logs",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<ExecutionLog {self.step_name} {self.status}>"
