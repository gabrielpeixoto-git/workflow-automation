"""Workflow versioning models."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WorkflowVersion(BaseModel):
    """Workflow version history.
    
    Stores historical versions of workflows for audit and rollback purposes.
    """
    
    __tablename__ = "workflow_versions"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
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
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    
    # Version info
    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    version_tag: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )
    change_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    # Workflow snapshot
    workflow_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    steps_data: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    
    # Change tracking
    previous_version_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_versions.id"),
        nullable=True,
    )
    is_restored: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    
    # Relationships
    workflow = relationship("Workflow", back_populates="versions")
    organization = relationship("Organization", back_populates="workflow_versions")
    creator = relationship("User", back_populates="workflow_versions")
    previous_version = relationship("WorkflowVersion", remote_side=[id])
    diffs_from = relationship(
        "WorkflowDiff",
        foreign_keys="WorkflowDiff.from_version_id",
        back_populates="from_version",
    )
    diffs_to = relationship(
        "WorkflowDiff",
        foreign_keys="WorkflowDiff.to_version_id",
        back_populates="to_version",
    )


class WorkflowDiff(BaseModel):
    """Store diffs between workflow versions.
    
    Pre-computed diffs for quick comparison between versions.
    """
    
    __tablename__ = "workflow_diffs"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    from_version_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_version_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Diff data
    workflow_changes: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    steps_added: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    steps_removed: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    steps_modified: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )
    
    # Metadata
    total_changes: Mapped[int] = mapped_column(Integer, default=0)
    is_major_change: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    
    # Relationships
    from_version = relationship(
        "WorkflowVersion",
        foreign_keys=[from_version_id],
        back_populates="diffs_from",
    )
    to_version = relationship(
        "WorkflowVersion",
        foreign_keys=[to_version_id],
        back_populates="diffs_to",
    )
