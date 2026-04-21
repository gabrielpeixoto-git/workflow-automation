"""Unit tests for integration service."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock

from app.services.integration_service import (
    IntegrationService,
    SlackIntegration,
    EmailSMTPIntegration,
    DiscordIntegration,
)
from app.models.integration import Integration, IntegrationStatus, IntegrationType


class TestSlackIntegration:
    """Test Slack integration functionality."""

    async def test_send_message_success(self):
        """Test sending message to Slack successfully."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                text="ok",
            )

            result = await SlackIntegration.send_message(
                webhook_url="https://hooks.slack.com/test",
                message="Test message",
            )

            assert result["success"] is True
            assert result["status_code"] == 200

    async def test_send_message_failure(self):
        """Test sending message to Slack with failure."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=400,
                text="invalid_payload",
            )

            result = await SlackIntegration.send_message(
                webhook_url="https://hooks.slack.com/test",
                message="Test message",
            )

            assert result["success"] is False
            assert result["status_code"] == 400

    async def test_send_message_with_options(self):
        """Test sending message with optional parameters."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                text="ok",
            )

            result = await SlackIntegration.send_message(
                webhook_url="https://hooks.slack.com/test",
                message="Test message",
                channel="#general",
                username="Bot",
                icon_emoji=":robot:",
            )

            assert result["success"] is True

    async def test_send_rich_message(self):
        """Test sending rich formatted message."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                text="ok",
            )

            result = await SlackIntegration.send_rich_message(
                webhook_url="https://hooks.slack.com/test",
                title="Test Title",
                description="Test Description",
                color="#36a64f",
                fields=[
                    {"title": "Field 1", "value": "Value 1", "short": True},
                ],
            )

            assert result["success"] is True


class TestDiscordIntegration:
    """Test Discord integration functionality."""

    async def test_send_message_success(self):
        """Test sending message to Discord successfully."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=204,
            )

            result = await DiscordIntegration.send_message(
                webhook_url="https://discord.com/api/webhooks/test",
                content="Test message",
            )

            assert result["success"] is True
            assert result["status_code"] == 204

    async def test_send_message_failure(self):
        """Test sending message to Discord with failure."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=404,
                text="Webhook not found",
            )

            result = await DiscordIntegration.send_message(
                webhook_url="https://discord.com/api/webhooks/invalid",
                content="Test message",
            )

            assert result["success"] is False
            assert result["status_code"] == 404

    async def test_send_embed(self):
        """Test sending rich embed message."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=204,
            )

            result = await DiscordIntegration.send_embed(
                webhook_url="https://discord.com/api/webhooks/test",
                title="Test Title",
                description="Test Description",
                color=0x36a64f,
                fields=[
                    {"name": "Field 1", "value": "Value 1", "inline": True},
                ],
            )

            assert result["success"] is True


class TestIntegrationService:
    """Test main integration service."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create integration service instance."""
        return IntegrationService()

    @pytest_asyncio.fixture
    async def slack_integration(self, db, test_org, test_user):
        """Create a Slack integration for testing."""
        integration = Integration(
            name="Test Slack",
            integration_type=IntegrationType.SLACK.value,
            organization_id=test_org.id,
            created_by=test_user.id,
            configuration={
                "webhook_url": "https://hooks.slack.com/test",
            },
            status=IntegrationStatus.PENDING.value,
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        return integration

    @pytest_asyncio.fixture
    async def discord_integration(self, db, test_org, test_user):
        """Create a Discord integration for testing."""
        integration = Integration(
            name="Test Discord",
            integration_type=IntegrationType.DISCORD.value,
            organization_id=test_org.id,
            created_by=test_user.id,
            configuration={
                "webhook_url": "https://discord.com/api/webhooks/test",
            },
            status=IntegrationStatus.PENDING.value,
        )
        db.add(integration)
        await db.commit()
        await db.refresh(integration)
        return integration

    async def test_test_integration_slack_success(self, db, service, slack_integration):
        """Test testing Slack integration successfully."""
        with patch.object(SlackIntegration, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"success": True, "status_code": 200}

            result = await service.test_integration(slack_integration)

            assert result["success"] is True
            assert slack_integration.status == IntegrationStatus.ACTIVE.value

    async def test_test_integration_slack_failure(self, db, service, slack_integration):
        """Test testing Slack integration with failure."""
        with patch.object(SlackIntegration, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"success": False, "error": "Invalid webhook"}

            result = await service.test_integration(slack_integration)

            assert result["success"] is False
            assert slack_integration.status == IntegrationStatus.ERROR.value
            assert "Invalid webhook" in slack_integration.status_message

    async def test_execute_integration_slack(self, db, service, slack_integration):
        """Test executing Slack integration."""
        with patch.object(SlackIntegration, 'send_rich_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"success": True, "status_code": 200}

            result = await service.execute_integration(
                db=db,
                integration=slack_integration,
                event_type="test",
                payload={
                    "title": "Test",
                    "message": "Test message",
                },
            )

            assert result["success"] is True
            assert slack_integration.use_count == 1
            assert slack_integration.success_count == 1

    async def test_execute_integration_discord(self, db, service, discord_integration):
        """Test executing Discord integration."""
        with patch.object(DiscordIntegration, 'send_embed', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"success": True, "status_code": 204}

            result = await service.execute_integration(
                db=db,
                integration=discord_integration,
                event_type="test",
                payload={
                    "title": "Test",
                    "message": "Test message",
                },
            )

            assert result["success"] is True
            assert discord_integration.use_count == 1

    async def test_get_integrations(self, db, service, test_org, test_user):
        """Test listing integrations."""
        # Create multiple integrations
        for i in range(3):
            integration = Integration(
                name=f"Integration {i}",
                integration_type=IntegrationType.SLACK.value,
                organization_id=test_org.id,
                created_by=test_user.id,
                configuration={},
            )
            db.add(integration)
        await db.commit()

        integrations = await service.get_integrations(
            db=db,
            organization_id=test_org.id,
        )

        assert len(integrations) == 3

    async def test_get_integrations_with_type_filter(self, db, service, test_org, test_user):
        """Test listing integrations with type filter."""
        # Create Slack integration
        slack = Integration(
            name="Slack",
            integration_type=IntegrationType.SLACK.value,
            organization_id=test_org.id,
            created_by=test_user.id,
            configuration={},
        )
        db.add(slack)

        # Create Discord integration
        discord = Integration(
            name="Discord",
            integration_type=IntegrationType.DISCORD.value,
            organization_id=test_org.id,
            created_by=test_user.id,
            configuration={},
        )
        db.add(discord)
        await db.commit()

        slack_integrations = await service.get_integrations(
            db=db,
            organization_id=test_org.id,
            integration_type="slack",
        )

        assert len(slack_integrations) == 1
        assert slack_integrations[0].integration_type == IntegrationType.SLACK.value

    async def test_get_integration_by_id(self, db, service, slack_integration):
        """Test getting integration by ID."""
        result = await service.get_integration_by_id(
            db=db,
            integration_id=slack_integration.id,
            organization_id=slack_integration.organization_id,
        )

        assert result is not None
        assert result.id == slack_integration.id
        assert result.name == slack_integration.name

    async def test_integration_success_rate(self, db, service, slack_integration):
        """Test calculating integration success rate."""
        # Record some usages
        slack_integration.record_usage(success=True)
        slack_integration.record_usage(success=True)
        slack_integration.record_usage(success=False)

        assert slack_integration.use_count == 3
        assert slack_integration.success_count == 2
        assert slack_integration.error_count == 1
        assert slack_integration.success_rate == pytest.approx(66.67, 0.01)
