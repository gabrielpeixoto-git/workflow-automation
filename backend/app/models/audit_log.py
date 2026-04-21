"""Audit log model for tracking all system actions."""

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class AuditAction(str, enum.Enum):
    """Audit action types."""

    # Auth
    LOGIN = "login"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    TOKEN_REFRESH = "token_refresh"

    # User management
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"

    # Organization
    ORG_CREATE = "org_create"
    ORG_UPDATE = "org_update"
    ORG_DELETE = "org_delete"

    # Workflow
    WORKFLOW_CREATE = "workflow_create"
    WORKFLOW_UPDATE = "workflow_update"
    WORKFLOW_DELETE = "workflow_delete"
    WORKFLOW_ACTIVATE = "workflow_activate"
    WORKFLOW_DEACTIVATE = "workflow_deactivate"
    WORKFLOW_DUPLICATE = "workflow_duplicate"

    # Execution
    EXECUTION_START = "execution_start"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_FAIL = "execution_fail"
    EXECUTION_RETRY = "execution_retry"
    EXECUTION_CANCEL = "execution_cancel"

    # File
    FILE_UPLOAD = "file_upload"
    FILE_DELETE = "file_delete"

    # Webhook
    WEBHOOK_TRIGGER = "webhook_trigger"


class AuditLog(BaseModel):
    """Audit log entry."""

    __tablename__ = "audit_logs"

    # Actor
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # Action
    action: Mapped[AuditAction] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    # Details
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
        nullable=True,
    )

    # Request context
    ip_address: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Multi-tenant
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Relationships
    user: Mapped["User | None"] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="joined",
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_email}>"
