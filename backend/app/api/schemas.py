"""Pydantic schemas for API.

This module defines all Pydantic models used for request/validation
in the Workflow Automation API.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ============== Base Schemas ==============

class BaseSchema(BaseModel):
    """Base schema with common configuration.

    All schemas inherit from this class to ensure consistent
    behavior across the API.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_schema_extra={"examples": []},
    )


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields.

    Automatically includes id, created_at and updated_at fields.
    """

    id: UUID = Field(
        ..., 
        description="Unique identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    created_at: datetime = Field(
        ..., 
        description="When the record was created",
        examples=["2024-01-15T10:30:00Z"]
    )
    updated_at: datetime = Field(
        ..., 
        description="When the record was last updated",
        examples=["2024-01-15T10:30:00Z"]
    )


# ============== Auth Schemas ==============

class UserLogin(BaseSchema):
    """User login request schema.

    Used to authenticate a user and receive access/refresh tokens.
    """

    email: EmailStr = Field(
        ..., 
        description="User email address",
        examples=["admin@example.com"]
    )
    password: str = Field(
        ..., 
        min_length=6,
        description="User password (minimum 6 characters)",
        examples=["admin123"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin@example.com",
                "password": "admin123"
            }
        }
    )


class UserRegister(BaseSchema):
    """User registration request schema.

    Creates a new user account with an associated organization.
    """

    email: EmailStr = Field(
        ..., 
        description="User email address (must be unique)",
        examples=["newuser@example.com"]
    )
    password: str = Field(
        ..., 
        min_length=8,
        description="User password (minimum 8 characters)",
        examples=["SecurePass123!"]
    )
    full_name: str | None = Field(
        None,
        description="User full name",
        examples=["João Silva"]
    )
    organization_name: str = Field(
        ..., 
        min_length=2,
        description="Organization name (minimum 2 characters)",
        examples=["Minha Empresa"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "João Silva",
                "organization_name": "Minha Empresa"
            }
        }
    )


class TokenResponse(BaseSchema):
    """Token response schema.

    Returned after successful authentication.
    Contains JWT access token and refresh token.
    """

    access_token: str = Field(
        ..., 
        description="JWT access token (valid for 15 minutes)",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )
    refresh_token: str = Field(
        ..., 
        description="JWT refresh token (valid for 7 days)",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (always 'bearer')",
        examples=["bearer"]
    )
    expires_in: int = Field(
        ..., 
        description="Access token expiration time in seconds",
        examples=[900]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 900
            }
        }
    )


class TokenRefresh(BaseSchema):
    """Token refresh request schema.

    Used to obtain a new access token using a valid refresh token.
    """

    refresh_token: str = Field(
        ..., 
        description="Valid refresh token",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."]
    )


class PasswordChange(BaseSchema):
    """Password change request schema.

    Allows authenticated users to change their password.
    """

    current_password: str = Field(
        ..., 
        description="Current password for verification",
        examples=["oldpassword123"]
    )
    new_password: str = Field(
        ..., 
        min_length=8,
        description="New password (minimum 8 characters, must be different from current)",
        examples=["NewSecurePass456!"]
    )


# ============== User Schemas ==============

class UserBase(BaseSchema):
    """User base schema with common user fields."""

    email: EmailStr = Field(
        ..., 
        description="User email address",
        examples=["user@example.com"]
    )
    full_name: str | None = Field(
        None,
        description="User full name",
        examples=["João Silva"]
    )
    role: str = Field(
        ..., 
        description="User role: admin, editor, or viewer",
        examples=["admin"]
    )
    is_active: bool = Field(
        ..., 
        description="Whether the user account is active",
        examples=[True]
    )


class UserResponse(UserBase, TimestampSchema):
    """User response schema.

    Returned when fetching user information.
    """

    organization_id: UUID = Field(
        ..., 
        description="ID of the organization the user belongs to",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "admin@example.com",
                "full_name": "João Silva",
                "role": "admin",
                "is_active": True,
                "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    )


class UserCreate(BaseSchema):
    """Create user request schema.

    Used by admins to create new users in their organization.
    """

    email: EmailStr = Field(
        ..., 
        description="User email address (must be unique)",
        examples=["newuser@example.com"]
    )
    password: str = Field(
        ..., 
        min_length=8,
        description="Initial password for the user",
        examples=["TempPass123!"]
    )
    full_name: str | None = Field(
        None,
        description="User full name",
        examples=["Maria Santos"]
    )
    role: str = Field(
        default="viewer",
        description="User role: admin, editor, or viewer",
        examples=["editor"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "newuser@example.com",
                "password": "TempPass123!",
                "full_name": "Maria Santos",
                "role": "editor"
            }
        }
    )


class UserUpdate(BaseSchema):
    """Update user request schema.

    Allows updating user information. All fields are optional.
    """

    full_name: str | None = Field(
        None,
        description="New full name for the user",
        examples=["João Silva Updated"]
    )
    role: str | None = Field(
        None,
        description="New role: admin, editor, or viewer",
        examples=["admin"]
    )
    is_active: bool | None = Field(
        None,
        description="Activate or deactivate the user account",
        examples=[True]
    )


# ============== Organization Schemas ==============

class OrganizationBase(BaseSchema):
    """Organization base schema."""

    name: str
    slug: str
    description: str | None


class OrganizationResponse(OrganizationBase, TimestampSchema):
    """Organization response schema."""

    pass


# ============== Workflow Schemas ==============

class WorkflowStepBase(BaseSchema):
    """Workflow step base schema.

    Defines a single step in a workflow (trigger or action).
    """

    name: str = Field(
        ..., 
        description="Step name",
        examples=["Webhook Trigger"]
    )
    description: str | None = Field(
        None,
        description="Step description",
        examples=["Receives webhook from external system"]
    )
    step_type: str = Field(
        ..., 
        description="Step type: 'trigger' or 'action'",
        examples=["trigger"]
    )
    trigger_type: str | None = Field(
        None,
        description="Trigger type (for trigger steps): webhook, scheduled, manual, file_upload",
        examples=["webhook"]
    )
    action_type: str | None = Field(
        None,
        description="Action type (for action steps): http_request, send_email, write_database, etc.",
        examples=["http_request"]
    )
    order: int = Field(
        ..., 
        ge=0,
        description="Execution order (0 for trigger, then 1, 2, 3...)",
        examples=[0]
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Step configuration (varies by type)",
        examples=[{"url": "https://api.example.com/webhook"}]
    )
    is_active: bool = Field(
        default=True,
        description="Whether this step is active",
        examples=[True]
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum retry attempts on failure",
        examples=[3]
    )
    retry_delay: int = Field(
        default=60,
        ge=0,
        description="Delay between retries in seconds",
        examples=[60]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Send Email",
                "description": "Send notification email",
                "step_type": "action",
                "action_type": "send_email",
                "order": 1,
                "config": {
                    "to": "user@example.com",
                    "subject": "Workflow Completed",
                    "body": "Your workflow has completed successfully."
                },
                "is_active": True,
                "max_retries": 3,
                "retry_delay": 60
            }
        }
    )


class WorkflowStepResponse(WorkflowStepBase, TimestampSchema):
    """Workflow step response schema.

    Full step data including ID and timestamps.
    """

    workflow_id: UUID = Field(
        ..., 
        description="ID of the parent workflow",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )


class WorkflowBase(BaseSchema):
    """Workflow base schema with common fields."""

    name: str = Field(
        ..., 
        min_length=3,
        max_length=100,
        description="Workflow name",
        examples=["Processar Pedidos"]
    )
    slug: str = Field(
        ..., 
        description="URL-friendly identifier (auto-generated)",
        examples=["processar-pedidos"]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="Workflow description",
        examples=["Processa novos pedidos recebidos via webhook"]
    )
    status: str = Field(
        default="draft",
        description="Workflow status: draft, active, inactive, archived",
        examples=["active"]
    )
    tags: list[str] = Field(
        default_factory=list,
        description="List of tags for categorization",
        examples=[["ecommerce", "pedidos"]]
    )


class WorkflowCreate(WorkflowBase):
    """Create workflow request schema.

    Used to create a new workflow with its initial steps.
    """

    steps: list[WorkflowStepBase] = Field(
        default_factory=list,
        description="Initial workflow steps (optional)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Processar Pedidos",
                "description": "Processa novos pedidos recebidos via webhook",
                "status": "active",
                "tags": ["ecommerce", "pedidos"],
                "steps": [
                    {
                        "name": "Webhook Trigger",
                        "description": "Recebe webhook de novo pedido",
                        "step_type": "trigger",
                        "trigger_type": "webhook",
                        "order": 0,
                        "config": {},
                        "is_active": True
                    },
                    {
                        "name": "Salvar no Banco",
                        "description": "Salva dados do pedido",
                        "step_type": "action",
                        "action_type": "write_database",
                        "order": 1,
                        "config": {
                            "table": "orders",
                            "operation": "INSERT"
                        },
                        "is_active": True
                    }
                ]
            }
        }
    )


class WorkflowUpdate(BaseSchema):
    """Update workflow request schema.

    Allows updating workflow information. All fields are optional.
    """

    name: str | None = Field(
        None,
        min_length=3,
        max_length=100,
        description="New workflow name",
        examples=["Processar Pedidos V2"]
    )
    description: str | None = Field(
        None,
        max_length=500,
        description="New description",
        examples=["Versão atualizada do processamento de pedidos"]
    )
    status: str | None = Field(
        None,
        description="New status: draft, active, inactive, archived",
        examples=["active"]
    )
    tags: list[str] | None = Field(
        None,
        description="New tags list (replaces existing)",
        examples=[["ecommerce", "v2"]]
    )


class WorkflowResponse(WorkflowBase, TimestampSchema):
    """Workflow response schema.

    Complete workflow data including steps and metadata.
    """

    version: int = Field(
        ..., 
        description="Workflow version number (increments on update)",
        examples=[1]
    )
    organization_id: UUID = Field(
        ..., 
        description="Organization that owns this workflow",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    steps: list[WorkflowStepResponse] = Field(
        default_factory=list,
        description="Workflow steps in execution order"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Processar Pedidos",
                "slug": "processar-pedidos",
                "description": "Processa novos pedidos",
                "status": "active",
                "tags": ["ecommerce"],
                "version": 1,
                "organization_id": "660e8400-e29b-41d4-a716-446655440001",
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:30:00Z",
                "steps": []
            }
        }
    )


# ============== Execution Schemas ==============

class ExecutionStepLogResponse(BaseSchema):
    """Execution step log response schema.

    Detailed information about a single step execution.
    """

    id: UUID = Field(
        ..., 
        description="Step log ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    step_id: UUID = Field(
        ..., 
        description="ID of the workflow step",
        examples=["660e8400-e29b-41d4-a716-446655440001"]
    )
    step_order: int = Field(
        ..., 
        description="Execution order of the step",
        examples=[1]
    )
    step_name: str = Field(
        ..., 
        description="Name of the step",
        examples=["Send Email"]
    )
    step_type: str = Field(
        ..., 
        description="Step type: trigger or action",
        examples=["action"]
    )
    status: str = Field(
        ..., 
        description="Execution status: pending, running, completed, failed",
        examples=["completed"]
    )
    started_at: datetime | None = Field(
        None,
        description="When the step started executing",
        examples=["2024-01-15T10:30:00Z"]
    )
    completed_at: datetime | None = Field(
        None,
        description="When the step finished executing",
        examples=["2024-01-15T10:30:05Z"]
    )
    duration_ms: int | None = Field(
        None,
        description="Execution duration in milliseconds",
        examples=[5000]
    )
    error_message: str | None = Field(
        None,
        description="Error message if the step failed",
        examples=["Connection timeout after 30s"]
    )
    retry_count: int = Field(
        ..., 
        description="Number of retry attempts made",
        examples=[0]
    )


class ExecutionResponse(BaseSchema):
    """Workflow execution response schema.

    Complete execution details including all step logs.
    """

    id: UUID = Field(
        ..., 
        description="Execution ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    workflow_id: UUID = Field(
        ..., 
        description="ID of the executed workflow",
        examples=["660e8400-e29b-41d4-a716-446655440001"]
    )
    correlation_id: str = Field(
        ..., 
        description="Unique correlation ID for tracking",
        examples=["exec_abc123def456"]
    )
    status: str = Field(
        ..., 
        description="Execution status: pending, running, completed, failed",
        examples=["completed"]
    )
    trigger_type: str = Field(
        ..., 
        description="How the execution was triggered: manual, webhook, scheduled, file_upload",
        examples=["manual"]
    )
    started_at: datetime | None = Field(
        None,
        description="When the execution started",
        examples=["2024-01-15T10:30:00Z"]
    )
    completed_at: datetime | None = Field(
        None,
        description="When the execution completed",
        examples=["2024-01-15T10:30:10Z"]
    )
    error_message: str | None = Field(
        None,
        description="Error message if execution failed",
        examples=["Step 2 failed: SMTP connection error"]
    )
    retry_count: int = Field(
        ..., 
        description="Total retry attempts across all steps",
        examples=[0]
    )
    created_at: datetime = Field(
        ..., 
        description="When the execution record was created",
        examples=["2024-01-15T10:30:00Z"]
    )
    step_logs: list[ExecutionStepLogResponse] = Field(
        default_factory=list,
        description="Execution logs for each step"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "workflow_id": "660e8400-e29b-41d4-a716-446655440001",
                "correlation_id": "exec_abc123def456",
                "status": "completed",
                "trigger_type": "manual",
                "started_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:30:10Z",
                "error_message": None,
                "retry_count": 0,
                "created_at": "2024-01-15T10:30:00Z",
                "step_logs": []
            }
        }
    )


class ExecutionListResponse(BaseSchema):
    """Execution list response schema.

    Simplified execution data for listing endpoints.
    """

    id: UUID = Field(
        ..., 
        description="Execution ID",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    workflow_id: UUID = Field(
        ..., 
        description="Workflow ID",
        examples=["660e8400-e29b-41d4-a716-446655440001"]
    )
    workflow_name: str = Field(
        ..., 
        description="Name of the workflow",
        examples=["Processar Pedidos"]
    )
    correlation_id: str = Field(
        ..., 
        description="Correlation ID",
        examples=["exec_abc123def456"]
    )
    status: str = Field(
        ..., 
        description="Execution status",
        examples=["completed"]
    )
    trigger_type: str = Field(
        ..., 
        description="Trigger type",
        examples=["manual"]
    )
    started_at: datetime | None = Field(
        None,
        description="Start time",
        examples=["2024-01-15T10:30:00Z"]
    )
    completed_at: datetime | None = Field(
        None,
        description="Completion time",
        examples=["2024-01-15T10:30:10Z"]
    )
    created_at: datetime = Field(
        ..., 
        description="Creation time",
        examples=["2024-01-15T10:30:00Z"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "workflow_id": "660e8400-e29b-41d4-a716-446655440001",
                "workflow_name": "Processar Pedidos",
                "correlation_id": "exec_abc123def456",
                "status": "completed",
                "trigger_type": "manual",
                "started_at": "2024-01-15T10:30:00Z",
                "completed_at": "2024-01-15T10:30:10Z",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
    )


# ============== Audit Log Schemas ==============

class AuditLogResponse(BaseSchema):
    """Audit log response."""

    id: UUID
    user_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    description: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


# ============== File Upload Schemas ==============

class FileUploadResponse(BaseSchema):
    """File upload response."""

    id: UUID
    original_filename: str
    file_size: int
    mime_type: str
    extension: str
    processed: bool
    created_at: datetime


# ============== Dashboard Schemas ==============

class DashboardMetrics(BaseSchema):
    """Dashboard metrics."""

    total_workflows: int
    active_workflows: int
    total_executions_today: int
    successful_executions_today: int
    failed_executions_today: int
    pending_executions: int
    avg_execution_time_ms: int | None


class RecentExecution(BaseSchema):
    """Recent execution item."""

    id: UUID
    workflow_name: str
    status: str
    trigger_type: str
    created_at: datetime


class DashboardData(BaseSchema):
    """Dashboard data response."""

    metrics: DashboardMetrics
    recent_executions: list[RecentExecution]


# ============== Notification Schemas ==============

class NotificationConfigUpdate(BaseSchema):
    """Notification configuration update request."""
    
    notify_on_failure: bool | None = Field(
        None,
        description="Send notification when workflow fails",
        examples=[True]
    )
    notify_on_success: bool | None = Field(
        None,
        description="Send notification when workflow succeeds",
        examples=[False]
    )
    notify_on_retry: bool | None = Field(
        None,
        description="Send notification when workflow retries",
        examples=[True]
    )
    email_recipients: list[str] | None = Field(
        None,
        description="List of email addresses to notify",
        examples=[["admin@example.com", "devops@example.com"]]
    )
    slack_webhook_url: str | None = Field(
        None,
        description="Slack webhook URL for notifications",
        examples=["https://hooks.slack.com/services/xxx/yyy/zzz"]
    )
    custom_webhook_url: str | None = Field(
        None,
        description="Custom webhook URL for notifications",
        examples=["https://example.com/webhooks/notifications"]
    )
    cooldown_minutes: int | None = Field(
        None,
        ge=0,
        description="Minimum minutes between notifications",
        examples=[15]
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "notify_on_failure": True,
                "notify_on_success": False,
                "email_recipients": ["admin@example.com"],
                "cooldown_minutes": 15
            }
        }
    )
