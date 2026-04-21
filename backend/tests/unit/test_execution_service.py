"""Unit tests for execution service."""

import pytest
import pytest_asyncio
from datetime import datetime
from uuid import uuid4

from app.services.execution_service import ExecutionService
from app.models.execution import WorkflowExecution, ExecutionStatus, ExecutionLog


class TestExecutionService:
    """Test execution service functionality."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create execution service instance."""
        return ExecutionService()

    async def test_create_execution(self, db, service, test_workflow):
        """Test creating an execution."""
        execution = await service.create_execution(
            db=db,
            workflow_id=test_workflow.id,
            trigger_type="manual",
            input_data={"test": "data"},
            triggered_by_id=None,
        )

        assert execution is not None
        assert execution.workflow_id == test_workflow.id
        assert execution.status == ExecutionStatus.PENDING
        assert execution.trigger_type == "manual"
        assert execution.input_data == {"test": "data"}

    async def test_get_execution_by_id(self, db, service, test_execution):
        """Test getting execution by ID."""
        result = await service.get_execution_by_id(
            db=db,
            execution_id=test_execution.id,
            organization_id=test_execution.organization_id,
        )

        assert result is not None
        assert result.id == test_execution.id

    async def test_get_execution_not_found(self, db, service, test_org):
        """Test getting non-existent execution."""
        result = await service.get_execution_by_id(
            db=db,
            execution_id=uuid4(),
            organization_id=test_org.id,
        )

        assert result is None

    async def test_start_execution(self, db, service, test_execution):
        """Test starting an execution."""
        started = await service.start_execution(
            db=db,
            execution_id=test_execution.id,
        )

        assert started is not None
        assert started.status == ExecutionStatus.RUNNING
        assert started.started_at is not None

    async def test_complete_execution(self, db, service, test_execution):
        """Test completing an execution."""
        # First start the execution
        await service.start_execution(db=db, execution_id=test_execution.id)

        completed = await service.complete_execution(
            db=db,
            execution_id=test_execution.id,
            output_data={"result": "success"},
        )

        assert completed is not None
        assert completed.status == ExecutionStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.output_data == {"result": "success"}

    async def test_fail_execution(self, db, service, test_execution):
        """Test failing an execution."""
        # First start the execution
        await service.start_execution(db=db, execution_id=test_execution.id)

        failed = await service.fail_execution(
            db=db,
            execution_id=test_execution.id,
            error_message="Something went wrong",
        )

        assert failed is not None
        assert failed.status == ExecutionStatus.FAILED
        assert failed.completed_at is not None
        assert "Something went wrong" in str(failed.error_message)

    async def test_cancel_execution(self, db, service, test_execution):
        """Test cancelling an execution."""
        cancelled = await service.cancel_execution(
            db=db,
            execution_id=test_execution.id,
        )

        assert cancelled is not None
        assert cancelled.status == ExecutionStatus.CANCELLED

    async def test_list_executions(self, db, service, test_workflow):
        """Test listing executions."""
        # Create multiple executions
        for i in range(3):
            await service.create_execution(
                db=db,
                workflow_id=test_workflow.id,
                trigger_type="manual",
                input_data={"index": i},
            )

        executions, total = await service.list_executions(
            db=db,
            organization_id=test_workflow.organization_id,
        )

        assert len(executions) == 3
        assert total == 3

    async def test_list_executions_with_status_filter(self, db, service, test_workflow):
        """Test listing executions with status filter."""
        # Create executions with different statuses
        pending = await service.create_execution(
            db=db,
            workflow_id=test_workflow.id,
            trigger_type="manual",
            input_data={"status": "pending"},
        )

        completed = await service.create_execution(
            db=db,
            workflow_id=test_workflow.id,
            trigger_type="manual",
            input_data={"status": "completed"},
        )
        await service.start_execution(db=db, execution_id=completed.id)
        await service.complete_execution(db=db, execution_id=completed.id, output_data={})

        completed_execs, total = await service.list_executions(
            db=db,
            organization_id=test_workflow.organization_id,
            status="completed",
        )

        assert all(e.status == ExecutionStatus.COMPLETED for e in completed_execs)

    async def test_list_executions_with_workflow_filter(self, db, service, test_workflow):
        """Test listing executions filtered by workflow."""
        # Create execution for this workflow
        await service.create_execution(
            db=db,
            workflow_id=test_workflow.id,
            trigger_type="manual",
            input_data={},
        )

        executions, total = await service.list_executions(
            db=db,
            organization_id=test_workflow.organization_id,
            workflow_id=test_workflow.id,
        )

        assert len(executions) == 1
        assert executions[0].workflow_id == test_workflow.id

    async def test_get_execution_stats(self, db, service, test_workflow):
        """Test getting execution statistics."""
        # Create executions with different statuses
        for _ in range(5):
            exec_obj = await service.create_execution(
                db=db,
                workflow_id=test_workflow.id,
                trigger_type="manual",
                input_data={},
            )
            await service.start_execution(db=db, execution_id=exec_obj.id)
            await service.complete_execution(db=db, execution_id=exec_obj.id, output_data={})

        for _ in range(2):
            exec_obj = await service.create_execution(
                db=db,
                workflow_id=test_workflow.id,
                trigger_type="manual",
                input_data={},
            )
            await service.start_execution(db=db, execution_id=exec_obj.id)
            await service.fail_execution(db=db, execution_id=exec_obj.id, error_message="Error")

        stats = await service.get_execution_stats(
            db=db,
            organization_id=test_workflow.organization_id,
            workflow_id=test_workflow.id,
        )

        assert stats["total"] == 7
        assert stats["completed"] == 5
        assert stats["failed"] == 2
        assert stats["success_rate"] == pytest.approx(71.43, 0.01)


class TestExecutionLogs:
    """Test execution logging functionality."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create execution service instance."""
        return ExecutionService()

    async def test_add_execution_log(self, db, service, test_execution):
        """Test adding a log entry to execution."""
        log = await service.add_log(
            db=db,
            execution_id=test_execution.id,
            level="info",
            message="Test log message",
            step_id=None,
        )

        assert log is not None
        assert log.execution_id == test_execution.id
        assert log.level == "info"
        assert log.message == "Test log message"

    async def test_get_execution_logs(self, db, service, test_execution):
        """Test getting execution logs."""
        # Add multiple logs
        for i in range(3):
            await service.add_log(
                db=db,
                execution_id=test_execution.id,
                level="info",
                message=f"Log message {i}",
            )

        logs, total = await service.get_execution_logs(
            db=db,
            execution_id=test_execution.id,
        )

        assert len(logs) == 3
        assert total == 3

    async def test_get_execution_logs_with_level_filter(self, db, service, test_execution):
        """Test getting logs filtered by level."""
        await service.add_log(db=db, execution_id=test_execution.id, level="info", message="Info log")
        await service.add_log(db=db, execution_id=test_execution.id, level="error", message="Error log 1")
        await service.add_log(db=db, execution_id=test_execution.id, level="error", message="Error log 2")

        logs, total = await service.get_execution_logs(
            db=db,
            execution_id=test_execution.id,
            level="error",
        )

        assert len(logs) == 2
        assert all(l.level == "error" for l in logs)

    async def test_log_levels(self, db, service, test_execution):
        """Test different log levels."""
        levels = ["debug", "info", "warning", "error"]

        for level in levels:
            log = await service.add_log(
                db=db,
                execution_id=test_execution.id,
                level=level,
                message=f"{level} message",
            )
            assert log.level == level
