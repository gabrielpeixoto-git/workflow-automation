"""Dashboard API routes."""

from typing import Any

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app.api.schemas import DashboardData, DashboardMetrics, RecentExecution
from app.core.deps import CurrentUser, DBSession
from app.models.execution import ExecutionStatus, WorkflowExecution
from app.models.workflow import Workflow, WorkflowStatus
from app.services.execution_service import ExecutionService

router = APIRouter()


@router.get("/metrics", response_model=DashboardMetrics)
async def get_metrics(
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get dashboard metrics."""
    metrics = await ExecutionService.get_dashboard_metrics(
        db=db,
        organization_id=user.organization_id,
    )
    return DashboardMetrics(**metrics)


@router.get("/metrics/active-workflows")
async def get_active_workflows_count(
    db: DBSession,
    user: CurrentUser,
) -> str:
    """Get active workflows count (HTML fragment)."""
    result = await db.execute(
        select(func.count(Workflow.id))
        .where(
            Workflow.organization_id == user.organization_id,
            Workflow.status == WorkflowStatus.ACTIVE,
            Workflow.deleted_at.is_(None),
        )
    )
    count = result.scalar() or 0
    return str(count)


@router.get("/metrics/executions-today")
async def get_executions_today_count(
    db: DBSession,
    user: CurrentUser,
) -> str:
    """Get today's executions count (HTML fragment)."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= today,
        )
    )
    count = result.scalar() or 0
    return str(count)


@router.get("/metrics/success-rate")
async def get_success_rate(
    db: DBSession,
    user: CurrentUser,
) -> str:
    """Get today's success rate (HTML fragment)."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Total today
    total_result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= today,
        )
    )
    total = total_result.scalar() or 0

    # Successful today
    success_result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= today,
            WorkflowExecution.status == ExecutionStatus.COMPLETED,
        )
    )
    successful = success_result.scalar() or 0

    if total == 0:
        return "0"
    
    rate = (successful / total) * 100
    return str(round(rate))


@router.get("/metrics/failures-today")
async def get_failures_today_count(
    db: DBSession,
    user: CurrentUser,
) -> str:
    """Get today's failures count (HTML fragment)."""
    from datetime import datetime, timezone

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    result = await db.execute(
        select(func.count(WorkflowExecution.id))
        .join(Workflow)
        .where(
            Workflow.organization_id == user.organization_id,
            WorkflowExecution.created_at >= today,
            WorkflowExecution.status == ExecutionStatus.FAILED,
        )
    )
    count = result.scalar() or 0
    return str(count)


@router.get("/recent-executions")
async def get_recent_executions(
    db: DBSession,
    user: CurrentUser,
    limit: int = 5,
) -> list[RecentExecution]:
    """Get recent executions."""
    executions = await ExecutionService.get_executions(
        db=db,
        organization_id=user.organization_id,
        limit=limit,
    )
    
    return [
        RecentExecution(
            id=exec.id,
            workflow_name=exec.workflow.name if exec.workflow else "Unknown",
            status=exec.status.value,
            trigger_type=exec.trigger_type,
            created_at=exec.created_at,
        )
        for exec in executions
    ]
