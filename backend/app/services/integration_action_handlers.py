"""Integration action handlers for workflow execution.

This module provides handlers for executing integration actions (Slack, Email, Discord)
during workflow execution.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.integration import Integration, IntegrationType
from app.models.workflow import WorkflowStep
from app.services.integration_service import IntegrationService, SlackIntegration, DiscordIntegration, EmailSMTPIntegration

logger = get_logger(__name__)


class IntegrationActionHandler:
    """Handler for integration actions in workflows."""

    def __init__(self):
        self.integration_service = IntegrationService()

    async def handle_slack_action(
        self,
        db: AsyncSession,
        step: WorkflowStep,
        context: dict[str, Any],
        organization_id: str,
    ) -> dict[str, Any]:
        """Execute Slack action.
        
        Args:
            db: Database session
            step: Workflow step with configuration
            context: Execution context with variables
            organization_id: Organization ID
            
        Returns:
            Action result dict
        """
        config = step.config or {}
        
        # Get integration ID or use default
        integration_id = config.get("integration_id")
        
        # Find integration
        if integration_id:
            integration = await self.integration_service.get_integration_by_id(
                db=db,
                integration_id=integration_id,
                organization_id=organization_id,
            )
        else:
            # Get default Slack integration
            integrations = await self.integration_service.get_integrations(
                db=db,
                organization_id=organization_id,
                integration_type=IntegrationType.SLACK.value,
            )
            integration = integrations[0] if integrations else None
        
        if not integration:
            return {
                "success": False,
                "error": "No Slack integration found",
            }
        
        # Prepare message
        message = self._render_template(
            config.get("message", "Workflow notification"),
            context,
        )
        
        title = self._render_template(
            config.get("title", "Workflow Alert"),
            context,
        )
        
        # Execute integration
        result = await self.integration_service.execute_integration(
            db=db,
            integration=integration,
            event_type="workflow_action",
            payload={
                "title": title,
                "message": message,
                "color": config.get("color", "#36a64f"),
                "fields": config.get("fields", []),
            },
        )
        
        return result

    async def handle_discord_action(
        self,
        db: AsyncSession,
        step: WorkflowStep,
        context: dict[str, Any],
        organization_id: str,
    ) -> dict[str, Any]:
        """Execute Discord action.
        
        Args:
            db: Database session
            step: Workflow step with configuration
            context: Execution context with variables
            organization_id: Organization ID
            
        Returns:
            Action result dict
        """
        config = step.config or {}
        
        # Get integration ID or use default
        integration_id = config.get("integration_id")
        
        # Find integration
        if integration_id:
            integration = await self.integration_service.get_integration_by_id(
                db=db,
                integration_id=integration_id,
                organization_id=organization_id,
            )
        else:
            # Get default Discord integration
            integrations = await self.integration_service.get_integrations(
                db=db,
                organization_id=organization_id,
                integration_type=IntegrationType.DISCORD.value,
            )
            integration = integrations[0] if integrations else None
        
        if not integration:
            return {
                "success": False,
                "error": "No Discord integration found",
            }
        
        # Prepare message
        message = self._render_template(
            config.get("message", "Workflow notification"),
            context,
        )
        
        title = self._render_template(
            config.get("title", "Workflow Alert"),
            context,
        )
        
        # Execute integration
        result = await self.integration_service.execute_integration(
            db=db,
            integration=integration,
            event_type="workflow_action",
            payload={
                "title": title,
                "message": message,
                "color": config.get("color", "0x36a64f"),
                "fields": config.get("fields", {}),
            },
        )
        
        return result

    async def handle_email_action(
        self,
        db: AsyncSession,
        step: WorkflowStep,
        context: dict[str, Any],
        organization_id: str,
    ) -> dict[str, Any]:
        """Execute Email action.
        
        Args:
            db: Database session
            step: Workflow step with configuration
            context: Execution context with variables
            organization_id: Organization ID
            
        Returns:
            Action result dict
        """
        config = step.config or {}
        
        # Get integration ID or use default
        integration_id = config.get("integration_id")
        
        # Find integration
        if integration_id:
            integration = await self.integration_service.get_integration_by_id(
                db=db,
                integration_id=integration_id,
                organization_id=organization_id,
            )
        else:
            # Get default Email integration
            integrations = await self.integration_service.get_integrations(
                db=db,
                organization_id=organization_id,
                integration_type=IntegrationType.EMAIL_SMTP.value,
            )
            integration = integrations[0] if integrations else None
        
        if not integration:
            return {
                "success": False,
                "error": "No Email integration found",
            }
        
        # Prepare email content
        subject = self._render_template(
            config.get("subject", "Workflow Notification"),
            context,
        )
        
        body = self._render_template(
            config.get("body", "Workflow executed"),
            context,
        )
        
        html_body = config.get("html_body")
        if html_body:
            html_body = self._render_template(html_body, context)
        
        # Get recipients
        to_emails = config.get("to_emails", [])
        if not to_emails:
            # Use default from integration config
            to_emails = [integration.configuration.get("from_email", "")]
        
        # Execute integration
        result = await self.integration_service.execute_integration(
            db=db,
            integration=integration,
            event_type="workflow_action",
            payload={
                "subject": subject,
                "body": body,
                "html_body": html_body,
                "to_emails": to_emails,
            },
        )
        
        return result

    def _render_template(self, template: str, context: dict[str, Any]) -> str:
        """Render a template string with context variables.
        
        Args:
            template: Template string with {{variable}} placeholders
            context: Dict with variable values
            
        Returns:
            Rendered string
        """
        result = template
        for key, value in context.items():
            placeholder = f"{{{{{key}}}}}"
            result = result.replace(placeholder, str(value))
        return result


class IntegrationActionRegistry:
    """Registry for integration action handlers."""

    def __init__(self):
        self.handler = IntegrationActionHandler()

    async def execute(
        self,
        db: AsyncSession,
        action_type: str,
        step: WorkflowStep,
        context: dict[str, Any],
        organization_id: str,
    ) -> dict[str, Any]:
        """Execute an integration action.
        
        Args:
            db: Database session
            action_type: Type of action (send_slack, send_discord, send_email)
            step: Workflow step with configuration
            context: Execution context
            organization_id: Organization ID
            
        Returns:
            Action result dict
        """
        from app.models.workflow import ActionType
        
        if action_type == ActionType.SEND_SLACK.value:
            return await self.handler.handle_slack_action(
                db=db,
                step=step,
                context=context,
                organization_id=organization_id,
            )
        
        elif action_type == ActionType.SEND_DISCORD.value:
            return await self.handler.handle_discord_action(
                db=db,
                step=step,
                context=context,
                organization_id=organization_id,
            )
        
        elif action_type == ActionType.SEND_EMAIL.value:
            return await self.handler.handle_email_action(
                db=db,
                step=step,
                context=context,
                organization_id=organization_id,
            )
        
        else:
            return {
                "success": False,
                "error": f"Unknown integration action type: {action_type}",
            }


# Global registry instance
integration_registry = IntegrationActionRegistry()
