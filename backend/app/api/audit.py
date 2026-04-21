"""Audit log API routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

from app.core.deps import CurrentUser, DBSession, RequireAdmin, RequireAuditView
from app.core.logging_config import get_logger
from app.models.audit_log import AuditLog, AuditAction

logger = get_logger(__name__)
router = APIRouter()


class AuditLogResponse(BaseModel):
    """Audit log response schema."""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    user_id: UUID | None
    user_email: str | None
    action: str
    resource_type: str | None
    resource_id: str | None
    description: str | None
    details: dict[str, Any] | None
    ip_address: str | None
    created_at: datetime


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    db: DBSession,
    user: RequireAuditView,
    action: AuditAction | None = Query(None, description="Filter by action type"),
    resource_type: str | None = Query(None, description="Filter by resource type (workflow, execution, user)"),
    resource_id: str | None = Query(None, description="Filter by specific resource ID"),
    user_email: str | None = Query(None, description="Filter by user email"),
    limit: int = Query(50, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> Any:
    """List audit logs for the current user's organization.
    
    Returns a chronological list of all actions performed in the system,
    including who performed the action, what was affected, and when.
    
    **Common actions:**
    - `workflow_create`, `workflow_update`, `workflow_delete`
    - `execution_start`, `execution_complete`, `execution_fail`
    - `user_create`, `user_update`, `user_delete`
    - `login`, `logout`
    """
    query = (
        select(AuditLog)
        .where(AuditLog.organization_id == user.organization_id)
        .order_by(desc(AuditLog.created_at))
    )
    
    # Apply filters
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditLog.resource_id == resource_id)
    if user_email:
        query = query.where(AuditLog.user_email.ilike(f"%{user_email}%"))
    
    # Apply pagination
    query = query.offset(offset).limit(limit)
    
    result = await db.execute(query)
    logs = result.scalars().all()
    
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "user_email": log.user_email,
            "action": log.action.value if log.action else None,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "description": log.description,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.get("/audit-logs/stats")
async def get_audit_stats(
    db: DBSession,
    user: RequireAuditView,
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
) -> Any:
    """Get audit log statistics for the organization.
    
    Returns summary statistics including:
    - Total actions in the period
    - Actions by type
    - Most active users
    """
    from datetime import timedelta
    from sqlalchemy import func
    
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    # Total actions
    total_result = await db.execute(
        select(func.count(AuditLog.id))
        .where(
            AuditLog.organization_id == user.organization_id,
            AuditLog.created_at >= cutoff_date,
        )
    )
    total = total_result.scalar() or 0
    
    # Actions by type
    actions_result = await db.execute(
        select(AuditLog.action, func.count(AuditLog.id))
        .where(
            AuditLog.organization_id == user.organization_id,
            AuditLog.created_at >= cutoff_date,
        )
        .group_by(AuditLog.action)
        .order_by(func.count(AuditLog.id).desc())
    )
    actions_by_type = [
        {"action": action.value if action else None, "count": count}
        for action, count in actions_result.all()
    ]
    
    # Top users
    users_result = await db.execute(
        select(AuditLog.user_email, func.count(AuditLog.id))
        .where(
            AuditLog.organization_id == user.organization_id,
            AuditLog.created_at >= cutoff_date,
            AuditLog.user_email.isnot(None),
        )
        .group_by(AuditLog.user_email)
        .order_by(func.count(AuditLog.id).desc())
        .limit(5)
    )
    top_users = [
        {"email": email, "count": count}
        for email, count in users_result.all()
    ]
    
    return {
        "period_days": days,
        "total_actions": total,
        "actions_by_type": actions_by_type,
        "top_users": top_users,
    }


@router.get("/audit-logs/resource/{resource_type}/{resource_id}")
async def get_resource_history(
    resource_type: str,
    resource_id: str,
    db: DBSession,
    user: RequireAuditView,
    limit: int = Query(20, ge=1, le=50),
) -> Any:
    """Get complete history for a specific resource.
    
    Useful for tracking all changes made to a workflow, user, or execution.
    """
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.organization_id == user.organization_id,
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id,
        )
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    logs = result.scalars().all()
    
    if not logs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No audit logs found for {resource_type} {resource_id}",
        )
    
    return [
        {
            "id": log.id,
            "user_id": log.user_id,
            "user_email": log.user_email,
            "action": log.action.value if log.action else None,
            "description": log.description,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log in logs
    ]
