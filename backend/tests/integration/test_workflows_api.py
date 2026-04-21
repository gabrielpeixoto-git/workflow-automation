"""Integration tests for Workflows API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.workflow import Workflow, WorkflowStatus
from app.models.workflow_step import WorkflowStep, StepType


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
async def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    from app.core.security import create_access_token
    
    token = create_access_token({"sub": str(test_user.id), "email": test_user.email})
    return {"Authorization": f"Bearer {token}"}


class TestWorkflowsList:
    """Test listing workflows endpoint."""

    @pytest.mark.asyncio
    async def test_list_workflows_empty(self, client, auth_headers):
        """Test listing workflows when empty."""
        response = client.get("/api/workflows", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_workflows_with_data(
        self, client, auth_headers, db: AsyncSession, test_org, test_user
    ):
        """Test listing workflows with data."""
        # Create test workflow
        workflow = Workflow(
            name="Test Workflow",
            description="Test description",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
        )
        db.add(workflow)
        await db.commit()

        response = client.get("/api/workflows", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "Test Workflow"

    @pytest.mark.asyncio
    async def test_list_workflows_unauthorized(self, client):
        """Test listing workflows without auth."""
        response = client.get("/api/workflows")
        
        assert response.status_code == 401


class TestWorkflowCreate:
    """Test creating workflows."""

    @pytest.mark.asyncio
    async def test_create_workflow_success(self, client, auth_headers):
        """Test creating a workflow successfully."""
        workflow_data = {
            "name": "New Workflow",
            "description": "A test workflow",
            "trigger_type": "manual",
        }
        
        response = client.post(
            "/api/workflows",
            json=workflow_data,
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Workflow"
        assert data["status"] == "active"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_workflow_duplicate_name(self, client, auth_headers, db, test_org, test_user):
        """Test creating workflow with duplicate name."""
        # First workflow
        workflow = Workflow(
            name="Unique Workflow",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
        )
        db.add(workflow)
        await db.commit()

        # Try to create another with same name
        workflow_data = {
            "name": "Unique Workflow",
            "description": "Another workflow",
            "trigger_type": "manual",
        }
        
        response = client.post(
            "/api/workflows",
            json=workflow_data,
            headers=auth_headers,
        )
        
        assert response.status_code == 400
        assert "já existe" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_workflow_invalid_data(self, client, auth_headers):
        """Test creating workflow with invalid data."""
        workflow_data = {
            "name": "",  # Empty name
            "trigger_type": "manual",
        }
        
        response = client.post(
            "/api/workflows",
            json=workflow_data,
            headers=auth_headers,
        )
        
        assert response.status_code == 422  # Validation error


class TestWorkflowGet:
    """Test getting single workflow."""

    @pytest.mark.asyncio
    async def test_get_workflow_success(
        self, client, auth_headers, db, test_org, test_user
    ):
        """Test getting a workflow by ID."""
        workflow = Workflow(
            name="Get Test Workflow",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        response = client.get(f"/api/workflows/{workflow.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test Workflow"

    @pytest.mark.asyncio
    async def test_get_workflow_not_found(self, client, auth_headers):
        """Test getting non-existent workflow."""
        fake_id = "12345678-1234-1234-1234-123456789abc"
        response = client.get(f"/api/workflows/{fake_id}", headers=auth_headers)
        
        assert response.status_code == 404


class TestWorkflowUpdate:
    """Test updating workflows."""

    @pytest.mark.asyncio
    async def test_update_workflow_success(
        self, client, auth_headers, db, test_org, test_user
    ):
        """Test updating a workflow."""
        workflow = Workflow(
            name="Original Name",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        update_data = {"name": "Updated Name"}
        
        response = client.patch(
            f"/api/workflows/{workflow.id}",
            json=update_data,
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"


class TestWorkflowDelete:
    """Test deleting workflows."""

    @pytest.mark.asyncio
    async def test_delete_workflow_success(
        self, client, auth_headers, db, test_org, test_user
    ):
        """Test soft-deleting a workflow."""
        workflow = Workflow(
            name="To Delete",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        response = client.delete(
            f"/api/workflows/{workflow.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        
        # Verify it's marked as deleted
        await db.refresh(workflow)
        assert workflow.status == WorkflowStatus.ARCHIVED


class TestWorkflowDuplicate:
    """Test duplicating workflows."""

    @pytest.mark.asyncio
    async def test_duplicate_workflow_success(
        self, client, auth_headers, db, test_org, test_user
    ):
        """Test duplicating a workflow."""
        workflow = Workflow(
            name="Original Workflow",
            description="Original description",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
            version=1,
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        response = client.post(
            f"/api/workflows/{workflow.id}/duplicate",
            headers=auth_headers,
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Original Workflow (Cópia)"
        assert data["description"] == "Original description"
        assert data["version"] == 1


class TestWorkflowExecute:
    """Test executing workflows."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Celery worker")
    async def test_execute_workflow_manual(
        self, client, auth_headers, db, test_org, test_user
    ):
        """Test manual workflow execution."""
        workflow = Workflow(
            name="Executable Workflow",
            status=WorkflowStatus.ACTIVE,
            organization_id=test_org.id,
            created_by_id=test_user.id,
            trigger_type="manual",
        )
        db.add(workflow)
        await db.commit()
        await db.refresh(workflow)

        response = client.post(
            f"/api/workflows/{workflow.id}/execute",
            json={"payload": {"test": "data"}},
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "execution_id" in data
        assert data["status"] == "pending"
