"""Bulk operations service for workflows."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus

logger = get_logger(__name__)


class BulkAction(str, Enum):
    """Available bulk actions."""
    
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"
    DELETE = "delete"
    TAG_ADD = "tag_add"
    TAG_REMOVE = "tag_remove"
    CLONE = "clone"


class BulkOperationResult:
    """Result of a bulk operation."""
    
    def __init__(
        self,
        action: BulkAction,
        total: int,
        successful: int,
        failed: int,
        errors: list[dict],
        details: dict[str, Any] | None = None,
    ):
        self.action = action
        self.total = total
        self.successful = successful
        self.failed = failed
        self.errors = errors
        self.details = details or {}
    
    def to_dict(self) -> dict:
        """Convert result to dictionary."""
        return {
            "action": self.action.value,
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": f"{(self.successful / self.total * 100):.1f}%" if self.total > 0 else "0%",
            "errors": self.errors,
            "details": self.details,
        }


class BulkService:
    """Service for bulk workflow operations."""
    
    @staticmethod
    async def execute_bulk_action(
        db: AsyncSession,
        user: User,
        workflow_ids: list[UUID],
        action: BulkAction,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **kwargs: Any,
    ) -> BulkOperationResult:
        """Execute a bulk action on multiple workflows.
        
        Args:
            db: Database session
            user: Current user
            workflow_ids: List of workflow IDs to process
            action: Bulk action to execute
            ip_address: Client IP address
            user_agent: Client user agent
            **kwargs: Additional parameters for specific actions
            
        Returns:
            BulkOperationResult with execution details
        """
        if not workflow_ids:
            return BulkOperationResult(
                action=action,
                total=0,
                successful=0,
                failed=0,
                errors=[],
            )
        
        # Limit to 100 workflows per operation
        if len(workflow_ids) > 100:
            workflow_ids = workflow_ids[:100]
            logger.warning(
                "Bulk operation limited to 100 workflows",
                requested_count=len(workflow_ids),
            )
        
        # Get workflows
        result = await db.execute(
            select(Workflow).where(
                Workflow.id.in_(workflow_ids),
                Workflow.organization_id == user.organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        workflows = result.scalars().all()
        
        if not workflows:
            return BulkOperationResult(
                action=action,
                total=0,
                successful=0,
                failed=0,
                errors=[{"message": "No workflows found for the given IDs"}],
            )
        
        # Execute action
        errors = []
        successful = 0
        details = {}
        
        for workflow in workflows:
            try:
                await BulkService._execute_single_action(
                    db=db,
                    workflow=workflow,
                    action=action,
                    user=user,
                    **kwargs,
                )
                successful += 1
            except Exception as e:
                logger.error(
                    "Bulk action failed for workflow",
                    workflow_id=str(workflow.id),
                    action=action.value,
                    error=str(e),
                )
                errors.append({
                    "workflow_id": str(workflow.id),
                    "workflow_name": workflow.name,
                    "error": str(e),
                })
        
        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.BULK_ACTION,
            resource_type="workflow",
            resource_id=",".join([str(w.id) for w in workflows]),
            description=f"Bulk {action.value} on {len(workflows)} workflows",
            details={
                "action": action.value,
                "total": len(workflows),
                "successful": successful,
                "failed": len(errors),
            },
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()
        
        logger.info(
            "Bulk action completed",
            action=action.value,
            total=len(workflows),
            successful=successful,
            failed=len(errors),
        )
        
        return BulkOperationResult(
            action=action,
            total=len(workflows),
            successful=successful,
            failed=len(errors),
            errors=errors,
            details=details,
        )
    
    @staticmethod
    async def _execute_single_action(
        db: AsyncSession,
        workflow: Workflow,
        action: BulkAction,
        user: User,
        **kwargs: Any,
    ) -> None:
        """Execute a single action on a workflow."""
        if action == BulkAction.ACTIVATE:
            workflow.status = WorkflowStatus.ACTIVE
            workflow.updated_at = datetime.utcnow()
            
        elif action == BulkAction.DEACTIVATE:
            workflow.status = WorkflowStatus.INACTIVE
            workflow.updated_at = datetime.utcnow()
            
        elif action == BulkAction.DELETE:
            workflow.soft_delete()
            
        elif action == BulkAction.TAG_ADD:
            tags_to_add = kwargs.get("tags", [])
            if tags_to_add:
                current_tags = set(workflow.tags or [])
                current_tags.update(tags_to_add)
                workflow.tags = list(current_tags)
                workflow.updated_at = datetime.utcnow()
                
        elif action == BulkAction.TAG_REMOVE:
            tags_to_remove = kwargs.get("tags", [])
            if tags_to_remove and workflow.tags:
                current_tags = set(workflow.tags)
                current_tags.difference_update(tags_to_remove)
                workflow.tags = list(current_tags)
                workflow.updated_at = datetime.utcnow()
                
        elif action == BulkAction.CLONE:
            # Create clone with "_copy" suffix
            new_slug = f"{workflow.slug}_copy"
            
            # Check if slug already exists and append number
            counter = 1
            base_slug = new_slug
            while await BulkService._slug_exists(db, new_slug, workflow.organization_id):
                new_slug = f"{base_slug}_{counter}"
                counter += 1
            
            # Create new workflow
            cloned = Workflow(
                name=f"{workflow.name} (Copy)",
                slug=new_slug,
                description=workflow.description,
                status=WorkflowStatus.INACTIVE,  # Start inactive
                organization_id=workflow.organization_id,
                tags=workflow.tags,
            )
            db.add(cloned)
            await db.flush()
            
            # Clone steps
            from app.models.workflow import WorkflowStep
            for step in workflow.steps:
                new_step = WorkflowStep(
                    workflow_id=cloned.id,
                    organization_id=workflow.organization_id,
                    step_type=step.step_type,
                    action_type=step.action_type,
                    name=step.name,
                    order=step.order,
                    configuration=step.configuration,
                    condition=step.condition,
                    is_active=step.is_active,
                )
                db.add(new_step)
            
            await db.flush()
        
        else:
            raise ValueError(f"Unknown bulk action: {action}")
        
        await db.flush()
    
    @staticmethod
    async def _slug_exists(
        db: AsyncSession,
        slug: str,
        organization_id: UUID,
    ) -> bool:
        """Check if a workflow slug already exists."""
        result = await db.execute(
            select(Workflow).where(
                Workflow.slug == slug,
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none() is not None
    
    @staticmethod
    async def get_bulk_action_preview(
        db: AsyncSession,
        user: User,
        workflow_ids: list[UUID],
        action: BulkAction,
    ) -> dict[str, Any]:
        """Get a preview of what a bulk action would affect.
        
        Returns information about the workflows that would be affected
        without actually executing the action.
        """
        if not workflow_ids:
            return {
                "action": action.value,
                "total": 0,
                "workflows": [],
                "warning": "No workflow IDs provided",
            }
        
        # Limit to 100
        workflow_ids = workflow_ids[:100]
        
        # Get workflows
        result = await db.execute(
            select(Workflow).where(
                Workflow.id.in_(workflow_ids),
                Workflow.organization_id == user.organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        workflows = result.scalars().all()
        
        # Count by status
        status_counts = {}
        for wf in workflows:
            status = wf.status.value if wf.status else "unknown"
            status_counts[status] = status_counts.get(status, 0) + 1
        
        return {
            "action": action.value,
            "total": len(workflows),
            "requested": len(workflow_ids),
            "found": len(workflows),
            "not_found": len(workflow_ids) - len(workflows),
            "status_breakdown": status_counts,
            "workflows": [
                {
                    "id": str(wf.id),
                    "name": wf.name,
                    "slug": wf.slug,
                    "status": wf.status.value if wf.status else "unknown",
                }
                for wf in workflows
            ],
        }


# Add missing AuditAction
setattr(AuditAction, "BULK_ACTION", "bulk_action")
