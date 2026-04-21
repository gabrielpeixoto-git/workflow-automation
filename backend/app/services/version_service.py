"""Workflow versioning service."""

import copy
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.workflow import Workflow, WorkflowStep
from app.models.workflow_version import WorkflowDiff, WorkflowVersion
from app.models.user import User

logger = get_logger(__name__)


class VersionService:
    """Service for workflow versioning."""
    
    @staticmethod
    async def create_version(
        db: AsyncSession,
        workflow: Workflow,
        user: User,
        change_summary: str | None = None,
        version_tag: str | None = None,
    ) -> WorkflowVersion:
        """Create a new version of a workflow."""
        # Get next version number
        result = await db.execute(
            select(func.max(WorkflowVersion.version_number))
            .where(WorkflowVersion.workflow_id == workflow.id)
        )
        max_version = result.scalar() or 0
        next_version = max_version + 1
        
        # Serialize workflow data
        workflow_data = {
            "id": str(workflow.id),
            "name": workflow.name,
            "slug": workflow.slug,
            "description": workflow.description,
            "status": workflow.status.value if workflow.status else None,
            "trigger_type": workflow.trigger_type.value if workflow.trigger_type else None,
            "version": workflow.version,
            "configuration": workflow.configuration,
            "metadata": workflow.metadata,
        }
        
        # Serialize steps
        steps_data = []
        for step in workflow.steps:
            step_data = {
                "id": str(step.id),
                "name": step.name,
                "step_type": step.step_type.value if step.step_type else None,
                "action_type": step.action_type.value if step.action_type else None,
                "order": step.order,
                "is_active": step.is_active,
                "configuration": step.configuration,
                "condition": step.condition,
                "retry_policy": step.retry_policy,
            }
            steps_data.append(step_data)
        
        # Get previous version
        previous_version = None
        if next_version > 1:
            result = await db.execute(
                select(WorkflowVersion)
                .where(WorkflowVersion.workflow_id == workflow.id)
                .order_by(WorkflowVersion.version_number.desc())
                .limit(1)
            )
            previous_version = result.scalar_one_or_none()
        
        # Create version
        version = WorkflowVersion(
            workflow_id=workflow.id,
            organization_id=workflow.organization_id,
            created_by=user.id,
            version_number=next_version,
            version_tag=version_tag,
            change_summary=change_summary,
            workflow_data=workflow_data,
            steps_data=steps_data,
            previous_version_id=previous_version.id if previous_version else None,
            is_restored=False,
        )
        db.add(version)
        await db.commit()
        await db.refresh(version)
        
        logger.info(
            "Workflow version created",
            workflow_id=str(workflow.id),
            version=next_version,
            created_by=str(user.id),
        )
        
        # Calculate diff if there's a previous version
        if previous_version:
            await VersionService._create_diff(
                db, previous_version, version, workflow.id
            )
        
        return version
    
    @staticmethod
    async def _create_diff(
        db: AsyncSession,
        from_version: WorkflowVersion,
        to_version: WorkflowVersion,
        workflow_id: UUID,
    ) -> WorkflowDiff:
        """Create diff between two versions."""
        from_data = from_version.workflow_data
        to_data = to_version.workflow_data
        from_steps = {s["id"]: s for s in from_version.steps_data}
        to_steps = {s["id"]: s for s in to_version.steps_data}
        
        # Compare workflow fields
        workflow_changes = {}
        for key in set(from_data.keys()) | set(to_data.keys()):
            if key in ("configuration", "metadata"):
                # Deep compare for nested dicts
                from_val = from_data.get(key, {})
                to_val = to_data.get(key, {})
                if from_val != to_val:
                    workflow_changes[key] = {
                        "from": from_val,
                        "to": to_val,
                    }
            elif from_data.get(key) != to_data.get(key):
                workflow_changes[key] = {
                    "from": from_data.get(key),
                    "to": to_data.get(key),
                }
        
        # Compare steps
        steps_added = []
        steps_removed = []
        steps_modified = []
        
        # Find added and modified steps
        for step_id, step_data in to_steps.items():
            if step_id not in from_steps:
                steps_added.append({
                    "id": step_id,
                    "name": step_data.get("name"),
                    "step_type": step_data.get("step_type"),
                })
            elif from_steps[step_id] != step_data:
                # Find specific changes
                changes = {}
                for key in set(from_steps[step_id].keys()) | set(step_data.keys()):
                    if from_steps[step_id].get(key) != step_data.get(key):
                        changes[key] = {
                            "from": from_steps[step_id].get(key),
                            "to": step_data.get(key),
                        }
                steps_modified.append({
                    "id": step_id,
                    "name": step_data.get("name"),
                    "changes": changes,
                })
        
        # Find removed steps
        for step_id, step_data in from_steps.items():
            if step_id not in to_steps:
                steps_removed.append({
                    "id": step_id,
                    "name": step_data.get("name"),
                    "step_type": step_data.get("step_type"),
                })
        
        # Determine if major change
        is_major = bool(
            steps_added or
            steps_removed or
            workflow_changes.get("trigger_type") or
            workflow_changes.get("status")
        )
        
        total_changes = (
            len(workflow_changes) +
            len(steps_added) +
            len(steps_removed) +
            len(steps_modified)
        )
        
        diff = WorkflowDiff(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            workflow_id=workflow_id,
            workflow_changes=workflow_changes,
            steps_added=steps_added,
            steps_removed=steps_removed,
            steps_modified=steps_modified,
            total_changes=total_changes,
            is_major_change=is_major,
        )
        db.add(diff)
        await db.commit()
        
        return diff
    
    @staticmethod
    async def get_versions(
        db: AsyncSession,
        workflow_id: UUID,
        limit: int = 50,
    ) -> list[WorkflowVersion]:
        """Get version history for a workflow."""
        result = await db.execute(
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.version_number.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    @staticmethod
    async def get_version(
        db: AsyncSession,
        version_id: UUID,
    ) -> WorkflowVersion | None:
        """Get a specific version."""
        result = await db.execute(
            select(WorkflowVersion).where(WorkflowVersion.id == version_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_version_by_number(
        db: AsyncSession,
        workflow_id: UUID,
        version_number: int,
    ) -> WorkflowVersion | None:
        """Get a specific version by number."""
        result = await db.execute(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.workflow_id == workflow_id,
                WorkflowVersion.version_number == version_number,
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_diff(
        db: AsyncSession,
        from_version_id: UUID,
        to_version_id: UUID,
    ) -> WorkflowDiff | None:
        """Get diff between two versions."""
        result = await db.execute(
            select(WorkflowDiff)
            .where(
                WorkflowDiff.from_version_id == from_version_id,
                WorkflowDiff.to_version_id == to_version_id,
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def restore_version(
        db: AsyncSession,
        workflow: Workflow,
        version: WorkflowVersion,
        user: User,
    ) -> Workflow:
        """Restore workflow to a previous version."""
        # Update workflow from version data
        workflow_data = version.workflow_data
        workflow.name = workflow_data.get("name", workflow.name)
        workflow.description = workflow_data.get("description", workflow.description)
        workflow.configuration = workflow_data.get("configuration", workflow.configuration)
        workflow.metadata = workflow_data.get("metadata", workflow.metadata)
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()
        
        # Restore steps
        # First, mark existing steps as inactive
        for step in workflow.steps:
            step.is_active = False
        
        # Create new steps from version data
        for step_data in version.steps_data:
            new_step = WorkflowStep(
                workflow_id=workflow.id,
                organization_id=workflow.organization_id,
                name=step_data.get("name"),
                step_type=step_data.get("step_type"),
                action_type=step_data.get("action_type"),
                order=step_data.get("order"),
                is_active=step_data.get("is_active", True),
                configuration=step_data.get("configuration", {}),
                condition=step_data.get("condition"),
                retry_policy=step_data.get("retry_policy", {}),
            )
            db.add(new_step)
        
        # Create new version marking it as restored
        new_version = WorkflowVersion(
            workflow_id=workflow.id,
            organization_id=workflow.organization_id,
            created_by=user.id,
            version_number=version.version_number + 1,
            version_tag=f"restored-from-v{version.version_number}",
            change_summary=f"Restored from version {version.version_number}",
            workflow_data=workflow_data,
            steps_data=version.steps_data,
            previous_version_id=version.id,
            is_restored=True,
        )
        db.add(new_version)
        
        await db.commit()
        await db.refresh(workflow)
        
        logger.info(
            "Workflow version restored",
            workflow_id=str(workflow.id),
            from_version=version.version_number,
            new_version=new_version.version_number,
            restored_by=str(user.id),
        )
        
        return workflow
    
    @staticmethod
    async def compare_versions(
        db: AsyncSession,
        version1_id: UUID,
        version2_id: UUID,
    ) -> dict[str, Any]:
        """Compare two versions and return differences."""
        version1 = await VersionService.get_version(db, version1_id)
        version2 = await VersionService.get_version(db, version2_id)
        
        if not version1 or not version2:
            raise ValueError("One or both versions not found")
        
        # Try to get pre-computed diff
        diff = await VersionService.get_diff(db, version1_id, version2_id)
        if not diff:
            diff = await VersionService.get_diff(db, version2_id, version1_id)
        
        if diff:
            return {
                "from_version": version1.version_number,
                "to_version": version2.version_number,
                "workflow_changes": diff.workflow_changes,
                "steps_added": diff.steps_added,
                "steps_removed": diff.steps_removed,
                "steps_modified": diff.steps_modified,
                "total_changes": diff.total_changes,
                "is_major_change": diff.is_major_change,
            }
        
        # Compute diff on the fly if not pre-computed
        from_steps = {s["id"]: s for s in version1.steps_data}
        to_steps = {s["id"]: s for s in version2.steps_data}
        
        added = []
        removed = []
        modified = []
        
        for step_id, step_data in to_steps.items():
            if step_id not in from_steps:
                added.append({"id": step_id, "name": step_data.get("name")})
            elif from_steps[step_id] != step_data:
                modified.append({"id": step_id, "name": step_data.get("name")})
        
        for step_id, step_data in from_steps.items():
            if step_id not in to_steps:
                removed.append({"id": step_id, "name": step_data.get("name")})
        
        return {
            "from_version": version1.version_number,
            "to_version": version2.version_number,
            "steps_added": added,
            "steps_removed": removed,
            "steps_modified": modified,
            "total_changes": len(added) + len(removed) + len(modified),
        }
