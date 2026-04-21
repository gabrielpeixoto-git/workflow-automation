"""Celery tasks for workflow execution."""

import asyncio
import uuid
from datetime import datetime, timezone

from celery.exceptions import MaxRetriesExceededError, SoftTimeLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging_config import get_logger
from app.db.database import AsyncSessionLocal
from app.models.audit_log import AuditAction, AuditLog
from app.models.execution import (
    ExecutionLog,
    ExecutionStatus,
    StepStatus,
    WorkflowExecution,
)
from app.models.workflow import ActionType, StepType, TriggerType, WorkflowStep
from app.services.actions import (
    execute_database_action,
    execute_email_action,
    execute_export_csv_action,
    execute_export_pdf_action,
    execute_http_action,
    execute_notify_action,
    execute_transform_action,
)
from app.services.integration_action_handlers import integration_registry
from app.services.notification_service import NotificationService

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_workflow_task(self, execution_id: str) -> dict:
    """Execute workflow task."""
    # Run async code in sync Celery task
    return asyncio.run(_execute_workflow_async(self, execution_id))


async def _execute_workflow_async(self, execution_id: str) -> dict:
    """Async workflow execution."""
    async with AsyncSessionLocal() as db:
        try:
            # Load execution with workflow and steps
            result = await db.execute(
                select(WorkflowExecution)
                .options(
                    selectinload(WorkflowExecution.workflow).selectinload(WorkflowExecution.workflow.property.mapper.class_.steps),
                    selectinload(WorkflowExecution.step_logs),
                )
                .where(WorkflowExecution.id == uuid.UUID(execution_id))
            )
            execution = result.scalar_one_or_none()

            if not execution:
                logger.error("execution_not_found", execution_id=execution_id)
                return {"status": "failed", "error": "Execution not found"}

            if execution.status == ExecutionStatus.CANCELLED:
                logger.info("execution_cancelled", execution_id=execution_id)
                return {"status": "cancelled"}

            # Update status to running
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now(timezone.utc)
            await db.commit()

            # Execute steps
            context = execution.trigger_payload or {}
            workflow = execution.workflow

            # Get ordered active steps
            steps = sorted(
                [s for s in workflow.steps if s.is_active],
                key=lambda x: x.order
            )

            trigger_step = None
            action_steps = []

            for step in steps:
                if step.step_type == StepType.TRIGGER:
                    trigger_step = step
                else:
                    action_steps.append(step)

            # Execute trigger step (just mark as completed)
            if trigger_step:
                trigger_log = next(
                    (sl for sl in execution.step_logs if sl.step_id == trigger_step.id),
                    None
                )
                if trigger_log and trigger_log.status == StepStatus.PENDING:
                    trigger_log.status = StepStatus.COMPLETED
                    trigger_log.started_at = datetime.now(timezone.utc)
                    trigger_log.completed_at = datetime.now(timezone.utc)
                    trigger_log.duration_ms = 0
                    await db.commit()

            # Execute action steps
            for step in action_steps:
                step_log = next(
                    (sl for sl in execution.step_logs if sl.step_id == step.id),
                    None
                )
                if not step_log:
                    continue

                # Check if execution was cancelled
                await db.refresh(execution)
                if execution.status == ExecutionStatus.CANCELLED:
                    step_log.status = StepStatus.SKIPPED
                    step_log.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    continue

                # Execute step with retries
                step_log.status = StepStatus.RUNNING
                step_log.started_at = datetime.now(timezone.utc)
                step_log.input_data = context.copy()
                await db.commit()

                try:
                    result = await execute_step(step, context, db)
                    
                    # Update context with output
                    if result and isinstance(result, dict):
                        context.update(result)
                    
                    # Mark as completed
                    step_log.status = StepStatus.COMPLETED
                    step_log.completed_at = datetime.now(timezone.utc)
                    step_log.duration_ms = int(
                        (step_log.completed_at - step_log.started_at).total_seconds() * 1000
                    )
                    step_log.output_data = context.copy()
                    
                    logger.info(
                        "step_completed",
                        execution_id=execution_id,
                        step_id=str(step.id),
                        step_name=step.name,
                    )

                except Exception as e:
                    step_log.status = StepStatus.FAILED
                    step_log.completed_at = datetime.now(timezone.utc)
                    step_log.error_message = str(e)
                    step_log.error_details = {"exception_type": type(e).__name__}
                    step_log.retry_count += 1

                    logger.error(
                        "step_failed",
                        execution_id=execution_id,
                        step_id=str(step.id),
                        error=str(e),
                    )

                    # Check if should retry
                    if step_log.retry_count < step.max_retries:
                        execution.status = ExecutionStatus.RETRYING
                        await db.commit()
                        
                        # Retry the entire task
                        raise self.retry(
                            countdown=step.retry_delay * (2 ** step_log.retry_count),  # Exponential backoff
                            exc=e,
                        )

                    # Max retries exceeded
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = f"Step '{step.name}' failed: {str(e)}"
                    execution.completed_at = datetime.now(timezone.utc)
                    await db.commit()

                    # Create audit log
                    audit = AuditLog(
                        action=AuditAction.EXECUTION_FAIL,
                        resource_type="execution",
                        resource_id=execution_id,
                        description=f"Execution failed: {execution.correlation_id}",
                        details={
                            "error": str(e),
                            "failed_step": step.name,
                            "retry_count": step_log.retry_count,
                        },
                        organization_id=workflow.organization_id,
                    )
                    db.add(audit)
                    await db.commit()

                    # Send failure notifications
                    try:
                        await NotificationService.notify_workflow_failure(
                            db=db,
                            workflow=workflow,
                            execution_id=execution.id,
                            error_message=execution.error_message,
                        )
                    except Exception as notify_error:
                        logger.error(
                            "Failed to send failure notification",
                            execution_id=execution_id,
                            error=str(notify_error),
                        )

                    return {
                        "status": "failed",
                        "error": str(e),
                        "failed_step": step.name,
                    }

                await db.commit()

            # All steps completed successfully
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            execution.output_data = context
            await db.commit()

            # Create audit log
            audit = AuditLog(
                action=AuditAction.EXECUTION_COMPLETE,
                resource_type="execution",
                resource_id=execution_id,
                description=f"Execution completed: {execution.correlation_id}",
                details={"steps_count": len(action_steps)},
                organization_id=workflow.organization_id,
            )
            db.add(audit)
            await db.commit()

            logger.info(
                "execution_completed",
                execution_id=execution_id,
                correlation_id=execution.correlation_id,
            )

            return {
                "status": "completed",
                "execution_id": execution_id,
                "correlation_id": execution.correlation_id,
            }

        except SoftTimeLimitExceeded:
            logger.error("execution_timeout", execution_id=execution_id)
            await _mark_execution_failed(db, execution_id, "Execution timeout exceeded")
            return {"status": "failed", "error": "Timeout"}

        except MaxRetriesExceededError:
            logger.error("max_retries_exceeded", execution_id=execution_id)
            await _mark_execution_failed(db, execution_id, "Max retries exceeded")
            return {"status": "failed", "error": "Max retries exceeded"}

        except Exception as e:
            logger.exception("execution_error", execution_id=execution_id, error=str(e))
            await _mark_execution_failed(db, execution_id, str(e))
            raise


async def _mark_execution_failed(db: AsyncSession, execution_id: str, error: str) -> None:
    """Mark execution as failed and send notifications."""
    from app.models.workflow import Workflow
    
    result = await db.execute(
        select(WorkflowExecution)
        .options(selectinload(WorkflowExecution.workflow))
        .where(WorkflowExecution.id == uuid.UUID(execution_id))
    )
    execution = result.scalar_one_or_none()
    
    if execution:
        execution.status = ExecutionStatus.FAILED
        execution.error_message = error
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()
        
        # Send failure notifications
        try:
            await NotificationService.notify_workflow_failure(
                db=db,
                workflow=execution.workflow,
                execution_id=execution.id,
                error_message=error,
            )
        except Exception as notify_error:
            logger.error(
                "Failed to send failure notification",
                execution_id=execution_id,
                error=str(notify_error),
            )


async def execute_step(
    step: WorkflowStep,
    context: dict,
    db: AsyncSession,
) -> dict:
    """Execute a single workflow step."""
    config = step.config or {}

    if step.step_type == StepType.TRIGGER:
        return context

    if step.step_type != StepType.ACTION or not step.action_type:
        raise ValueError(f"Invalid step type: {step.step_type}")

    action_type = step.action_type

    if action_type == ActionType.HTTP_REQUEST:
        return await execute_http_action(config, context)
    elif action_type == ActionType.SEND_EMAIL:
        return await execute_email_action(config, context)
    elif action_type == ActionType.WRITE_DATABASE:
        return await execute_database_action(config, context, db)
    elif action_type == ActionType.TRANSFORM_PAYLOAD:
        return await execute_transform_action(config, context)
    elif action_type == ActionType.EXPORT_CSV:
        return await execute_export_csv_action(config, context)
    elif action_type == ActionType.EXPORT_PDF:
        return await execute_export_pdf_action(config, context)
    elif action_type == ActionType.NOTIFY:
        return await execute_notify_action(config, context)
    elif action_type == ActionType.SEND_SLACK:
        return await integration_registry.execute(
            db=db,
            action_type=action_type.value,
            step=step,
            context=context,
            organization_id=step.workflow.organization_id if step.workflow else None,
        )
    elif action_type == ActionType.SEND_DISCORD:
        return await integration_registry.execute(
            db=db,
            action_type=action_type.value,
            step=step,
            context=context,
            organization_id=step.workflow.organization_id if step.workflow else None,
        )
    else:
        raise ValueError(f"Unknown action type: {action_type}")


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def execute_scheduled_workflow(self, workflow_id: str, organization_id: str) -> dict:
    """Execute a scheduled workflow by creating a new execution."""
    return asyncio.run(_execute_scheduled_workflow_async(workflow_id, organization_id))


async def _execute_scheduled_workflow_async(workflow_id: str, organization_id: str) -> dict:
    """Async execution of scheduled workflow."""
    from app.models.workflow import Workflow
    from app.services.execution_service import ExecutionService
    
    async with AsyncSessionLocal() as db:
        try:
            # Load workflow
            result = await db.execute(
                select(Workflow)
                .options(selectinload(Workflow.steps))
                .where(
                    Workflow.id == uuid.UUID(workflow_id),
                    Workflow.organization_id == organization_id,
                    Workflow.status == "active",
                    Workflow.deleted_at.is_(None),
                )
            )
            workflow = result.scalar_one_or_none()
            
            if not workflow:
                logger.error("scheduled_workflow_not_found", workflow_id=workflow_id)
                return {"status": "failed", "error": "Workflow not found or not active"}
            
            # Check if trigger is scheduled type
            trigger_step = None
            for step in workflow.steps:
                if step.step_type == StepType.TRIGGER and step.trigger_type == TriggerType.SCHEDULED:
                    trigger_step = step
                    break
            
            if not trigger_step:
                logger.error("scheduled_trigger_not_found", workflow_id=workflow_id)
                return {"status": "failed", "error": "No scheduled trigger found"}
            
            # Create execution
            correlation_id = f"scheduled_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{workflow_id[:8]}"
            
            execution = WorkflowExecution(
                workflow_id=workflow.id,
                correlation_id=correlation_id,
                status=ExecutionStatus.PENDING,
                trigger_type="scheduled",
                trigger_payload={
                    "scheduled_at": datetime.now(timezone.utc).isoformat(),
                    "cron_expression": trigger_step.config.get("cron", "unknown"),
                },
            )
            db.add(execution)
            await db.flush()
            
            # Create step logs
            for step in workflow.steps:
                log = ExecutionLog(
                    execution_id=execution.id,
                    step_id=step.id,
                    step_order=step.order,
                    step_name=step.name,
                    step_type=step.step_type.value if hasattr(step.step_type, 'value') else str(step.step_type),
                    status=StepStatus.PENDING,
                )
                db.add(log)
            
            await db.commit()
            
            # Start execution
            execution.status = ExecutionStatus.RUNNING
            execution.started_at = datetime.now(timezone.utc)
            
            task = execute_workflow_task.delay(str(execution.id))
            execution.celery_task_id = task.id
            await db.commit()
            
            logger.info(
                "scheduled_workflow_started",
                workflow_id=workflow_id,
                execution_id=str(execution.id),
                correlation_id=correlation_id,
            )
            
            return {
                "status": "started",
                "workflow_id": workflow_id,
                "execution_id": str(execution.id),
                "correlation_id": correlation_id,
            }
            
        except Exception as e:
            logger.exception("scheduled_workflow_error", workflow_id=workflow_id, error=str(e))
            return {"status": "failed", "error": str(e)}
