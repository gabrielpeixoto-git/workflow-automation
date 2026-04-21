"""Organization/Workspace model."""

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.notification import Notification, NotificationConfig
    from app.models.user import User
    from app.models.workflow import Workflow


class Organization(BaseModel):
    """Organization/Workspace for multi-tenancy."""

    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organization_slug"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        lazy="selectin",
    )
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow",
        back_populates="organization",
        lazy="selectin",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="organization",
        lazy="selectin",
    )
    notification_configs: Mapped[list["NotificationConfig"]] = relationship(
        "NotificationConfig",
        back_populates="organization",
        lazy="selectin",
    )
    schemas: Mapped[list["WorkflowSchema"]] = relationship(
        "WorkflowSchema",
        back_populates="organization",
        lazy="selectin",
    )
    schema_validation_logs: Mapped[list["SchemaValidationLog"]] = relationship(
        "SchemaValidationLog",
        back_populates="organization",
        lazy="selectin",
    )
    workflow_versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion",
        back_populates="organization",
        lazy="selectin",
    )
    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        back_populates="organization",
        lazy="selectin",
    )
    api_key_usage_logs: Mapped[list["APIKeyUsageLog"]] = relationship(
        "APIKeyUsageLog",
        back_populates="organization",
        lazy="selectin",
    )
    templates: Mapped[list["WorkflowTemplate"]] = relationship(
        "WorkflowTemplate",
        back_populates="organization",
        lazy="selectin",
    )
    webhook_configs: Mapped[list["WebhookConfig"]] = relationship(
        "WebhookConfig",
        back_populates="organization",
        lazy="selectin",
    )
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        back_populates="organization",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"
