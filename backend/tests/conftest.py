"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import get_password_hash
from app.db.database import Base
from app.models.audit_log import AuditAction, AuditLog
from app.models.organization import Organization
from app.models.user import User, UserRole

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://workflow:workflow123@localhost:5432/workflow_automation_test"

# Create test engine
engine = create_async_engine(TEST_DATABASE_URL, echo=False, future=True)
TestSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    """Setup test database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db(setup_database) -> AsyncGenerator[AsyncSession, None]:
    """Get test database session."""
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@pytest_asyncio.fixture
async def test_org(db: AsyncSession) -> Organization:
    """Create test organization."""
    org = Organization(name="Test Org", slug="test-org")
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, test_org: Organization) -> User:
    """Create test user."""
    user = User(
        email="test@example.com",
        hashed_password=get_password_hash("test123"),
        full_name="Test User",
        role=UserRole.ADMIN,
        organization_id=test_org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_editor(db: AsyncSession, test_org: Organization) -> User:
    """Create test editor user."""
    user = User(
        email="editor@example.com",
        hashed_password=get_password_hash("editor123"),
        full_name="Test Editor",
        role=UserRole.EDITOR,
        organization_id=test_org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_viewer(db: AsyncSession, test_org: Organization) -> User:
    """Create test viewer user."""
    user = User(
        email="viewer@example.com",
        hashed_password=get_password_hash("viewer123"),
        full_name="Test Viewer",
        role=UserRole.VIEWER,
        organization_id=test_org.id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# Import workflow models
from app.models.workflow import Workflow, WorkflowStatus
from app.models.workflow_step import WorkflowStep, StepType, ActionType
from app.models.execution import WorkflowExecution, ExecutionStatus, ExecutionLog


@pytest_asyncio.fixture
async def test_workflow(db: AsyncSession, test_org: Organization, test_user: User) -> Workflow:
    """Create test workflow."""
    workflow = Workflow(
        name="Test Workflow",
        description="A test workflow",
        status=WorkflowStatus.ACTIVE,
        organization_id=test_org.id,
        created_by_id=test_user.id,
        trigger_type="manual",
        version=1,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


@pytest_asyncio.fixture
async def test_workflow_with_steps(
    db: AsyncSession, test_org: Organization, test_user: User
) -> Workflow:
    """Create test workflow with steps."""
    workflow = Workflow(
        name="Workflow with Steps",
        description="Workflow containing action steps",
        status=WorkflowStatus.ACTIVE,
        organization_id=test_org.id,
        created_by_id=test_user.id,
        trigger_type="manual",
        version=1,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    
    # Add trigger step
    trigger_step = WorkflowStep(
        workflow_id=workflow.id,
        name="Trigger",
        step_type=StepType.TRIGGER,
        order=0,
        config={"trigger_type": "manual"},
    )
    db.add(trigger_step)
    
    # Add action step
    action_step = WorkflowStep(
        workflow_id=workflow.id,
        name="HTTP Request",
        step_type=StepType.ACTION,
        action_type=ActionType.HTTP_REQUEST,
        order=1,
        config={"method": "GET", "url": "https://api.example.com/test"},
    )
    db.add(action_step)
    
    await db.commit()
    return workflow


@pytest_asyncio.fixture
async def test_execution(
    db: AsyncSession, test_workflow: Workflow
) -> WorkflowExecution:
    """Create test execution."""
    execution = WorkflowExecution(
        workflow_id=test_workflow.id,
        status=ExecutionStatus.COMPLETED,
        trigger_type="manual",
        input_data={"test": "data"},
        output_data={"result": "success"},
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    return execution


@pytest_asyncio.fixture
async def test_execution_with_logs(
    db: AsyncSession, test_workflow: Workflow
) -> WorkflowExecution:
    """Create test execution with step logs."""
    execution = WorkflowExecution(
        workflow_id=test_workflow.id,
        status=ExecutionStatus.COMPLETED,
        trigger_type="manual",
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    
    # Add step logs
    log1 = ExecutionLog(
        execution_id=execution.id,
        step_name="Trigger",
        status="completed",
        order=0,
        duration_ms=10,
    )
    log2 = ExecutionLog(
        execution_id=execution.id,
        step_name="HTTP Request",
        status="completed",
        order=1,
        duration_ms=250,
        output={"status_code": 200},
    )
    db.add_all([log1, log2])
    await db.commit()
    
    return execution
