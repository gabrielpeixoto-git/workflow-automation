"""User model."""

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.audit_log import AuditLog
    from app.models.organization import Organization


class UserRole(str, enum.Enum):
    """User roles."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(BaseModel):
    """User account model."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_user_email"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        String(20),
        default=UserRole.VIEWER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Multi-tenant
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users",
        lazy="joined",
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="selectin",
    )
    workflow_versions: Mapped[list["WorkflowVersion"]] = relationship(
        "WorkflowVersion",
        back_populates="creator",
        lazy="selectin",
    )
    created_api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey",
        foreign_keys="APIKey.created_by",
        back_populates="creator",
        lazy="selectin",
    )
    created_templates: Mapped[list["WorkflowTemplate"]] = relationship(
        "WorkflowTemplate",
        foreign_keys="WorkflowTemplate.created_by",
        back_populates="creator",
        lazy="selectin",
    )
    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        foreign_keys="Integration.created_by",
        back_populates="creator",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"
