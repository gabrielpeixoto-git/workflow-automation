"""Integration tests for Executions API."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta

from app.main import app
from app.models.workflow import Workflow, WorkflowStatus
from app.models.execution import WorkflowExecution, ExecutionStatus, ExecutionLog


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


@pytest.fixture
async def sample_workflow(db, test_org, test_user):
    """Create a sample workflow for tests."""
    workflow = Workflow(
        name="Sample Workflow",
        description="Test workflow",
        status=WorkflowStatus.ACTIVE,
        organization_id=test_org.id,
        created_by_id=test_user.id,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


class TestExecutionsList:
    """Test listing executions endpoint."""

    @pytest.mark.asyncio
    async def test_list_executions_empty(self, client, auth_headers):
        """Test listing executions when empty."""
        response = client.get("/api/executions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_executions_with_data(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test listing executions with data."""
        # Create test executions
        for i in range(3):
            execution = WorkflowExecution(
                workflow_id=sample_workflow.id,
                status=ExecutionStatus.COMPLETED if i < 2 else ExecutionStatus.FAILED,
                trigger_type="manual",
                started_at=datetime.utcnow() - timedelta(hours=i),
            )
            db.add(execution)
        await db.commit()

        response = client.get("/api/executions", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    @pytest.mark.asyncio
    async def test_list_executions_pagination(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test pagination in executions list."""
        # Create 5 executions
        for i in range(5):
            execution = WorkflowExecution(
                workflow_id=sample_workflow.id,
                status=ExecutionStatus.COMPLETED,
                trigger_type="manual",
            )
            db.add(execution)
        await db.commit()

        # Request first 2
        response = client.get("/api/executions?limit=2&offset=0", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_executions_filter_by_status(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test filtering executions by status."""
        # Create executions with different statuses
        completed = WorkflowExecution(
            workflow_id=sample_workflow.id,
            status=ExecutionStatus.COMPLETED,
            trigger_type="manual",
        )
        failed = WorkflowExecution(
            workflow_id=sample_workflow.id,
            status=ExecutionStatus.FAILED,
            trigger_type="manual",
        )
        db.add_all([completed, failed])
        await db.commit()

        response = client.get("/api/executions?status=completed", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "completed"


class TestExecutionGet:
    """Test getting single execution."""

    @pytest.mark.asyncio
    async def test_get_execution_success(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test getting execution details."""
        execution = WorkflowExecution(
            workflow_id=sample_workflow.id,
            status=ExecutionStatus.COMPLETED,
            trigger_type="manual",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            output_data={"result": "success"},
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        response = client.get(
            f"/api/executions/{execution.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(execution.id)
        assert data["status"] == "completed"
        assert data["trigger_type"] == "manual"

    @pytest.mark.asyncio
    async def test_get_execution_with_logs(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test getting execution with step logs."""
        execution = WorkflowExecution(
            workflow_id=sample_workflow.id,
            status=ExecutionStatus.COMPLETED,
            trigger_type="manual",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        # Add logs
        log = ExecutionLog(
            execution_id=execution.id,
            step_name="Test Step",
            status="completed",
            output={"result": "ok"},
            duration_ms=150,
        )
        db.add(log)
        await db.commit()

        response = client.get(
            f"/api/executions/{execution.id}",
            headers=auth_headers,
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) == 1
        assert data["logs"][0]["step_name"] == "Test Step"
        assert data["logs"][0]["duration_ms"] == 150

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, client, auth_headers):
        """Test getting non-existent execution."""
        fake_id = "12345678-1234-1234-1234-123456789abc"
        response = client.get(f"/api/executions/{fake_id}", headers=auth_headers)
        
        assert response.status_code == 404


class TestExecutionRetry:
    """Test retrying failed executions."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Celery worker")
    async def test_retry_execution(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test retrying a failed execution."""
        execution = WorkflowExecution(
            workflow_id=sample_workflow.id,
            status=ExecutionStatus.FAILED,
            trigger_type="manual",
            error_message="Previous error",
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)

        response = client.post(
            f"/api/executions/{execution.id}/retry",
            headers=auth_headers,
        )
        
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "pending"


class TestExecutionStatistics:
    """Test execution statistics."""

    @pytest.mark.asyncio
    async def test_execution_statistics(
        self, client, auth_headers, db, sample_workflow
    ):
        """Test getting execution statistics."""
        # Create various executions
        statuses = [
            ExecutionStatus.COMPLETED,
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.PENDING,
        ]
        
        for status in statuses:
            execution = WorkflowExecution(
                workflow_id=sample_workflow.id,
                status=status,
                trigger_type="manual",
            )
            db.add(execution)
        await db.commit()

        response = client.get("/api/executions/stats", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_status" in data
        assert data["by_status"]["completed"] == 2
        assert data["by_status"]["failed"] == 1
        assert data["by_status"]["pending"] == 1
