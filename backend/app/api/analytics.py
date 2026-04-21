"""Analytics and dashboard API routes."""

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict

from app.core.deps import CurrentUser, DBSession
from app.core.logging_config import get_logger
from app.services.analytics_service import AnalyticsService

logger = get_logger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])


# Response Schemas

class WorkflowStatsResponse(BaseModel):
    """Workflow statistics response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    total: int
    by_status: dict[str, int]
    recently_created: int
    recent_period_days: int
    most_active: list[dict]


class ExecutionStatsResponse(BaseModel):
    """Execution statistics response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    total: int
    by_status: dict[str, int]
    success_rate: float
    avg_duration_seconds: float
    daily_counts: list[dict]
    recent_failures: list[dict]
    period_days: int


class AuditActivityResponse(BaseModel):
    """Audit activity response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    total_actions: int
    by_action: dict[str, int]
    by_resource: dict[str, int]
    recent_activity: list[dict]
    period_days: int


class SystemHealthResponse(BaseModel):
    """System health response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    health_score: int
    status: str
    inactive_active_workflows: int
    recent_failures_24h: int
    recommendations: list[str]


class DashboardSummaryResponse(BaseModel):
    """Complete dashboard summary response."""
    
    model_config = ConfigDict(from_attributes=True)
    
    workflows: WorkflowStatsResponse
    executions: ExecutionStatsResponse
    audit: AuditActivityResponse
    health: SystemHealthResponse
    generated_at: str


@router.get("/dashboard", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get complete dashboard summary with all metrics.
    
    Returns a consolidated view of:
    - Workflow statistics
    - Execution metrics
    - Audit activity
    - System health score
    """
    summary = await AnalyticsService.get_dashboard_summary(
        db=db,
        organization_id=user.organization_id,
    )
    return summary


@router.get("/workflows", response_model=WorkflowStatsResponse)
async def get_workflow_stats(
    db: DBSession,
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
) -> Any:
    """Get workflow statistics.
    
    Returns:
    - Total workflows count
    - Breakdown by status
    - Recently created workflows
    - Most active workflows
    """
    stats = await AnalyticsService.get_workflow_stats(
        db=db,
        organization_id=user.organization_id,
        days=days,
    )
    return stats


@router.get("/executions", response_model=ExecutionStatsResponse)
async def get_execution_stats(
    db: DBSession,
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
) -> Any:
    """Get execution statistics.
    
    Returns:
    - Total executions count
    - Breakdown by status
    - Success rate percentage
    - Average execution duration
    - Daily execution counts (for charts)
    - Recent failures
    """
    stats = await AnalyticsService.get_execution_stats(
        db=db,
        organization_id=user.organization_id,
        days=days,
    )
    return stats


@router.get("/audit", response_model=AuditActivityResponse)
async def get_audit_activity(
    db: DBSession,
    user: CurrentUser,
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
) -> Any:
    """Get audit activity statistics.
    
    Returns:
    - Total actions logged
    - Breakdown by action type
    - Breakdown by resource type
    - Recent activity stream
    """
    activity = await AnalyticsService.get_audit_activity(
        db=db,
        organization_id=user.organization_id,
        days=days,
    )
    return activity


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health(
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get system health metrics.
    
    Returns:
    - Health score (0-100)
    - Status (healthy/warning/critical)
    - Recommendations
    - Issues detected
    """
    health = await AnalyticsService.get_system_health(
        db=db,
        organization_id=user.organization_id,
    )
    return health


@router.get("/charts/executions")
async def get_execution_chart_data(
    db: DBSession,
    user: CurrentUser,
    days: int = Query(30, ge=7, le=90, description="Number of days for chart"),
) -> Any:
    """Get data for execution trend charts.
    
    Returns daily execution counts for chart visualization.
    """
    stats = await AnalyticsService.get_execution_stats(
        db=db,
        organization_id=user.organization_id,
        days=days,
    )
    
    return {
        "title": "Execuções Diárias",
        "type": "line",
        "labels": [d["date"] for d in stats["daily_counts"]],
        "datasets": [
            {
                "label": "Execuções",
                "data": [d["count"] for d in stats["daily_counts"]],
                "color": "#007bff",
            }
        ],
        "summary": {
            "total": stats["total"],
            "success_rate": stats["success_rate"],
            "avg_duration": stats["avg_duration_seconds"],
        },
    }


@router.get("/charts/status")
async def get_status_distribution(
    db: DBSession,
    user: CurrentUser,
) -> Any:
    """Get status distribution for pie/donut charts.
    
    Returns workflow and execution status distributions.
    """
    workflow_stats = await AnalyticsService.get_workflow_stats(
        db=db,
        organization_id=user.organization_id,
        days=7,
    )
    execution_stats = await AnalyticsService.get_execution_stats(
        db=db,
        organization_id=user.organization_id,
        days=7,
    )
    
    return {
        "workflows": {
            "title": "Workflows por Status",
            "type": "pie",
            "labels": list(workflow_stats["by_status"].keys()),
            "data": list(workflow_stats["by_status"].values()),
            "total": workflow_stats["total"],
        },
        "executions": {
            "title": "Execuções por Status (7 dias)",
            "type": "donut",
            "labels": list(execution_stats["by_status"].keys()),
            "data": list(execution_stats["by_status"].values()),
            "total": execution_stats["total"],
        },
    }
