"""JSON Schema validation models."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID as SQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class SchemaType(str, Enum):
    """Types of schema validation."""
    
    JSON_SCHEMA = "json_schema"  # JSON Schema (draft-07)
    JSON_LOGIC = "json_logic"      # JSON Logic rules
    REGEX = "regex"              # Regular expression patterns
    CUSTOM = "custom"            # Custom validation rules


class SchemaStatus(str, Enum):
    """Status of schema validation."""
    
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class ValidationResult(str, Enum):
    """Result of schema validation."""
    
    VALID = "valid"
    INVALID = "invalid"
    ERROR = "error"


class WorkflowSchema(BaseModel):
    """JSON Schema for workflow payload validation.
    
    Allows users to define validation rules for webhook payloads,
    ensuring data integrity before workflow execution.
    """
    
    __tablename__ = "workflow_schemas"
    
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
    
    # Schema metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_type: Mapped[SchemaType] = mapped_column(
        SQLEnum(SchemaType),
        default=SchemaType.JSON_SCHEMA,
        nullable=False,
    )
    status: Mapped[SchemaStatus] = mapped_column(
        SQLEnum(SchemaStatus),
        default=SchemaStatus.ACTIVE,
        nullable=False,
    )
    
    # Schema definition (JSON Schema, JSON Logic, or custom rules)
    schema_definition: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    
    # Validation settings
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    fail_on_error: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message_template: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default="Validation failed: {error}",
    )
    
    # Versioning
    version: Mapped[int] = mapped_column(default=1)
    previous_version_id: Mapped[UUID | None] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_schemas.id"),
        nullable=True,
    )
    
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
    workflow = relationship("Workflow", back_populates="schemas")
    organization = relationship("Organization", back_populates="schemas")
    previous_version = relationship("WorkflowSchema", remote_side=[id])
    validation_logs = relationship(
        "SchemaValidationLog",
        back_populates="schema",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )


class SchemaValidationLog(BaseModel):
    """Log of schema validation attempts.
    
    Tracks all validation attempts for auditing and debugging.
    """
    
    __tablename__ = "schema_validation_logs"
    
    id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    schema_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("workflow_schemas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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
    )
    organization_id: Mapped[UUID] = mapped_column(
        SQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Validation details
    result: Mapped[ValidationResult] = mapped_column(
        SQLEnum(ValidationResult),
        nullable=False,
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Timing
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    validation_duration_ms: Mapped[float | None] = mapped_column(
        nullable=True,
    )
    
    # Relationships
    schema = relationship("WorkflowSchema", back_populates="validation_logs")
    workflow = relationship("Workflow", back_populates="schema_validation_logs")
    execution = relationship("WorkflowExecution", back_populates="schema_validation_logs")
    organization = relationship("Organization", back_populates="schema_validation_logs")
