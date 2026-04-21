"""Execution API routes."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import ExecutionListResponse, ExecutionResponse
from app.core.deps import (
    CurrentUser, DBSession, RequireEditor, get_client_info,
    RequireExecutionView, RequireExecutionStart, RequireExecutionCancel, RequireExecutionRetry,
)
from app.core.logging_config import get_logger
from app.models.execution import ExecutionStatus, WorkflowExecution
from app.models.workflow import TriggerType, Workflow, WorkflowStatus
from app.services.execution_service import ExecutionService
from app.services.workflow_service import WorkflowService

logger = get_logger(__name__)
router = APIRouter()


@router.get("", response_model=list[ExecutionListResponse])
async def list_executions(
    db: DBSession,
    user: RequireExecutionView,
    workflow_id: UUID | None = Query(None),
    status: ExecutionStatus | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> Any:
    """List executions for current user's organization."""
    executions = await ExecutionService.get_executions(
        db=db,
        organization_id=user.organization_id,
        workflow_id=workflow_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    
    # Transform to response format
    result = []
    for exec in executions:
        result.append({
            "id": exec.id,
            "workflow_id": exec.workflow_id,
            "workflow_name": exec.workflow.name if exec.workflow else "Unknown",
            "correlation_id": exec.correlation_id,
            "status": exec.status.value,
            "trigger_type": exec.trigger_type,
            "started_at": exec.started_at,
            "completed_at": exec.completed_at,
            "created_at": exec.created_at,
        })
    
    return result


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: DBSession,
    user: RequireExecutionView,
) -> Any:
    """Get execution by ID."""
    execution = await ExecutionService.get_execution(
        db=db,
        execution_id=execution_id,
        organization_id=user.organization_id,
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    
    # Transform to response format
    return {
        "id": execution.id,
        "workflow_id": execution.workflow_id,
        "correlation_id": execution.correlation_id,
        "status": execution.status.value,
        "trigger_type": execution.trigger_type,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "error_message": execution.error_message,
        "retry_count": execution.retry_count,
        "created_at": execution.created_at,
        "step_logs": [
            {
                "id": sl.id,
                "step_id": sl.step_id,
                "step_order": sl.step_order,
                "step_name": sl.step_name,
                "step_type": sl.step_type,
                "status": sl.status.value,
                "started_at": sl.started_at,
                "completed_at": sl.completed_at,
                "duration_ms": sl.duration_ms,
                "error_message": sl.error_message,
                "retry_count": sl.retry_count,
            }
            for sl in execution.step_logs
        ],
    }


@router.post("/{execution_id}/retry")
async def retry_execution(
    request: Request,
    execution_id: UUID,
    db: DBSession,
    user: RequireEditor,
) -> dict[str, str]:
    """Retry a failed execution."""
    execution = await ExecutionService.get_execution(
        db=db,
        execution_id=execution_id,
        organization_id=user.organization_id,
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    execution = await ExecutionService.retry_execution(
        db=db,
        execution=execution,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    return {
        "message": "Execution queued for retry",
        "execution_id": str(execution.id),
        "status": execution.status.value,
    }


@router.post("/{execution_id}/cancel")
async def cancel_execution(
    request: Request,
    execution_id: UUID,
    db: DBSession,
    user: RequireEditor,
) -> dict[str, str]:
    """Cancel a running execution."""
    execution = await ExecutionService.get_execution(
        db=db,
        execution_id=execution_id,
        organization_id=user.organization_id,
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    execution = await ExecutionService.cancel_execution(
        db=db,
        execution=execution,
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    return {
        "message": "Execution cancelled",
        "execution_id": str(execution.id),
        "status": execution.status.value,
    }


@router.post("/trigger/{workflow_id}")
async def trigger_workflow_manual(
    request: Request,
    workflow_id: UUID,
    db: DBSession,
    user: CurrentUser,
    payload: dict | None = None,
) -> dict[str, str]:
    """Manually trigger a workflow."""
    workflow = await WorkflowService.get_workflow(
        db=db,
        workflow_id=workflow_id,
        organization_id=user.organization_id,
    )
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    
    # Allow execution of active or draft workflows (manual trigger)
    if workflow.status not in (WorkflowStatus.ACTIVE, WorkflowStatus.DRAFT):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow must be active or in draft status to execute",
        )
    
    ip_address, user_agent = get_client_info(request)
    
    execution = await ExecutionService.create_execution(
        db=db,
        workflow=workflow,
        trigger_type=TriggerType.MANUAL,
        trigger_payload=payload or {},
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    
    # Start execution
    execution = await ExecutionService.start_execution(db=db, execution=execution)
    
    return {
        "message": "Workflow triggered",
        "execution_id": str(execution.id),
        "correlation_id": execution.correlation_id,
        "status": execution.status.value,
    }


@router.get("/stats/timeseries")
async def get_execution_timeseries(
    db: DBSession,
    user: CurrentUser,
    days: int = Query(7, ge=1, le=30),
) -> dict:
    """Get execution statistics by day for Chart.js.
    
    Returns daily counts of executions by status for the last N days.
    """
    from datetime import date
    
    # Calculate date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days - 1)
    
    # Build date list
    date_list = []
    current = start_date
    while current <= end_date:
        date_list.append(current)
        current += timedelta(days=1)
    
    # Query executions grouped by date and status
    start_dt = datetime.combine(start_date, datetime.min.time())
    
    result = await db.execute(
        select(
            func.date(WorkflowExecution.created_at).label("date"),
            WorkflowExecution.status,
            func.count(WorkflowExecution.id).label("count"),
        )
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= start_dt,
        )
        .group_by(func.date(WorkflowExecution.created_at), WorkflowExecution.status)
        .order_by(func.date(WorkflowExecution.created_at))
    )
    
    # Process results
    data_by_date = {}
    for row in result.all():
        date_str = row.date.strftime("%Y-%m-%d") if row.date else None
        if date_str:
            if date_str not in data_by_date:
                data_by_date[date_str] = {"completed": 0, "failed": 0, "running": 0}
            status_key = row.status.value if hasattr(row.status, "value") else str(row.status)
            if status_key in ["completed", "failed"]:
                data_by_date[date_str][status_key] = row.count
            elif status_key in ["running", "pending"]:
                data_by_date[date_str]["running"] += row.count
    
    # Fill missing dates with zeros
    labels = []
    completed_data = []
    failed_data = []
    running_data = []
    
    for d in date_list:
        date_str = d.strftime("%Y-%m-%d")
        labels.append(d.strftime("%d/%m"))
        day_data = data_by_date.get(date_str, {"completed": 0, "failed": 0, "running": 0})
        completed_data.append(day_data["completed"])
        failed_data.append(day_data["failed"])
        running_data.append(day_data["running"])
    
    # Calculate totals
    total_completed = sum(completed_data)
    total_failed = sum(failed_data)
    total_running = sum(running_data)
    total = total_completed + total_failed + total_running
    
    success_rate = round((total_completed / total * 100), 1) if total > 0 else 0
    
    return {
        "labels": labels,
        "datasets": {
            "completed": completed_data,
            "failed": failed_data,
            "running": running_data,
        },
        "summary": {
            "total": total,
            "completed": total_completed,
            "failed": total_failed,
            "running": total_running,
            "success_rate": success_rate,
            "period_days": days,
        },
    }


@router.get("/stats/summary")
async def get_execution_summary(
    db: DBSession,
    user: CurrentUser,
) -> dict:
    """Get overall execution statistics summary."""
    # Total counts by status
    status_result = await db.execute(
        select(
            WorkflowExecution.status,
            func.count(WorkflowExecution.id).label("count"),
        )
        .join(Workflow)
        .where(Workflow.organization_id == user.organization_id)
        .group_by(WorkflowExecution.status)
    )
    
    status_counts = {}
    total = 0
    for status, count in status_result.all():
        status_key = status.value if hasattr(status, "value") else str(status)
        status_counts[status_key] = count
        total += count
    
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    running = status_counts.get("running", 0) + status_counts.get("pending", 0)
    
    # Today's executions
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= today_start,
        )
    )
    today_count = today_result.scalar() or 0
    
    # Average execution time (for completed executions)
    avg_time_result = await db.execute(
        select(
            func.avg(
                func.extract("epoch", WorkflowExecution.completed_at) - 
                func.extract("epoch", WorkflowExecution.started_at)
            )
        )
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.status == "completed",
            WorkflowExecution.completed_at.isnot(None),
            WorkflowExecution.started_at.isnot(None),
        )
    )
    avg_seconds = avg_time_result.scalar()
    avg_duration = round(avg_seconds, 1) if avg_seconds else None
    
    return {
        "total": total,
        "by_status": {
            "completed": completed,
            "failed": failed,
            "running": running,
        },
        "success_rate": round((completed / total * 100), 1) if total > 0 else 0,
        "today": today_count,
        "avg_duration_seconds": avg_duration,
    }
