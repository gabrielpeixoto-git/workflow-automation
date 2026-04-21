"""API Key management service."""

import hashlib
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.api_key import APIKey, APIKeyScope, APIKeyStatus, APIKeyUsageLog
from app.models.user import User

logger = get_logger(__name__)


class APIKeyError(Exception):
    """API Key error."""
    pass


class APIKeyService:
    """Service for API key management."""
    
    @staticmethod
    def _hash_key(key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(key.encode()).hexdigest()
    
    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        user: User,
        name: str,
        scopes: list[str],
        description: str | None = None,
        expires_days: int | None = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_hour: int = 1000,
        allowed_ips: list[str] | None = None,
    ) -> tuple[APIKey, str]:
        """Create a new API key.
        
        Returns:
            Tuple of (APIKey object, plain text key)
            IMPORTANT: The plain text key is only returned once!
        """
        # Generate key
        full_key, key_prefix = APIKey.generate_key()
        key_hash = APIKeyService._hash_key(full_key)
        
        # Calculate expiration
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        # Create key record
        api_key = APIKey(
            organization_id=user.organization_id,
            created_by=user.id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            description=description,
            expires_at=expires_at,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_hour=rate_limit_per_hour,
            allowed_ips=allowed_ips,
            status=APIKeyStatus.ACTIVE,
        )
        
        db.add(api_key)
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(
            "API key created",
            key_id=str(api_key.id),
            organization_id=str(user.organization_id),
            created_by=str(user.id),
            scopes=scopes,
        )
        
        # Return key object and plain text key
        return api_key, full_key
    
    @staticmethod
    async def get_api_key_by_id(
        db: AsyncSession,
        key_id: UUID,
        organization_id: UUID,
    ) -> APIKey | None:
        """Get API key by ID."""
        result = await db.execute(
            select(APIKey).where(
                APIKey.id == key_id,
                APIKey.organization_id == organization_id,
            )
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_api_keys(
        db: AsyncSession,
        organization_id: UUID,
        status: APIKeyStatus | None = None,
        limit: int = 50,
    ) -> list[APIKey]:
        """List API keys for organization."""
        query = select(APIKey).where(
            APIKey.organization_id == organization_id,
        )
        
        if status:
            query = query.where(APIKey.status == status)
        
        query = query.order_by(APIKey.created_at.desc()).limit(limit)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def revoke_api_key(
        db: AsyncSession,
        api_key: APIKey,
        revoked_by: User,
    ) -> APIKey:
        """Revoke an API key."""
        api_key.status = APIKeyStatus.REVOKED
        api_key.revoked_at = datetime.utcnow()
        api_key.revoked_by = revoked_by.id
        
        await db.commit()
        
        logger.info(
            "API key revoked",
            key_id=str(api_key.id),
            revoked_by=str(revoked_by.id),
        )
        
        return api_key
    
    @staticmethod
    async def update_api_key(
        db: AsyncSession,
        api_key: APIKey,
        name: str | None = None,
        scopes: list[str] | None = None,
        description: str | None = None,
        status: APIKeyStatus | None = None,
        rate_limit_per_minute: int | None = None,
        rate_limit_per_hour: int | None = None,
    ) -> APIKey:
        """Update API key."""
        if name:
            api_key.name = name
        if scopes:
            api_key.scopes = scopes
        if description is not None:
            api_key.description = description
        if status:
            api_key.status = status
        if rate_limit_per_minute is not None:
            api_key.rate_limit_per_minute = rate_limit_per_minute
        if rate_limit_per_hour is not None:
            api_key.rate_limit_per_hour = rate_limit_per_hour
        
        api_key.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(api_key)
        
        logger.info(
            "API key updated",
            key_id=str(api_key.id),
        )
        
        return api_key
    
    @staticmethod
    async def validate_api_key(
        db: AsyncSession,
        key: str,
        ip_address: str | None = None,
    ) -> APIKey | None:
        """Validate an API key.
        
        Returns the APIKey if valid, None otherwise.
        """
        # Extract prefix from key
        if not key.startswith("wfa_"):
            return None
        
        key_without_prefix = key[4:]  # Remove 'wfa_' prefix
        key_prefix = key_without_prefix[:8]
        key_hash = APIKeyService._hash_key(key)
        
        # Find key by prefix and hash
        result = await db.execute(
            select(APIKey).where(
                APIKey.key_prefix == key_prefix,
                APIKey.key_hash == key_hash,
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return None
        
        # Check if key is valid
        if not api_key.is_valid():
            return None
        
        # Check IP restrictions
        if api_key.allowed_ips and ip_address:
            if ip_address not in api_key.allowed_ips:
                logger.warning(
                    "API key used from unauthorized IP",
                    key_id=str(api_key.id),
                    ip_address=ip_address,
                )
                return None
        
        return api_key
    
    @staticmethod
    async def check_rate_limit(
        db: AsyncSession,
        api_key: APIKey,
    ) -> bool:
        """Check if API key is within rate limits.
        
        Returns True if within limits, False if exceeded.
        """
        # Count requests in last minute
        minute_ago = datetime.utcnow() - timedelta(minutes=1)
        result = await db.execute(
            select(func.count(APIKeyUsageLog.id)).where(
                APIKeyUsageLog.api_key_id == api_key.id,
                APIKeyUsageLog.created_at >= minute_ago,
            )
        )
        minute_count = result.scalar() or 0
        
        if minute_count >= api_key.rate_limit_per_minute:
            return False
        
        # Count requests in last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        result = await db.execute(
            select(func.count(APIKeyUsageLog.id)).where(
                APIKeyUsageLog.api_key_id == api_key.id,
                APIKeyUsageLog.created_at >= hour_ago,
            )
        )
        hour_count = result.scalar() or 0
        
        if hour_count >= api_key.rate_limit_per_hour:
            return False
        
        return True
    
    @staticmethod
    async def log_api_key_usage(
        db: AsyncSession,
        api_key: APIKey,
        endpoint: str,
        method: str,
        status_code: int,
        ip_address: str | None = None,
        user_agent: str | None = None,
        response_time_ms: float | None = None,
        error_message: str | None = None,
    ) -> None:
        """Log API key usage."""
        # Update key stats
        api_key.record_usage()
        
        # Create usage log
        log = APIKeyUsageLog(
            api_key_id=api_key.id,
            organization_id=api_key.organization_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            ip_address=ip_address,
            user_agent=user_agent,
            response_time_ms=response_time_ms,
            error_message=error_message,
        )
        db.add(log)
        await db.commit()
    
    @staticmethod
    async def get_usage_stats(
        db: AsyncSession,
        api_key_id: UUID,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get usage statistics for an API key."""
        since = datetime.utcnow() - timedelta(days=days)
        
        # Total requests
        result = await db.execute(
            select(func.count(APIKeyUsageLog.id)).where(
                APIKeyUsageLog.api_key_id == api_key_id,
                APIKeyUsageLog.created_at >= since,
            )
        )
        total_requests = result.scalar() or 0
        
        # Successful requests (2xx)
        result = await db.execute(
            select(func.count(APIKeyUsageLog.id)).where(
                APIKeyUsageLog.api_key_id == api_key_id,
                APIKeyUsageLog.created_at >= since,
                APIKeyUsageLog.status_code >= 200,
                APIKeyUsageLog.status_code < 300,
            )
        )
        successful = result.scalar() or 0
        
        # Failed requests (4xx, 5xx)
        result = await db.execute(
            select(func.count(APIKeyUsageLog.id)).where(
                APIKeyUsageLog.api_key_id == api_key_id,
                APIKeyUsageLog.created_at >= since,
                APIKeyUsageLog.status_code >= 400,
            )
        )
        failed = result.scalar() or 0
        
        # Average response time
        result = await db.execute(
            select(func.avg(APIKeyUsageLog.response_time_ms)).where(
                APIKeyUsageLog.api_key_id == api_key_id,
                APIKeyUsageLog.created_at >= since,
            )
        )
        avg_response_time = result.scalar() or 0
        
        # Top endpoints
        result = await db.execute(
            select(
                APIKeyUsageLog.endpoint,
                func.count(APIKeyUsageLog.id).label("count"),
            )
            .where(
                APIKeyUsageLog.api_key_id == api_key_id,
                APIKeyUsageLog.created_at >= since,
            )
            .group_by(APIKeyUsageLog.endpoint)
            .order_by(func.count(APIKeyUsageLog.id).desc())
            .limit(5)
        )
        top_endpoints = [
            {"endpoint": row[0], "count": row[1]}
            for row in result.all()
        ]
        
        return {
            "total_requests": total_requests,
            "successful": successful,
            "failed": failed,
            "success_rate": (successful / total_requests * 100) if total_requests > 0 else 0,
            "avg_response_time_ms": round(avg_response_time, 2),
            "top_endpoints": top_endpoints,
            "period_days": days,
        }
