"""Unit tests for workflow service."""

import pytest
import pytest_asyncio
from uuid import uuid4

from app.services.workflow_service import WorkflowService
from app.models.workflow import Workflow, WorkflowStatus
from app.models.workflow_step import WorkflowStep, StepType, ActionType


class TestWorkflowService:
    """Test workflow service functionality."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create workflow service instance."""
        return WorkflowService()

    async def test_create_workflow(self, db, service, test_org, test_user):
        """Test creating a workflow."""
        workflow = await service.create_workflow(
            db=db,
            name="Test Workflow",
            description="A test workflow",
            organization_id=test_org.id,
            created_by_id=test_user.id,
            trigger_type="manual",
        )

        assert workflow is not None
        assert workflow.name == "Test Workflow"
        assert workflow.description == "A test workflow"
        assert workflow.organization_id == test_org.id
        assert workflow.created_by_id == test_user.id
        assert workflow.status == WorkflowStatus.ACTIVE
        assert workflow.trigger_type == "manual"
        assert workflow.version == 1

    async def test_get_workflow_by_id(self, db, service, test_workflow):
        """Test getting workflow by ID."""
        result = await service.get_workflow_by_id(
            db=db,
            workflow_id=test_workflow.id,
            organization_id=test_workflow.organization_id,
        )

        assert result is not None
        assert result.id == test_workflow.id
        assert result.name == test_workflow.name

    async def test_get_workflow_not_found(self, db, service, test_org):
        """Test getting non-existent workflow."""
        result = await service.get_workflow_by_id(
            db=db,
            workflow_id=uuid4(),
            organization_id=test_org.id,
        )

        assert result is None

    async def test_update_workflow(self, db, service, test_workflow):
        """Test updating a workflow."""
        updated = await service.update_workflow(
            db=db,
            workflow_id=test_workflow.id,
            organization_id=test_workflow.organization_id,
            name="Updated Workflow",
            description="Updated description",
        )

        assert updated is not None
        assert updated.name == "Updated Workflow"
        assert updated.description == "Updated description"

    async def test_delete_workflow(self, db, service, test_workflow):
        """Test deleting a workflow."""
        result = await service.delete_workflow(
            db=db,
            workflow_id=test_workflow.id,
            organization_id=test_workflow.organization_id,
        )

        assert result is True

        # Verify workflow is deleted
        deleted = await service.get_workflow_by_id(
            db=db,
            workflow_id=test_workflow.id,
            organization_id=test_workflow.organization_id,
        )
        assert deleted is None

    async def test_list_workflows(self, db, service, test_org, test_user):
        """Test listing workflows."""
        # Create multiple workflows
        for i in range(3):
            await service.create_workflow(
                db=db,
                name=f"Workflow {i}",
                description=f"Description {i}",
                organization_id=test_org.id,
                created_by_id=test_user.id,
                trigger_type="manual",
            )

        workflows, total = await service.list_workflows(
            db=db,
            organization_id=test_org.id,
        )

        assert len(workflows) == 3
        assert total == 3

    async def test_list_workflows_with_search(self, db, service, test_org, test_user):
        """Test listing workflows with search filter."""
        await service.create_workflow(
            db=db,
            name="Searchable Workflow",
            description="Find me",
            organization_id=test_org.id,
            created_by_id=test_user.id,
            trigger_type="manual",
        )

        await service.create_workflow(
            db=db,
            name="Other Workflow",
            description="Not searchable",
            organization_id=test_org.id,
            created_by_id=test_user.id,
            trigger_type="manual",
        )

        workflows, total = await service.list_workflows(
            db=db,
            organization_id=test_org.id,
            search="Searchable",
        )

        assert len(workflows) == 1
        assert workflows[0].name == "Searchable Workflow"

    async def test_list_workflows_with_status_filter(self, db, service, test_org, test_user):
        """Test listing workflows with status filter."""
        active = await service.create_workflow(
            db=db,
            name="Active Workflow",
            description="Active",
            organization_id=test_org.id,
            created_by_id=test_user.id,
            trigger_type="manual",
        )
        active.status = WorkflowStatus.ACTIVE

        draft = await service.create_workflow(
            db=db,
            name="Draft Workflow",
            description="Draft",
            organization_id=test_org.id,
            created_by_id=test_user.id,
            trigger_type="manual",
        )
        draft.status = WorkflowStatus.DRAFT
        await db.commit()

        workflows, total = await service.list_workflows(
            db=db,
            organization_id=test_org.id,
            status="active",
        )

        assert all(w.status == WorkflowStatus.ACTIVE for w in workflows)


class TestWorkflowSteps:
    """Test workflow steps functionality."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create workflow service instance."""
        return WorkflowService()

    async def test_add_step_to_workflow(self, db, service, test_workflow):
        """Test adding a step to workflow."""
        step = await service.add_step(
            db=db,
            workflow_id=test_workflow.id,
            name="New Step",
            step_type=StepType.ACTION,
            action_type=ActionType.HTTP_REQUEST,
            order=1,
            config={"method": "POST", "url": "https://api.example.com"},
        )

        assert step is not None
        assert step.name == "New Step"
        assert step.workflow_id == test_workflow.id
        assert step.step_type == StepType.ACTION
        assert step.action_type == ActionType.HTTP_REQUEST
        assert step.order == 1

    async def test_get_workflow_steps(self, db, service, test_workflow_with_steps):
        """Test getting workflow steps."""
        steps = await service.get_workflow_steps(
            db=db,
            workflow_id=test_workflow_with_steps.id,
        )

        assert len(steps) == 2
        assert steps[0].step_type == StepType.TRIGGER
        assert steps[1].step_type == StepType.ACTION

    async def test_reorder_steps(self, db, service, test_workflow_with_steps):
        """Test reordering workflow steps."""
        steps = await service.get_workflow_steps(
            db=db,
            workflow_id=test_workflow_with_steps.id,
        )

        step_ids = [str(s.id) for s in steps]
        # Reverse order
        reversed_ids = list(reversed(step_ids))

        result = await service.reorder_steps(
            db=db,
            workflow_id=test_workflow_with_steps.id,
            step_ids=reversed_ids,
        )

        assert result is True

        # Verify new order
        updated_steps = await service.get_workflow_steps(
            db=db,
            workflow_id=test_workflow_with_steps.id,
        )

        orders = [s.order for s in updated_steps]
        assert orders == sorted(orders)

    async def test_delete_step(self, db, service, test_workflow_with_steps):
        """Test deleting a workflow step."""
        steps = await service.get_workflow_steps(
            db=db,
            workflow_id=test_workflow_with_steps.id,
        )

        initial_count = len(steps)
        step_to_delete = steps[1]  # Delete the action step

        result = await service.delete_step(
            db=db,
            workflow_id=test_workflow_with_steps.id,
            step_id=step_to_delete.id,
        )

        assert result is True

        # Verify step is deleted
        remaining = await service.get_workflow_steps(
            db=db,
            workflow_id=test_workflow_with_steps.id,
        )
        assert len(remaining) == initial_count - 1
