"""Integration service for external services."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.integration import Integration, IntegrationLog, IntegrationStatus, IntegrationType
from app.models.user import User

logger = get_logger(__name__)


class SlackIntegration:
    """Slack integration handler."""
    
    @staticmethod
    async def send_message(
        webhook_url: str,
        message: str,
        channel: str | None = None,
        username: str | None = None,
        icon_emoji: str | None = None,
    ) -> dict[str, Any]:
        """Send message to Slack via webhook.
        
        Args:
            webhook_url: Slack incoming webhook URL
            message: Message text (supports markdown)
            channel: Optional channel override
            username: Optional bot username
            icon_emoji: Optional emoji icon
            
        Returns:
            Response dict with status and details
        """
        payload = {
            "text": message,
        }
        
        if channel:
            payload["channel"] = channel
        if username:
            payload["username"] = username
        if icon_emoji:
            payload["icon_emoji"] = icon_emoji
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                # Slack returns "ok" on success
                if response.status_code == 200 and response.text == "ok":
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response": response.text,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                    }
                    
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Timeout connecting to Slack",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @staticmethod
    async def send_rich_message(
        webhook_url: str,
        title: str,
        description: str,
        color: str = "#36a64f",
        fields: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Send rich formatted message with attachments."""
        attachment = {
            "color": color,
            "title": title,
            "text": description,
            "footer": "Automation Platform",
            "ts": int(datetime.utcnow().timestamp()),
        }
        
        if fields:
            attachment["fields"] = fields
        
        payload = {
            "attachments": [attachment],
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code == 200 and response.text == "ok":
                    return {
                        "success": True,
                        "status_code": response.status_code,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class EmailSMTPIntegration:
    """Email SMTP integration handler."""
    
    @staticmethod
    async def send_email(
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        to_emails: list[str],
        subject: str,
        body: str,
        html_body: str | None = None,
        use_tls: bool = True,
    ) -> dict[str, Any]:
        """Send email via SMTP.
        
        Args:
            host: SMTP server host
            port: SMTP server port
            username: SMTP username
            password: SMTP password
            from_email: From email address
            to_emails: List of recipient emails
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body
            use_tls: Use TLS encryption
            
        Returns:
            Response dict with status and details
        """
        try:
            import aiosmtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
            
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_email
            msg["To"] = ", ".join(to_emails)
            
            # Add plain text part
            msg.attach(MIMEText(body, "plain"))
            
            # Add HTML part if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))
            
            # Connect and send
            smtp = aiosmtplib.SMTP(
                hostname=host,
                port=port,
                use_tls=use_tls,
            )
            
            await smtp.connect()
            
            if not use_tls:
                await smtp.starttls()
            
            await smtp.login(username, password)
            
            await smtp.send_message(msg)
            await smtp.quit()
            
            return {
                "success": True,
                "recipients": len(to_emails),
            }
            
        except ImportError:
            return {
                "success": False,
                "error": "aiosmtplib not installed. Run: pip install aiosmtplib",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class DiscordIntegration:
    """Discord integration handler."""
    
    @staticmethod
    async def send_message(
        webhook_url: str,
        content: str,
        username: str | None = None,
        avatar_url: str | None = None,
    ) -> dict[str, Any]:
        """Send message to Discord via webhook.
        
        Args:
            webhook_url: Discord webhook URL
            content: Message content
            username: Optional bot username
            avatar_url: Optional bot avatar URL
            
        Returns:
            Response dict with status and details
        """
        payload = {
            "content": content,
        }
        
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                # Discord returns 204 on success
                if response.status_code == 204:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                    }
                    
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "Timeout connecting to Discord",
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    @staticmethod
    async def send_embed(
        webhook_url: str,
        title: str,
        description: str,
        color: int = 0x36a64f,
        fields: list[dict] | None = None,
        footer: dict | None = None,
    ) -> dict[str, Any]:
        """Send rich embed message."""
        embed = {
            "title": title,
            "description": description,
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        if fields:
            embed["fields"] = fields
        
        if footer:
            embed["footer"] = footer
        else:
            embed["footer"] = {"text": "Automation Platform"}
        
        payload = {
            "embeds": [embed],
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                if response.status_code == 204:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": response.text,
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }


class IntegrationService:
    """Main service for managing integrations."""
    
    @staticmethod
    async def test_integration(
        integration: Integration,
    ) -> dict[str, Any]:
        """Test an integration connection.
        
        Args:
            integration: Integration to test
            
        Returns:
            Test result dict
        """
        config = integration.configuration
        
        if integration.integration_type == IntegrationType.SLACK.value:
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                return {"success": False, "error": "Webhook URL not configured"}
            
            result = await SlackIntegration.send_message(
                webhook_url=webhook_url,
                message="🔧 Test message from Automation Platform",
            )
            
        elif integration.integration_type == IntegrationType.EMAIL_SMTP.value:
            result = await EmailSMTPIntegration.send_email(
                host=config.get("host", ""),
                port=config.get("port", 587),
                username=config.get("username", ""),
                password=config.get("password", ""),
                from_email=config.get("from_email", ""),
                to_emails=[config.get("test_email", config.get("username", ""))],
                subject="Test Email from Automation Platform",
                body="This is a test email to verify your SMTP configuration.",
                use_tls=config.get("use_tls", True),
            )
            
        elif integration.integration_type == IntegrationType.DISCORD.value:
            webhook_url = config.get("webhook_url")
            if not webhook_url:
                return {"success": False, "error": "Webhook URL not configured"}
            
            result = await DiscordIntegration.send_message(
                webhook_url=webhook_url,
                content="🔧 Test message from Automation Platform",
            )
            
        else:
            return {"success": False, "error": f"Unknown integration type: {integration.integration_type}"}
        
        return result
    
    @staticmethod
    async def execute_integration(
        db: AsyncSession,
        integration: Integration,
        event_type: str,
        payload: dict,
    ) -> dict[str, Any]:
        """Execute an integration with given payload.
        
        Args:
            db: Database session
            integration: Integration to execute
            event_type: Type of event triggering the integration
            payload: Data payload for the integration
            
        Returns:
            Execution result dict
        """
        start_time = datetime.utcnow()
        
        # Execute based on type
        if integration.integration_type == IntegrationType.SLACK.value:
            result = await SlackIntegration.send_rich_message(
                webhook_url=integration.configuration.get("webhook_url", ""),
                title=payload.get("title", "Automation Platform Notification"),
                description=payload.get("message", ""),
                color=payload.get("color", "#36a64f"),
                fields=payload.get("fields"),
            )
            
        elif integration.integration_type == IntegrationType.EMAIL_SMTP.value:
            result = await EmailSMTPIntegration.send_email(
                host=integration.configuration.get("host", ""),
                port=integration.configuration.get("port", 587),
                username=integration.configuration.get("username", ""),
                password=integration.configuration.get("password", ""),
                from_email=integration.configuration.get("from_email", ""),
                to_emails=payload.get("to_emails", []),
                subject=payload.get("subject", "Notification"),
                body=payload.get("body", ""),
                html_body=payload.get("html_body"),
                use_tls=integration.configuration.get("use_tls", True),
            )
            
        elif integration.integration_type == IntegrationType.DISCORD.value:
            result = await DiscordIntegration.send_embed(
                webhook_url=integration.configuration.get("webhook_url", ""),
                title=payload.get("title", "Automation Platform"),
                description=payload.get("message", ""),
                color=int(payload.get("color", "0x36a64f"), 16),
                fields=[
                    {"name": k, "value": str(v), "inline": True}
                    for k, v in (payload.get("fields") or {}).items()
                ] if payload.get("fields") else None,
            )
            
        else:
            result = {"success": False, "error": "Unknown integration type"}
        
        # Calculate duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Record usage
        integration.record_usage(
            success=result.get("success", False),
            message=result.get("error"),
        )
        
        # Create log entry
        log = IntegrationLog(
            integration_id=integration.id,
            organization_id=integration.organization_id,
            event_type=event_type,
            payload=payload,
            status="success" if result.get("success") else "failed",
            status_code=result.get("status_code"),
            error_message=result.get("error"),
            response_data={"result": result},
            duration_ms=duration_ms,
        )
        db.add(log)
        await db.flush()
        
        return result
    
    @staticmethod
    async def get_integrations(
        db: AsyncSession,
        organization_id: UUID,
        integration_type: str | None = None,
        status: str | None = None,
    ) -> list[Integration]:
        """Get integrations for an organization."""
        query = select(Integration).where(
            Integration.organization_id == organization_id,
        )
        
        if integration_type:
            query = query.where(Integration.integration_type == integration_type)
        
        if status:
            query = query.where(Integration.status == status)
        
        query = query.order_by(Integration.created_at.desc())
        
        result = await db.execute(query)
        return list(result.scalars().all())
    
    @staticmethod
    async def get_integration_by_id(
        db: AsyncSession,
        integration_id: UUID,
        organization_id: UUID,
    ) -> Integration | None:
        """Get a specific integration."""
        result = await db.execute(
            select(Integration).where(
                Integration.id == integration_id,
                Integration.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()
