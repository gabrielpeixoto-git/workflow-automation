"""Webhook trigger routes."""

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.core.logging_config import get_logger
from app.db.database import AsyncSessionLocal
from app.models.audit_log import AuditAction, AuditLog
from app.models.execution import ExecutionStatus
from app.models.workflow import TriggerType, Workflow, WorkflowStatus, WorkflowStep
from app.services.execution_service import ExecutionService
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)
router = APIRouter()


@router.post("/{workflow_id}", status_code=status.HTTP_202_ACCEPTED)
async def webhook_trigger(
    request: Request,
    workflow_id: str,
) -> dict[str, str]:
    """Handle webhook trigger."""
    # Validate workflow_id
    try:
        wf_id = uuid.UUID(workflow_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workflow ID",
        )
    
    # Get client info
    forwarded_for = request.headers.get("x-forwarded-for")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Get payload
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    
    # Add headers and query params to payload
    payload["_webhook"] = {
        "headers": dict(request.headers),
        "query_params": dict(request.query_params),
        "ip_address": ip_address,
    }
    
    async with AsyncSessionLocal() as db:
        # Get workflow
        workflow = await WorkflowService.get_workflow(
            db=db,
            workflow_id=wf_id,
            organization_id=None,  # Will be checked later
        )
        
        if not workflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow not found",
            )
        
        # Check if workflow is active
        if workflow.status != WorkflowStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow is not active",
            )
        
        # Check if workflow has webhook trigger
        has_webhook_trigger = any(
            s.step_type == "trigger" and s.trigger_type == TriggerType.WEBHOOK
            for s in workflow.steps
        )
        
        if not has_webhook_trigger:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow does not support webhook triggers",
            )
        
        # Create execution
        execution = await ExecutionService.create_execution(
            db=db,
            workflow=workflow,
            trigger_type=TriggerType.WEBHOOK,
            trigger_payload=payload,
            user=None,  # System triggered
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        # Create audit log
        audit = AuditLog(
            action=AuditAction.WEBHOOK_TRIGGER,
            resource_type="workflow",
            resource_id=str(workflow.id),
            description=f"Webhook triggered workflow: {workflow.name}",
            details={
                "execution_id": str(execution.id),
                "correlation_id": execution.correlation_id,
                "ip_address": ip_address,
            },
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=workflow.organization_id,
        )
        db.add(audit)
        await db.commit()
        
        # Start execution
        execution = await ExecutionService.start_execution(db=db, execution=execution)
    
    logger.info(
        "webhook_triggered",
        workflow_id=workflow_id,
        execution_id=str(execution.id),
        correlation_id=execution.correlation_id,
    )
    
    return {
        "message": "Webhook received and execution queued",
        "execution_id": str(execution.id),
        "correlation_id": execution.correlation_id,
        "status": execution.status.value,
    }
