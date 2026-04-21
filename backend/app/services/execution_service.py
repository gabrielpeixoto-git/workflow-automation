"""Workflow execution service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import ExecutionStepLogResponse
from app.core.logging_config import get_logger
from app.models.audit_log import AuditAction, AuditLog
from app.models.execution import (
    ExecutionLog,
    ExecutionStatus,
    StepStatus,
    WorkflowExecution,
)
from app.models.user import User
from app.models.workflow import TriggerType, Workflow, WorkflowStep
from app.tasks.workflow_tasks import execute_workflow_task

logger = get_logger(__name__)


class ExecutionService:
    """Workflow execution management service."""

    @staticmethod
    def generate_correlation_id() -> str:
        """Generate unique correlation ID."""
        return f"exec_{uuid.uuid4().hex[:12]}_{int(datetime.now(timezone.utc).timestamp())}"

    @staticmethod
    async def create_execution(
        db: AsyncSession,
        workflow: Workflow,
        trigger_type: TriggerType | str,
        trigger_payload: dict[str, Any] | None,
        user: User | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> WorkflowExecution:
        """Create a new workflow execution."""
        correlation_id = ExecutionService.generate_correlation_id()

        execution = WorkflowExecution(
            workflow_id=workflow.id,
            correlation_id=correlation_id,
            status=ExecutionStatus.PENDING,
            trigger_type=trigger_type.value if isinstance(trigger_type, TriggerType) else trigger_type,
            trigger_payload=trigger_payload or {},
        )
        db.add(execution)
        await db.flush()

        # Create step logs
        for step in workflow.steps:
            if step.is_active:
                # Handle both enum and string step_type
                step_type_val = step.step_type.value if hasattr(step.step_type, 'value') else step.step_type
                step_log = ExecutionLog(
                    execution_id=execution.id,
                    step_id=step.id,
                    step_order=step.order,
                    step_name=step.name,
                    step_type=step_type_val,
                    status=StepStatus.PENDING,
                )
                db.add(step_log)

        # Create audit log
        audit = AuditLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            action=AuditAction.EXECUTION_START,
            resource_type="execution",
            resource_id=str(execution.id),
            description=f"Started execution for workflow: {workflow.name}",
            details={
                "workflow_id": str(workflow.id),
                "trigger_type": trigger_type.value if isinstance(trigger_type, TriggerType) else trigger_type,
                "correlation_id": correlation_id,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=workflow.organization_id,
        )
        db.add(audit)

        await db.commit()
        await db.refresh(execution)

        logger.info(
            "Execution created: %s for workflow %s (correlation: %s)",
            execution.id,
            workflow.id,
            correlation_id,
        )
        return execution

    @staticmethod
    async def start_execution(
        db: AsyncSession,
        execution: WorkflowExecution,
    ) -> WorkflowExecution:
        """Start workflow execution (queue Celery task)."""
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc)

        # Queue Celery task
        task = execute_workflow_task.delay(str(execution.id))
        execution.celery_task_id = task.id

        await db.commit()

        logger.info(
            "Execution started: %s (celery task: %s)",
            execution.id,
            task.id,
        )
        return execution

    @staticmethod
    async def get_execution(
        db: AsyncSession,
        execution_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> WorkflowExecution | None:
        """Get execution by ID."""
        result = await db.execute(
            select(WorkflowExecution)
            .options(selectinload(WorkflowExecution.step_logs))
            .join(Workflow)
            .where(
                WorkflowExecution.id == execution_id,
                Workflow.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_executions(
        db: AsyncSession,
        organization_id: uuid.UUID,
        workflow_id: uuid.UUID | None = None,
        status: ExecutionStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[WorkflowExecution]:
        """Get executions for organization."""
        query = (
            select(WorkflowExecution)
            .join(Workflow)
            .where(Workflow.organization_id == organization_id)
            .order_by(WorkflowExecution.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

        if workflow_id:
            query = query.where(WorkflowExecution.workflow_id == workflow_id)
        if status:
            query = query.where(WorkflowExecution.status == status)

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def retry_execution(
        db: AsyncSession,
        execution: WorkflowExecution,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> WorkflowExecution:
        """Retry a failed execution."""
        if execution.status not in (ExecutionStatus.FAILED, ExecutionStatus.CANCELLED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only failed or cancelled executions can be retried",
            )

        # Reset status
        execution.status = ExecutionStatus.PENDING
        execution.retry_count += 1
        execution.error_message = None
        execution.completed_at = None

        # Reset step logs
        for step_log in execution.step_logs:
            step_log.status = StepStatus.PENDING
            step_log.started_at = None
            step_log.completed_at = None
            step_log.duration_ms = None
            step_log.error_message = None
            step_log.error_details = None
            step_log.retry_count = 0

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.EXECUTION_RETRY,
            resource_type="execution",
            resource_id=str(execution.id),
            description=f"Retried execution: {execution.correlation_id}",
            details={"retry_count": execution.retry_count},
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)

        await db.commit()

        # Queue Celery task
        task = execute_workflow_task.delay(str(execution.id))
        execution.celery_task_id = task.id
        await db.commit()

        logger.info(
            "Execution retried: %s (retry #%s)",
            execution.id,
            execution.retry_count,
        )
        return execution

    @staticmethod
    async def cancel_execution(
        db: AsyncSession,
        execution: WorkflowExecution,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> WorkflowExecution:
        """Cancel a running execution."""
        if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING, ExecutionStatus.RETRYING):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending, running or retrying executions can be cancelled",
            )

        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.now(timezone.utc)

        # Update running steps
        for step_log in execution.step_logs:
            if step_log.status == StepStatus.RUNNING:
                step_log.status = StepStatus.SKIPPED
                step_log.completed_at = datetime.now(timezone.utc)

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.EXECUTION_CANCEL,
            resource_type="execution",
            resource_id=str(execution.id),
            description=f"Cancelled execution: {execution.correlation_id}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)

        await db.commit()

        logger.info("Execution cancelled: %s", execution.id)
        return execution

    @staticmethod
    async def get_dashboard_metrics(
        db: AsyncSession,
        organization_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get dashboard metrics."""
        from datetime import timedelta

        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        # Total workflows
        workflows_result = await db.execute(
            select(func.count(Workflow.id))
            .where(
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        total_workflows = workflows_result.scalar() or 0

        # Active workflows
        active_workflows_result = await db.execute(
            select(func.count(Workflow.id))
            .where(
                Workflow.organization_id == organization_id,
                Workflow.status == "active",
                Workflow.deleted_at.is_(None),
            )
        )
        active_workflows = active_workflows_result.scalar() or 0

        # Today's executions
        today_executions_result = await db.execute(
            select(func.count(WorkflowExecution.id))
            .join(Workflow)
            .where(
                Workflow.organization_id == organization_id,
                WorkflowExecution.created_at >= today,
            )
        )
        total_executions_today = today_executions_result.scalar() or 0

        # Successful executions today
        successful_result = await db.execute(
            select(func.count(WorkflowExecution.id))
            .join(Workflow)
            .where(
                Workflow.organization_id == organization_id,
                WorkflowExecution.created_at >= today,
                WorkflowExecution.status == ExecutionStatus.COMPLETED,
            )
        )
        successful_executions_today = successful_result.scalar() or 0

        # Failed executions today
        failed_result = await db.execute(
            select(func.count(WorkflowExecution.id))
            .join(Workflow)
            .where(
                Workflow.organization_id == organization_id,
                WorkflowExecution.created_at >= today,
                WorkflowExecution.status == ExecutionStatus.FAILED,
            )
        )
        failed_executions_today = failed_result.scalar() or 0

        # Pending executions
        pending_result = await db.execute(
            select(func.count(WorkflowExecution.id))
            .join(Workflow)
            .where(
                Workflow.organization_id == organization_id,
                WorkflowExecution.status.in_([ExecutionStatus.PENDING, ExecutionStatus.RUNNING]),
            )
        )
        pending_executions = pending_result.scalar() or 0

        return {
            "total_workflows": total_workflows,
            "active_workflows": active_workflows,
            "total_executions_today": total_executions_today,
            "successful_executions_today": successful_executions_today,
            "failed_executions_today": failed_executions_today,
            "pending_executions": pending_executions,
            "avg_execution_time_ms": None,  # Calculated from execution data
        }
