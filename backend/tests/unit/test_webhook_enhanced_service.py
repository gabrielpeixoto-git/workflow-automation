"""Unit tests for enhanced webhook service."""

import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from app.services.webhook_enhanced_service import (
    EnhancedWebhookService,
    WebhookRetryConfig,
    WebhookDeliveryLog,
    WebhookDeliveryStatus,
    WebhookAttempt,
)


class TestWebhookRetryConfig:
    """Test webhook retry configuration."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = WebhookRetryConfig()
        assert config.max_retries == 3
        assert config.retry_delays == [1, 5, 15]
        assert config.timeout == 30

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = WebhookRetryConfig(
            max_retries=5,
            retry_delays=[2, 4, 8, 16, 32],
            timeout=60,
        )
        assert config.max_retries == 5
        assert config.retry_delays == [2, 4, 8, 16, 32]
        assert config.timeout == 60

    def test_get_delay_for_attempt(self):
        """Test getting delay for specific attempt."""
        config = WebhookRetryConfig(retry_delays=[1, 5, 15])

        assert config.get_delay_for_attempt(0) == 1
        assert config.get_delay_for_attempt(1) == 5
        assert config.get_delay_for_attempt(2) == 15
        assert config.get_delay_for_attempt(5) == 15  # Out of bounds returns last


class TestWebhookAttempt:
    """Test webhook attempt data structure."""

    def test_attempt_creation(self):
        """Test creating a webhook attempt."""
        attempt = WebhookAttempt(
            attempt_number=1,
            started_at=datetime.utcnow(),
        )

        assert attempt.attempt_number == 1
        assert attempt.status_code is None
        assert attempt.error_message is None
        assert attempt.duration_ms is None

    def test_attempt_completion(self):
        """Test completing a webhook attempt."""
        attempt = WebhookAttempt(
            attempt_number=1,
            started_at=datetime.utcnow(),
        )

        attempt.completed_at = datetime.utcnow()
        attempt.status_code = 200
        attempt.duration_ms = 150.5

        assert attempt.status_code == 200
        assert attempt.duration_ms == 150.5


class TestWebhookDeliveryLog:
    """Test webhook delivery log."""

    def test_log_creation(self):
        """Test creating a delivery log."""
        log = WebhookDeliveryLog(
            delivery_id="test-id",
            webhook_id="webhook-1",
            payload={"test": "data"},
        )

        assert log.delivery_id == "test-id"
        assert log.webhook_id == "webhook-1"
        assert log.payload == {"test": "data"}
        assert log.final_status == WebhookDeliveryStatus.PENDING
        assert log.attempts == []

    def test_add_attempt(self):
        """Test adding an attempt to log."""
        log = WebhookDeliveryLog(
            delivery_id="test-id",
            webhook_id="webhook-1",
            payload={},
        )

        attempt = WebhookAttempt(
            attempt_number=1,
            started_at=datetime.utcnow(),
        )

        log.add_attempt(attempt)

        assert len(log.attempts) == 1
        assert log.attempts[0].attempt_number == 1

    def test_log_serialization(self):
        """Test serializing delivery log."""
        log = WebhookDeliveryLog(
            delivery_id="test-id",
            webhook_id="webhook-1",
            payload={"key": "value"},
        )

        attempt = WebhookAttempt(
            attempt_number=1,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            status_code=200,
            duration_ms=100.0,
        )
        log.add_attempt(attempt)
        log.final_status = WebhookDeliveryStatus.SUCCESS

        serialized = log.to_dict()

        assert serialized["delivery_id"] == "test-id"
        assert serialized["webhook_id"] == "webhook-1"
        assert serialized["final_status"] == "success"
        assert "payload" in serialized
        assert "attempts" in serialized


class TestEnhancedWebhookService:
    """Test enhanced webhook service."""

    @pytest_asyncio.fixture
    async def service(self):
        """Create enhanced webhook service."""
        return EnhancedWebhookService()

    @pytest_asyncio.fixture
    def retry_config(self):
        """Create test retry configuration."""
        return WebhookRetryConfig(
            max_retries=2,
            retry_delays=[0.1, 0.1],
            timeout=5,
        )

    async def test_send_webhook_success(self, service, retry_config):
        """Test sending webhook successfully."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(
                status_code=200,
                headers={"X-Request-ID": "test-123"},
                text='{"success": true}',
            )

            result = await service.send_webhook(
                webhook_url="https://example.com/webhook",
                payload={"test": "data"},
                retry_config=retry_config,
            )

            assert result.final_status == WebhookDeliveryStatus.SUCCESS
            assert len(result.attempts) == 1
            assert result.attempts[0].status_code == 200

    async def test_send_webhook_with_retries(self, service, retry_config):
        """Test sending webhook with retry on failure."""
        with patch('httpx.AsyncClient.post') as mock_post:
            # First call fails, second succeeds
            mock_post.side_effect = [
                AsyncMock(status_code=500, text="Error"),
                AsyncMock(status_code=200, text="OK"),
            ]

            result = await service.send_webhook(
                webhook_url="https://example.com/webhook",
                payload={"test": "data"},
                retry_config=retry_config,
            )

            assert result.final_status == WebhookDeliveryStatus.SUCCESS
            assert len(result.attempts) == 2
            assert result.attempts[0].status_code == 500
            assert result.attempts[1].status_code == 200

    async def test_send_webhook_all_retries_fail(self, service, retry_config):
        """Test sending webhook when all retries fail."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(status_code=500, text="Server Error")

            result = await service.send_webhook(
                webhook_url="https://example.com/webhook",
                payload={"test": "data"},
                retry_config=retry_config,
            )

            assert result.final_status == WebhookDeliveryStatus.FAILED
            assert len(result.attempts) == retry_config.max_retries + 1

    async def test_send_webhook_with_hmac_signature(self, service, retry_config):
        """Test sending webhook with HMAC signature."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, text="OK")

            result = await service.send_webhook(
                webhook_url="https://example.com/webhook",
                payload={"test": "data"},
                secret="my-secret-key",
                retry_config=retry_config,
            )

            assert result.final_status == WebhookDeliveryStatus.SUCCESS

            # Verify signature was generated and sent
            call_args = mock_post.call_args
            headers = call_args[1].get('headers', {})
            assert 'X-Webhook-Signature' in headers

    async def test_send_webhook_timeout(self, service, retry_config):
        """Test sending webhook with timeout."""
        with patch('httpx.AsyncClient.post') as mock_post:
            import httpx
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            result = await service.send_webhook(
                webhook_url="https://example.com/webhook",
                payload={"test": "data"},
                retry_config=retry_config,
            )

            assert result.final_status == WebhookDeliveryStatus.FAILED

    async def test_send_webhook_with_custom_headers(self, service, retry_config):
        """Test sending webhook with custom headers."""
        with patch('httpx.AsyncClient.post') as mock_post:
            mock_post.return_value = AsyncMock(status_code=200, text="OK")

            result = await service.send_webhook(
                webhook_url="https://example.com/webhook",
                payload={"test": "data"},
                headers={"X-Custom-Header": "custom-value"},
                retry_config=retry_config,
            )

            assert result.final_status == WebhookDeliveryStatus.SUCCESS

            # Verify custom header was sent
            call_args = mock_post.call_args
            headers = call_args[1].get('headers', {})
            assert headers.get('X-Custom-Header') == 'custom-value'

    def test_generate_hmac_signature(self, service):
        """Test HMAC signature generation."""
        payload = {"test": "data"}
        secret = "my-secret"

        signature = service._generate_signature(payload, secret)

        assert signature is not None
        assert len(signature) > 0
        # Signature should be base64 encoded
        import base64
        try:
            base64.b64decode(signature)
            valid_base64 = True
        except Exception:
            valid_base64 = False
        assert valid_base64

    def test_is_retryable_status_code(self, service):
        """Test determining if status code is retryable."""
        assert service._is_retryable_status_code(500) is True
        assert service._is_retryable_status_code(502) is True
        assert service._is_retryable_status_code(503) is True
        assert service._is_retryable_status_code(504) is True
        assert service._is_retryable_status_code(400) is False
        assert service._is_retryable_status_code(404) is False
        assert service._is_retryable_status_code(200) is False
