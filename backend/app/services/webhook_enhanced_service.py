"""Enhanced webhook service with retries, timeouts and custom headers."""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.audit_log import AuditAction, AuditLog
from app.models.user import User
from app.models.workflow import Workflow

logger = get_logger(__name__)


class WebhookDeliveryStatus(str, Enum):
    """Webhook delivery status."""
    
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookRetryConfig:
    """Configuration for webhook retries."""
    
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAYS = [1, 5, 15]  # seconds between retries
    DEFAULT_TIMEOUT = 30  # seconds
    
    def __init__(
        self,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delays: list[int] | None = None,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.max_retries = max_retries
        self.retry_delays = retry_delays or self.DEFAULT_RETRY_DELAYS
        self.timeout = timeout


class WebhookDeliveryAttempt:
    """Record of a webhook delivery attempt."""
    
    def __init__(
        self,
        attempt_number: int,
        status: WebhookDeliveryStatus,
        status_code: int | None = None,
        response_body: str | None = None,
        error_message: str | None = None,
        duration_ms: float | None = None,
        timestamp: datetime | None = None,
    ):
        self.attempt_number = attempt_number
        self.status = status
        self.status_code = status_code
        self.response_body = response_body
        self.error_message = error_message
        self.duration_ms = duration_ms
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "attempt_number": self.attempt_number,
            "status": self.status.value,
            "status_code": self.status_code,
            "response_body": self.response_body,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }


class WebhookDeliveryLog:
    """Complete log of a webhook delivery."""
    
    def __init__(
        self,
        delivery_id: UUID,
        webhook_url: str,
        payload: dict,
        headers: dict,
        attempts: list[WebhookDeliveryAttempt],
        final_status: WebhookDeliveryStatus,
        created_at: datetime | None = None,
    ):
        self.delivery_id = delivery_id
        self.webhook_url = webhook_url
        self.payload = payload
        self.headers = headers
        self.attempts = attempts
        self.final_status = final_status
        self.created_at = created_at or datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "delivery_id": str(self.delivery_id),
            "webhook_url": self.webhook_url,
            "payload": self.payload,
            "headers": {k: v for k, v in self.headers.items() if k.lower() not in ['authorization', 'x-api-key']},
            "attempts": [a.to_dict() for a in self.attempts],
            "final_status": self.final_status.value,
            "created_at": self.created_at.isoformat(),
            "total_duration_ms": sum(
                (a.duration_ms or 0) for a in self.attempts
            ),
        }


class EnhancedWebhookService:
    """Enhanced service for sending webhooks with retries and logging."""
    
    def __init__(self):
        self.delivery_logs: list[WebhookDeliveryLog] = []
        self._lock = asyncio.Lock()
    
    async def send_webhook(
        self,
        webhook_url: str,
        payload: dict,
        headers: dict | None = None,
        secret: str | None = None,
        retry_config: WebhookRetryConfig | None = None,
        webhook_id: str | None = None,
    ) -> WebhookDeliveryLog:
        """Send webhook with automatic retries and logging.
        
        Args:
            webhook_url: URL to send webhook to
            payload: Data to send
            headers: Custom headers to include
            secret: Secret for HMAC signature
            retry_config: Retry configuration
            webhook_id: Optional webhook identifier
            
        Returns:
            WebhookDeliveryLog with complete delivery details
        """
        retry_config = retry_config or WebhookRetryConfig()
        delivery_id = uuid4()
        
        # Build headers
        request_headers = self._build_headers(
            payload=payload,
            custom_headers=headers,
            secret=secret,
            webhook_id=webhook_id,
        )
        
        attempts: list[WebhookDeliveryAttempt] = []
        final_status = WebhookDeliveryStatus.FAILED
        
        # Attempt delivery with retries
        for attempt_number in range(retry_config.max_retries + 1):
            attempt = await self._attempt_delivery(
                webhook_url=webhook_url,
                payload=payload,
                headers=request_headers,
                attempt_number=attempt_number + 1,
                timeout=retry_config.timeout,
            )
            attempts.append(attempt)
            
            if attempt.status == WebhookDeliveryStatus.SUCCESS:
                final_status = WebhookDeliveryStatus.SUCCESS
                break
            
            # Check if we should retry
            if attempt_number < retry_config.max_retries:
                delay = retry_config.retry_delays[min(attempt_number, len(retry_config.retry_delays) - 1)]
                logger.info(
                    "Webhook delivery failed, retrying",
                    delivery_id=str(delivery_id),
                    attempt=attempt_number + 1,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                final_status = WebhookDeliveryStatus.RETRYING
            else:
                final_status = WebhookDeliveryStatus.FAILED
        
        # Create delivery log
        log = WebhookDeliveryLog(
            delivery_id=delivery_id,
            webhook_url=webhook_url,
            payload=payload,
            headers=request_headers,
            attempts=attempts,
            final_status=final_status,
        )
        
        # Store log (in-memory for now, could be persisted to DB)
        async with self._lock:
            self.delivery_logs.append(log)
            # Keep only last 1000 logs
            if len(self.delivery_logs) > 1000:
                self.delivery_logs = self.delivery_logs[-1000:]
        
        # Log result
        if final_status == WebhookDeliveryStatus.SUCCESS:
            logger.info(
                "Webhook delivered successfully",
                delivery_id=str(delivery_id),
                attempts=len(attempts),
                total_duration_ms=sum(a.duration_ms or 0 for a in attempts),
            )
        else:
            logger.error(
                "Webhook delivery failed after all retries",
                delivery_id=str(delivery_id),
                attempts=len(attempts),
                last_error=attempts[-1].error_message if attempts else None,
            )
        
        return log
    
    def _build_headers(
        self,
        payload: dict,
        custom_headers: dict | None,
        secret: str | None,
        webhook_id: str | None,
    ) -> dict:
        """Build request headers with signature if secret provided."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AutomationPlatform/1.0",
            "X-Webhook-Timestamp": datetime.utcnow().isoformat(),
        }
        
        if webhook_id:
            headers["X-Webhook-ID"] = webhook_id
        
        # Add HMAC signature if secret provided
        if secret:
            signature = self._generate_signature(payload, secret)
            headers["X-Webhook-Signature"] = signature
        
        # Add custom headers (override defaults if needed)
        if custom_headers:
            headers.update(custom_headers)
        
        return headers
    
    def _generate_signature(self, payload: dict, secret: str) -> str:
        """Generate HMAC SHA256 signature for payload."""
        payload_bytes = json.dumps(payload, sort_keys=True, default=str).encode()
        secret_bytes = secret.encode()
        signature = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
        return f"sha256={signature}"
    
    async def _attempt_delivery(
        self,
        webhook_url: str,
        payload: dict,
        headers: dict,
        attempt_number: int,
        timeout: int,
    ) -> WebhookDeliveryAttempt:
        """Attempt a single webhook delivery."""
        start_time = datetime.utcnow()
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    url=webhook_url,
                    json=payload,
                    headers=headers,
                )
                
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Consider 2xx status codes as success
                if 200 <= response.status_code < 300:
                    return WebhookDeliveryAttempt(
                        attempt_number=attempt_number,
                        status=WebhookDeliveryStatus.SUCCESS,
                        status_code=response.status_code,
                        response_body=response.text[:1000],  # Limit response size
                        duration_ms=duration_ms,
                    )
                else:
                    return WebhookDeliveryAttempt(
                        attempt_number=attempt_number,
                        status=WebhookDeliveryStatus.FAILED,
                        status_code=response.status_code,
                        response_body=response.text[:1000],
                        error_message=f"HTTP {response.status_code}",
                        duration_ms=duration_ms,
                    )
                    
        except httpx.TimeoutException:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return WebhookDeliveryAttempt(
                attempt_number=attempt_number,
                status=WebhookDeliveryStatus.FAILED,
                error_message=f"Timeout after {timeout}s",
                duration_ms=duration_ms,
            )
        except httpx.ConnectError as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return WebhookDeliveryAttempt(
                attempt_number=attempt_number,
                status=WebhookDeliveryStatus.FAILED,
                error_message=f"Connection error: {str(e)}",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            return WebhookDeliveryAttempt(
                attempt_number=attempt_number,
                status=WebhookDeliveryStatus.FAILED,
                error_message=str(e)[:500],
                duration_ms=duration_ms,
            )
    
    async def get_delivery_logs(
        self,
        limit: int = 100,
        status: WebhookDeliveryStatus | None = None,
    ) -> list[WebhookDeliveryLog]:
        """Get recent delivery logs."""
        async with self._lock:
            logs = self.delivery_logs.copy()
        
        if status:
            logs = [log for log in logs if log.final_status == status]
        
        return logs[-limit:]
    
    async def get_delivery_log(self, delivery_id: UUID) -> WebhookDeliveryLog | None:
        """Get a specific delivery log."""
        async with self._lock:
            for log in self.delivery_logs:
                if log.delivery_id == delivery_id:
                    return log
        return None
    
    async def get_stats(self) -> dict:
        """Get webhook delivery statistics."""
        async with self._lock:
            total = len(self.delivery_logs)
            successful = sum(1 for log in self.delivery_logs if log.final_status == WebhookDeliveryStatus.SUCCESS)
            failed = sum(1 for log in self.delivery_logs if log.final_status == WebhookDeliveryStatus.FAILED)
        
        success_rate = (successful / total * 100) if total > 0 else 0
        
        return {
            "total_deliveries": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(success_rate, 2),
        }


# Global service instance
webhook_service = EnhancedWebhookService()
