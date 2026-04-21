"""Analytics service for dashboard metrics and insights."""

from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.audit_log import AuditAction, AuditLog
from app.models.execution import ExecutionStatus, WorkflowExecution
from app.models.workflow import Workflow, WorkflowStatus
from app.services.cache_service import CacheKeys, CacheTTL, cache

logger = get_logger(__name__)


class AnalyticsService:
    """Service for computing analytics and metrics."""

    @staticmethod
    @cache.cached(CacheKeys.ANALYTICS, ttl=CacheTTL.ANALYTICS)
    async def get_workflow_stats(
        db: AsyncSession,
        organization_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get workflow statistics for the organization."""
        # Total workflows
        result = await db.execute(
            select(func.count(Workflow.id)).where(
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        total_workflows = result.scalar() or 0
        
        # By status
        result = await db.execute(
            select(Workflow.status, func.count(Workflow.id))
            .where(
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
            .group_by(Workflow.status)
        )
        status_counts = {str(row[0]): row[1] for row in result.all()}
        
        # Recently created
        recent_date = datetime.utcnow() - timedelta(days=days)
        result = await db.execute(
            select(func.count(Workflow.id)).where(
                Workflow.organization_id == organization_id,
                Workflow.created_at >= recent_date,
                Workflow.deleted_at.is_(None),
            )
        )
        recently_created = result.scalar() or 0
        
        # Most active workflows (most executions)
        result = await db.execute(
            select(
                Workflow.id,
                Workflow.name,
                func.count(WorkflowExecution.id).label("execution_count"),
            )
            .join(WorkflowExecution, Workflow.id == WorkflowExecution.workflow_id)
            .where(
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
            .group_by(Workflow.id, Workflow.name)
            .order_by(func.count(WorkflowExecution.id).desc())
            .limit(5)
        )
        most_active = [
            {
                "id": str(row[0]),
                "name": row[1],
                "execution_count": row[2],
            }
            for row in result.all()
        ]
        
        return {
            "total": total_workflows,
            "by_status": status_counts,
            "recently_created": recently_created,
            "recent_period_days": days,
            "most_active": most_active,
        }
    
    @staticmethod
    @cache.cached(CacheKeys.ANALYTICS, ttl=CacheTTL.ANALYTICS)
    async def get_execution_stats(
        db: AsyncSession,
        organization_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get execution statistics for the organization."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Total executions
        result = await db.execute(
            select(func.count(WorkflowExecution.id)).where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= since,
            )
        )
        total_executions = result.scalar() or 0
        
        # By status
        result = await db.execute(
            select(WorkflowExecution.status, func.count(WorkflowExecution.id))
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= since,
            )
            .group_by(WorkflowExecution.status)
        )
        status_counts = {str(row[0]): row[1] for row in result.all()}
        
        # Success rate
        completed = status_counts.get(ExecutionStatus.COMPLETED.value, 0)
        failed = status_counts.get(ExecutionStatus.FAILED.value, 0)
        total_completed_or_failed = completed + failed
        success_rate = (completed / total_completed_or_failed * 100) if total_completed_or_failed > 0 else 0
        
        # Average duration
        result = await db.execute(
            select(func.avg(WorkflowExecution.duration_seconds)).where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= since,
                WorkflowExecution.duration_seconds.isnot(None),
            )
        )
        avg_duration = result.scalar() or 0
        
        # Daily execution counts (for chart)
        result = await db.execute(
            select(
                func.date_trunc('day', WorkflowExecution.created_at).label("day"),
                func.count(WorkflowExecution.id).label("count"),
            )
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.created_at >= since,
            )
            .group_by(func.date_trunc('day', WorkflowExecution.created_at))
            .order_by(func.date_trunc('day', WorkflowExecution.created_at))
        )
        daily_counts = [
            {
                "date": row[0].strftime("%Y-%m-%d") if row[0] else None,
                "count": row[1],
            }
            for row in result.all()
        ]
        
        # Recent failed executions
        result = await db.execute(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.status == ExecutionStatus.FAILED,
                WorkflowExecution.created_at >= since,
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(5)
        )
        recent_failures = result.scalars().all()
        
        return {
            "total": total_executions,
            "by_status": status_counts,
            "success_rate": round(success_rate, 2),
            "avg_duration_seconds": round(avg_duration, 2),
            "daily_counts": daily_counts,
            "recent_failures": [
                {
                    "id": str(exec.id),
                    "workflow_id": str(exec.workflow_id),
                    "error": (exec.error_message or "Unknown")[:100],
                    "created_at": exec.created_at.isoformat() if exec.created_at else None,
                }
                for exec in recent_failures
            ],
            "period_days": days,
        }
    
    @staticmethod
    async def get_audit_activity(
        db: AsyncSession,
        organization_id: UUID,
        days: int = 30,
    ) -> dict[str, Any]:
        """Get audit activity statistics."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Total actions
        result = await db.execute(
            select(func.count(AuditLog.id)).where(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= since,
            )
        )
        total_actions = result.scalar() or 0
        
        # By action type
        result = await db.execute(
            select(AuditLog.action, func.count(AuditLog.id))
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= since,
            )
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.id).desc())
        )
        action_counts = {str(row[0]): row[1] for row in result.all()}
        
        # By resource type
        result = await db.execute(
            select(AuditLog.resource_type, func.count(AuditLog.id))
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= since,
            )
            .group_by(AuditLog.resource_type)
            .order_by(func.count(AuditLog.id).desc())
        )
        resource_counts = {row[0] or "unknown": row[1] for row in result.all()}
        
        # Recent activity
        result = await db.execute(
            select(AuditLog)
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= since,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(10)
        )
        recent_activity = result.scalars().all()
        
        return {
            "total_actions": total_actions,
            "by_action": action_counts,
            "by_resource": resource_counts,
            "recent_activity": [
                {
                    "id": str(log.id),
                    "user_email": log.user_email or "Sistema",
                    "action": log.action.value if log.action else "unknown",
                    "resource_type": log.resource_type or "-",
                    "description": (log.description or "-")[:50],
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in recent_activity
            ],
            "period_days": days,
        }
    
    @staticmethod
    async def get_system_health(
        db: AsyncSession,
        organization_id: UUID,
    ) -> dict[str, Any]:
        """Get system health metrics."""
        # Active workflows with no recent executions
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        
        result = await db.execute(
            select(Workflow)
            .where(
                Workflow.organization_id == organization_id,
                Workflow.status == WorkflowStatus.ACTIVE,
                Workflow.deleted_at.is_(None),
            )
            .outerjoin(
                WorkflowExecution,
                (Workflow.id == WorkflowExecution.workflow_id) &
                (WorkflowExecution.created_at >= one_week_ago)
            )
            .group_by(Workflow.id)
            .having(func.count(WorkflowExecution.id) == 0)
        )
        inactive_active_workflows = result.scalars().all()
        
        # Failed executions in last 24 hours
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        result = await db.execute(
            select(func.count(WorkflowExecution.id)).where(
                WorkflowExecution.organization_id == organization_id,
                WorkflowExecution.status == ExecutionStatus.FAILED,
                WorkflowExecution.created_at >= one_day_ago,
            )
        )
        recent_failures = result.scalar() or 0
        
        # Health score (0-100)
        # Based on: workflows active, low failure rate, recent activity
        result = await db.execute(
            select(Workflow).where(
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        all_workflows = result.scalars().all()
        
        if not all_workflows:
            health_score = 100  # No workflows = healthy
        else:
            active_count = sum(1 for w in all_workflows if w.status == WorkflowStatus.ACTIVE)
            active_ratio = active_count / len(all_workflows)
            
            # Get recent execution stats
            result = await db.execute(
                select(func.count(WorkflowExecution.id)).where(
                    WorkflowExecution.organization_id == organization_id,
                    WorkflowExecution.created_at >= one_day_ago,
                )
            )
            recent_execs = result.scalar() or 0
            
            # Simple health calculation
            health_score = min(100, int(
                (active_ratio * 50) +  # 50% based on active workflows
                (50 if recent_execs > 0 else 25)  # 50% based on activity
            ))
        
        return {
            "health_score": health_score,
            "status": "healthy" if health_score >= 70 else "warning" if health_score >= 40 else "critical",
            "inactive_active_workflows": len(inactive_active_workflows),
            "recent_failures_24h": recent_failures,
            "recommendations": [
                "Sistema funcionando normalmente" if health_score >= 70 else
                "Verifique workflows ativos sem execuções recentes" if inactive_active_workflows else
                "Monitore as falhas recentes de execução"
            ],
        }
    
    @staticmethod
    async def get_dashboard_summary(
        db: AsyncSession,
        organization_id: UUID,
    ) -> dict[str, Any]:
        """Get complete dashboard summary."""
        workflow_stats = await AnalyticsService.get_workflow_stats(db, organization_id, days=7)
        execution_stats = await AnalyticsService.get_execution_stats(db, organization_id, days=7)
        audit_activity = await AnalyticsService.get_audit_activity(db, organization_id, days=7)
        health = await AnalyticsService.get_system_health(db, organization_id)
        
        return {
            "workflows": workflow_stats,
            "executions": execution_stats,
            "audit": audit_activity,
            "health": health,
            "generated_at": datetime.utcnow().isoformat(),
        }
