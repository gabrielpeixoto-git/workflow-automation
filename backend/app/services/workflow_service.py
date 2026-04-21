"""Workflow service."""

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.schemas import WorkflowCreate, WorkflowUpdate
from app.core.logging_config import get_logger
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User
from app.models.workflow import (
    ActionType,
    StepType,
    TriggerType,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from app.services.version_service import VersionService

logger = get_logger(__name__)


class WorkflowService:
    """Workflow management service."""

    @staticmethod
    async def create_workflow(
        db: AsyncSession,
        user: User,
        data: WorkflowCreate,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Workflow:
        """Create a new workflow."""
        # Validate slug uniqueness
        result = await db.execute(
            select(Workflow).where(
                Workflow.organization_id == user.organization_id,
                Workflow.slug == data.slug,
                Workflow.deleted_at.is_(None),
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow slug already exists in this organization",
            )

        # Validate at least one trigger step
        triggers = [s for s in data.steps if s.step_type == "trigger"]
        if len(triggers) != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workflow must have exactly one trigger step",
            )

        # Create workflow
        workflow = Workflow(
            name=data.name,
            slug=data.slug,
            description=data.description,
            status=data.status,
            tags=data.tags,
            organization_id=user.organization_id,
            version=1,
        )
        db.add(workflow)
        await db.flush()

        # Create steps
        for step_data in data.steps:
            step = WorkflowStep(
                workflow_id=workflow.id,
                order=step_data.order,
                step_type=step_data.step_type,
                trigger_type=TriggerType(step_data.trigger_type) if step_data.trigger_type else None,
                action_type=ActionType(step_data.action_type) if step_data.action_type else None,
                name=step_data.name,
                description=step_data.description,
                config=step_data.config,
                is_active=step_data.is_active,
                max_retries=step_data.max_retries,
                retry_delay=step_data.retry_delay,
            )
            db.add(step)

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.WORKFLOW_CREATE,
            resource_type="workflow",
            resource_id=str(workflow.id),
            description=f"Created workflow: {data.name}",
            details={"slug": data.slug, "steps_count": len(data.steps)},
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)

        await db.commit()
        await db.refresh(workflow)
        
        # Create initial version
        await db.refresh(workflow, ["steps"])
        await VersionService.create_version(
            db=db,
            workflow=workflow,
            user=user,
            change_summary="Initial version",
            version_tag="v1.0",
        )

        logger.info("Workflow created: %s by user %s", workflow.id, user.id)
        return workflow

    @staticmethod
    async def get_workflows(
        db: AsyncSession,
        organization_id: uuid.UUID,
        status: WorkflowStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Workflow]:
        """Get workflows for organization."""
        query = (
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )

        if status:
            query = query.where(Workflow.status == status)

        query = query.order_by(Workflow.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_workflow(
        db: AsyncSession,
        workflow_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Workflow | None:
        """Get workflow by ID."""
        result = await db.execute(
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(
                Workflow.id == workflow_id,
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_workflow_by_slug(
        db: AsyncSession,
        slug: str,
        organization_id: uuid.UUID,
    ) -> Workflow | None:
        """Get workflow by slug."""
        result = await db.execute(
            select(Workflow)
            .options(selectinload(Workflow.steps))
            .where(
                Workflow.slug == slug,
                Workflow.organization_id == organization_id,
                Workflow.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def update_workflow(
        db: AsyncSession,
        workflow: Workflow,
        user: User,
        data: WorkflowUpdate,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Workflow:
        """Update workflow."""
        update_data = data.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(workflow, field, value)

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.WORKFLOW_UPDATE,
            resource_type="workflow",
            resource_id=str(workflow.id),
            description=f"Updated workflow: {workflow.name}",
            details=update_data,
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)

        await db.commit()
        await db.refresh(workflow)
        
        # Create new version
        await db.refresh(workflow, ["steps"])
        await VersionService.create_version(
            db=db,
            workflow=workflow,
            user=user,
            change_summary=f"Updated workflow: {', '.join(update_data.keys())}",
        )

        logger.info("Workflow updated: %s by user %s", workflow.id, user.id)
        return workflow

    @staticmethod
    async def delete_workflow(
        db: AsyncSession,
        workflow: Workflow,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Soft delete workflow."""
        workflow.soft_delete()

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.WORKFLOW_DELETE,
            resource_type="workflow",
            resource_id=str(workflow.id),
            description=f"Deleted workflow: {workflow.name}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)

        await db.commit()

        logger.info("Workflow deleted: %s by user %s", workflow.id, user.id)

    @staticmethod
    async def activate_workflow(
        db: AsyncSession,
        workflow: Workflow,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Workflow:
        """Activate workflow."""
        workflow.status = WorkflowStatus.ACTIVE

        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.WORKFLOW_ACTIVATE,
            resource_type="workflow",
            resource_id=str(workflow.id),
            description=f"Activated workflow: {workflow.name}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()

        logger.info("Workflow activated: %s", workflow.id)
        return workflow

    @staticmethod
    async def deactivate_workflow(
        db: AsyncSession,
        workflow: Workflow,
        user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Workflow:
        """Deactivate workflow."""
        workflow.status = WorkflowStatus.INACTIVE

        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.WORKFLOW_DEACTIVATE,
            resource_type="workflow",
            resource_id=str(workflow.id),
            description=f"Deactivated workflow: {workflow.name}",
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)
        await db.commit()

        logger.info("Workflow deactivated: %s", workflow.id)
        return workflow

    @staticmethod
    async def duplicate_workflow(
        db: AsyncSession,
        workflow: Workflow,
        user: User,
        new_name: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Workflow:
        """Duplicate workflow."""
        # Generate new slug
        base_slug = f"{workflow.slug}-copy"
        new_slug = base_slug
        counter = 1
        while True:
            result = await db.execute(
                select(Workflow).where(
                    Workflow.organization_id == user.organization_id,
                    Workflow.slug == new_slug,
                    Workflow.deleted_at.is_(None),
                )
            )
            if not result.scalar_one_or_none():
                break
            new_slug = f"{base_slug}-{counter}"
            counter += 1

        # Create new workflow
        new_workflow = Workflow(
            name=new_name or f"{workflow.name} (Copy)",
            slug=new_slug,
            description=workflow.description,
            status=WorkflowStatus.DRAFT,
            tags=workflow.tags.copy(),
            organization_id=user.organization_id,
            version=1,
        )
        db.add(new_workflow)
        await db.flush()

        # Copy steps
        for step in workflow.steps:
            new_step = WorkflowStep(
                workflow_id=new_workflow.id,
                order=step.order,
                step_type=step.step_type,
                trigger_type=step.trigger_type,
                action_type=step.action_type,
                name=step.name,
                description=step.description,
                config=step.config.copy(),
                is_active=step.is_active,
                max_retries=step.max_retries,
                retry_delay=step.retry_delay,
            )
            db.add(new_step)

        # Create audit log
        audit = AuditLog(
            user_id=user.id,
            user_email=user.email,
            action=AuditAction.WORKFLOW_DUPLICATE,
            resource_type="workflow",
            resource_id=str(new_workflow.id),
            description=f"Duplicated workflow from: {workflow.name}",
            details={"source_workflow_id": str(workflow.id)},
            ip_address=ip_address,
            user_agent=user_agent,
            organization_id=user.organization_id,
        )
        db.add(audit)

        await db.commit()
        await db.refresh(new_workflow)

        logger.info(
            "Workflow duplicated: %s -> %s",
            workflow.id,
            new_workflow.id,
        )
        return new_workflow
