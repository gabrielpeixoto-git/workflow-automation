"""Workflow template service."""

import re
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.template import TemplateCategory, WorkflowTemplate, WorkflowTemplateUsage
from app.models.user import User
from app.models.workflow import Workflow, WorkflowStatus, WorkflowStep

logger = get_logger(__name__)


# Built-in templates data
BUILTIN_TEMPLATES = [
    {
        "slug": "email-notification",
        "name": "Email Notification",
        "description": "Send email notifications when specific events occur.",
        "category": TemplateCategory.NOTIFICATION.value,
        "trigger_type": "webhook",
        "icon": "mail",
        "color": "#007bff",
        "steps_configuration": [
            {
                "name": "Trigger",
                "step_type": "trigger",
                "action_type": "webhook",
                "order": 0,
                "configuration": {
                    "webhook_url": "{{trigger.webhook_url}}",
                    "method": "POST",
                },
            },
            {
                "name": "Send Email",
                "step_type": "action",
                "action_type": "email",
                "order": 1,
                "configuration": {
                    "to": "{{data.email}}",
                    "subject": "{{data.subject}}",
                    "body": "{{data.message}}",
                },
            },
        ],
        "tags": ["email", "notification", "alert"],
    },
    {
        "slug": "data-validation",
        "name": "Data Validation Pipeline",
        "description": "Validate incoming data against schema before processing.",
        "category": TemplateCategory.DATA_PROCESSING.value,
        "trigger_type": "api",
        "icon": "check-circle",
        "color": "#28a745",
        "steps_configuration": [
            {
                "name": "API Endpoint",
                "step_type": "trigger",
                "action_type": "api",
                "order": 0,
                "configuration": {
                    "endpoint": "/api/data/ingest",
                    "method": "POST",
                },
            },
            {
                "name": "Validate Schema",
                "step_type": "action",
                "action_type": "validate",
                "order": 1,
                "configuration": {
                    "schema": "{{template.schema}}",
                },
            },
            {
                "name": "Transform Data",
                "step_type": "action",
                "action_type": "transform",
                "order": 2,
                "configuration": {
                    "transformation": "{{template.transformation}}",
                },
            },
        ],
        "tags": ["validation", "data", "schema"],
    },
    {
        "slug": "webhook-integration",
        "name": "External Webhook Integration",
        "description": "Receive webhooks from external services and process them.",
        "category": TemplateCategory.INTEGRATION.value,
        "trigger_type": "webhook",
        "icon": "webhook",
        "color": "#ffc107",
        "steps_configuration": [
            {
                "name": "Webhook Trigger",
                "step_type": "trigger",
                "action_type": "webhook",
                "order": 0,
                "configuration": {
                    "secret": "{{webhook.secret}}",
                },
            },
            {
                "name": "Parse Payload",
                "step_type": "action",
                "action_type": "transform",
                "order": 1,
                "configuration": {
                    "mapping": "{{template.mapping}}",
                },
            },
            {
                "name": "Forward to API",
                "step_type": "action",
                "action_type": "api",
                "order": 2,
                "configuration": {
                    "url": "{{data.forward_url}}",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                },
            },
        ],
        "tags": ["webhook", "integration", "external"],
    },
    {
        "slug": "scheduled-cleanup",
        "name": "Scheduled Data Cleanup",
        "description": "Periodically clean up old data or temporary files.",
        "category": TemplateCategory.AUTOMATION.value,
        "trigger_type": "schedule",
        "icon": "clock",
        "color": "#dc3545",
        "steps_configuration": [
            {
                "name": "Schedule",
                "step_type": "trigger",
                "action_type": "schedule",
                "order": 0,
                "configuration": {
                    "cron": "0 2 * * *",  # Daily at 2 AM
                    "timezone": "UTC",
                },
            },
            {
                "name": "Delete Old Records",
                "step_type": "action",
                "action_type": "database",
                "order": 1,
                "configuration": {
                    "operation": "delete",
                    "table": "{{data.table}}",
                    "where": "created_at < NOW() - INTERVAL '{{data.days}} days'",
                },
            },
            {
                "name": "Log Cleanup",
                "step_type": "action",
                "action_type": "log",
                "order": 2,
                "configuration": {
                    "message": "Cleanup completed for {{data.table}}",
                    "level": "info",
                },
            },
        ],
        "tags": ["schedule", "cleanup", "maintenance"],
    },
    {
        "slug": "conditional-routing",
        "name": "Conditional Data Routing",
        "description": "Route data to different destinations based on conditions.",
        "category": TemplateCategory.AUTOMATION.value,
        "trigger_type": "webhook",
        "icon": "git-branch",
        "color": "#6f42c1",
        "steps_configuration": [
            {
                "name": "Trigger",
                "step_type": "trigger",
                "action_type": "webhook",
                "order": 0,
                "configuration": {},
            },
            {
                "name": "Route to Team A",
                "step_type": "action",
                "action_type": "email",
                "order": 1,
                "condition": "{{data.priority}} == 'high'",
                "configuration": {
                    "to": "team-a@example.com",
                    "subject": "High Priority: {{data.title}}",
                },
            },
            {
                "name": "Route to Team B",
                "step_type": "action",
                "action_type": "email",
                "order": 2,
                "condition": "{{data.priority}} == 'low'",
                "configuration": {
                    "to": "team-b@example.com",
                    "subject": "Low Priority: {{data.title}}",
                },
            },
        ],
        "tags": ["conditional", "routing", "logic"],
    },
]


class TemplateService:
    """Service for workflow template management."""
    
    @staticmethod
    async def initialize_builtin_templates(db: AsyncSession) -> None:
        """Initialize built-in templates in the database."""
        for template_data in BUILTIN_TEMPLATES:
            # Check if template already exists
            result = await db.execute(
                select(WorkflowTemplate).where(
                    WorkflowTemplate.slug == template_data["slug"],
                    WorkflowTemplate.is_builtin == True,
                )
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing template
                existing.name = template_data["name"]
                existing.description = template_data["description"]
                existing.category = template_data["category"]
                existing.trigger_type = template_data.get("trigger_type")
                existing.steps_configuration = template_data["steps_configuration"]
                existing.icon = template_data.get("icon")
                existing.color = template_data.get("color")
                existing.tags = template_data.get("tags", [])
                existing.is_active = True
            else:
                # Create new template
                template = WorkflowTemplate(
                    slug=template_data["slug"],
                    name=template_data["name"],
                    description=template_data["description"],
                    category=template_data["category"],
                    trigger_type=template_data.get("trigger_type"),
                    steps_configuration=template_data["steps_configuration"],
                    icon=template_data.get("icon"),
                    color=template_data.get("color"),
                    tags=template_data.get("tags", []),
                    is_builtin=True,
                    is_active=True,
                )
                db.add(template)
        
        await db.commit()
        logger.info("Built-in templates initialized")
    
    @staticmethod
    async def get_templates(
        db: AsyncSession,
        organization_id: UUID | None,
        category: str | None = None,
        search: str | None = None,
        include_builtin: bool = True,
    ) -> list[WorkflowTemplate]:
        """Get available templates for an organization."""
        query = select(WorkflowTemplate).where(
            WorkflowTemplate.is_active == True
        )
        
        # Filter by organization or built-in
        if include_builtin and organization_id:
            query = query.where(
                or_(
                    WorkflowTemplate.organization_id == organization_id,
                    WorkflowTemplate.is_builtin == True,
                )
            )
        elif organization_id:
            query = query.where(WorkflowTemplate.organization_id == organization_id)
        else:
            query = query.where(WorkflowTemplate.is_builtin == True)
        
        # Filter by category
        if category:
            query = query.where(WorkflowTemplate.category == category)
        
        # Search by name or description
        if search:
            search_term = f"%{search}%"
            query = query.where(
                or_(
                    WorkflowTemplate.name.ilike(search_term),
                    WorkflowTemplate.description.ilike(search_term),
                )
            )
        
        # Order by built-in first, then usage count
        query = query.order_by(
            WorkflowTemplate.is_builtin.desc(),
            WorkflowTemplate.usage_count.desc(),
        )
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_template_by_id(
        db: AsyncSession,
        template_id: UUID,
    ) -> WorkflowTemplate | None:
        """Get a template by ID."""
        result = await db.execute(
            select(WorkflowTemplate).where(WorkflowTemplate.id == template_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def create_workflow_from_template(
        db: AsyncSession,
        template: WorkflowTemplate,
        user: User,
        name: str | None = None,
        customizations: dict | None = None,
    ) -> Workflow:
        """Create a workflow from a template."""
        # Generate unique slug
        base_slug = TemplateService._slugify(name or template.name)
        slug = base_slug
        counter = 1
        
        while await TemplateService._workflow_exists(db, slug, user.organization_id):
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Create workflow
        workflow = Workflow(
            name=name or f"{template.name} (Copy)",
            slug=slug,
            description=template.description,
            status=WorkflowStatus.INACTIVE,  # Start inactive for review
            trigger_type=template.trigger_type,
            organization_id=user.organization_id,
            tags=template.tags.copy(),
        )
        db.add(workflow)
        await db.flush()  # Get workflow ID
        
        # Create steps from template
        for step_config in template.steps_configuration:
            step = WorkflowStep(
                workflow_id=workflow.id,
                organization_id=user.organization_id,
                step_type=step_config["step_type"],
                action_type=step_config["action_type"],
                name=step_config["name"],
                order=step_config["order"],
                configuration=TemplateService._apply_customizations(
                    step_config.get("configuration", {}),
                    customizations,
                ),
                condition=step_config.get("condition"),
                is_active=True,
            )
            db.add(step)
        
        # Record template usage
        template.record_usage()
        usage = WorkflowTemplateUsage(
            template_id=template.id,
            organization_id=user.organization_id,
            user_id=user.id,
            workflow_id=workflow.id,
            customizations=customizations or {},
        )
        db.add(usage)
        
        await db.flush()
        
        logger.info(
            "Workflow created from template",
            template_id=str(template.id),
            workflow_id=str(workflow.id),
            user_id=str(user.id),
        )
        
        return workflow
    
    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to URL-friendly slug."""
        # Convert to lowercase
        text = text.lower()
        # Replace spaces and underscores with hyphens
        text = re.sub(r"[\s_]+", "-", text)
        # Remove non-alphanumeric characters except hyphens
        text = re.sub(r"[^a-z0-9-]", "", text)
        # Remove multiple hyphens
        text = re.sub(r"-+", "-", text)
        # Remove leading/trailing hyphens
        text = text.strip("-")
        return text or "workflow"
    
    @staticmethod
    async def _workflow_exists(
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
    def _apply_customizations(
        configuration: dict,
        customizations: dict | None,
    ) -> dict:
        """Apply customizations to step configuration."""
        if not customizations:
            return configuration
        
        result = configuration.copy()
        
        # Simple placeholder replacement
        for key, value in result.items():
            if isinstance(value, str):
                for custom_key, custom_value in customizations.items():
                    placeholder = f"{{{{template.{custom_key}}}}}"
                    if placeholder in value:
                        result[key] = value.replace(placeholder, str(custom_value))
        
        return result
    
    @staticmethod
    async def create_custom_template(
        db: AsyncSession,
        user: User,
        name: str,
        description: str | None,
        category: str,
        workflow_id: UUID,
    ) -> WorkflowTemplate:
        """Create a custom template from an existing workflow."""
        # Get workflow
        result = await db.execute(
            select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.organization_id == user.organization_id,
            )
        )
        workflow = result.scalar_one_or_none()
        
        if not workflow:
            raise ValueError("Workflow not found")
        
        # Load steps
        await db.refresh(workflow, ["steps"])
        
        # Build steps configuration
        steps_config = []
        for step in workflow.steps:
            steps_config.append({
                "name": step.name,
                "step_type": step.step_type.value if step.step_type else None,
                "action_type": step.action_type.value if step.action_type else None,
                "order": step.order,
                "configuration": step.configuration,
                "condition": step.condition,
            })
        
        # Generate unique slug
        base_slug = TemplateService._slugify(name)
        slug = base_slug
        counter = 1
        
        while await TemplateService._template_exists(db, slug, user.organization_id):
            slug = f"{base_slug}-{counter}"
            counter += 1
        
        # Create template
        template = WorkflowTemplate(
            slug=slug,
            name=name,
            description=description,
            category=category,
            trigger_type=workflow.trigger_type.value if workflow.trigger_type else None,
            steps_configuration=steps_config,
            organization_id=user.organization_id,
            created_by=user.id,
            is_builtin=False,
            is_active=True,
            tags=workflow.tags.copy() if workflow.tags else [],
        )
        db.add(template)
        await db.flush()
        
        logger.info(
            "Custom template created",
            template_id=str(template.id),
            workflow_id=str(workflow_id),
            user_id=str(user.id),
        )
        
        return template
    
    @staticmethod
    async def _template_exists(
        db: AsyncSession,
        slug: str,
        organization_id: UUID | None,
    ) -> bool:
        """Check if a template slug already exists."""
        query = select(WorkflowTemplate).where(WorkflowTemplate.slug == slug)
        
        if organization_id:
            query = query.where(
                or_(
                    WorkflowTemplate.organization_id == organization_id,
                    WorkflowTemplate.is_builtin == True,
                )
            )
        else:
            query = query.where(WorkflowTemplate.is_builtin == True)
        
        result = await db.execute(query)
        return result.scalar_one_or_none() is not None
