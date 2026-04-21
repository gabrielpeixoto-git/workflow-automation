"""Redis caching service for workflow automation.

This module provides a comprehensive caching layer with Redis backend,
supporting TTL, cache invalidation, and decorators for easy integration.
"""

import functools
import hashlib
import json
import pickle
from typing import Any, Callable, TypeVar

import redis.asyncio as redis
from app.core.config import get_settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

T = TypeVar("T")


class CacheService:
    """Redis-based caching service."""

    _instance = None
    _redis_client: redis.Redis | None = None

    def __new__(cls):
        """Singleton pattern to ensure single Redis connection."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def redis(self) -> redis.Redis:
        """Get or create Redis client."""
        if self._redis_client is None:
            self._redis_client = redis.from_url(
                settings.redis_url or "redis://localhost:6379/0",
                decode_responses=False,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=20,
            )
        return self._redis_client

    async def close(self):
        """Close Redis connection."""
        if self._redis_client:
            await self._redis_client.close()
            self._redis_client = None

    def _serialize(self, value: Any) -> bytes:
        """Serialize value to bytes."""
        return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to value."""
        return pickle.loads(data)

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from prefix and arguments."""
        key_parts = [prefix]

        # Add args
        for arg in args:
            key_parts.append(str(arg))

        # Add sorted kwargs
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")

        key = ":".join(key_parts)

        # Hash if too long
        if len(key) > 250:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            return f"{prefix}:hash:{key_hash}"

        return key

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        try:
            data = await self.redis.get(key)
            if data:
                logger.debug(f"cache_hit: {key}")
                return self._deserialize(data)
            logger.debug(f"cache_miss: {key}")
            return None
        except Exception as e:
            logger.error(f"cache_get_error: {key}, error={e}")
            return None

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 300,
        nx: bool = False,
    ) -> bool:
        """Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (default: 5 minutes)
            nx: Only set if key does not exist
        """
        try:
            data = self._serialize(value)
            result = await self.redis.set(key, data, ex=ttl, nx=nx)
            logger.debug(f"cache_set: {key}, ttl={ttl}, success={bool(result)}")
            return bool(result)
        except Exception as e:
            logger.error(f"cache_set_error: {key}, error={e}")
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache."""
        try:
            result = await self.redis.delete(key)
            logger.debug(f"cache_delete: {key}, deleted={bool(result)}")
            return bool(result)
        except Exception as e:
            logger.error(f"cache_delete_error: {key}, error={e}")
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern."""
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                result = await self.redis.delete(*keys)
                logger.debug(f"cache_delete_pattern: {pattern}, deleted={result}")
                return result
            return 0
        except Exception as e:
            logger.error(f"cache_delete_pattern_error: {pattern}, error={e}")
            return 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            result = await self.redis.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"cache_exists_error: {key}, error={e}")
            return False

    async def ttl(self, key: str) -> int:
        """Get remaining TTL for key."""
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error(f"cache_ttl_error: {key}, error={e}")
            return -2

    async def incr(self, key: str, amount: int = 1) -> int:
        """Increment counter."""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"cache_incr_error: {key}, error={e}")
            return 0

    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key."""
        try:
            result = await self.redis.expire(key, ttl)
            return bool(result)
        except Exception as e:
            logger.error(f"cache_expire_error: {key}, error={e}")
            return False

    async def ping(self) -> bool:
        """Check if Redis is available."""
        try:
            result = await self.redis.ping()
            return result
        except Exception as e:
            logger.error(f"cache_ping_error: {e}")
            return False

    def cached(
        self,
        prefix: str,
        ttl: int = 300,
        key_builder: Callable | None = None,
    ):
        """Decorator to cache function results.

        Args:
            prefix: Cache key prefix
            ttl: Time to live in seconds
            key_builder: Optional custom key builder function
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Skip cache if requested
                if kwargs.pop("skip_cache", False):
                    return await func(*args, **kwargs)

                # Build cache key
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    # Extract relevant args (skip self, db, etc.)
                    cache_args = [
                        arg for arg in args
                        if not isinstance(arg, (type, object)) or type(arg).__name__ not in ["AsyncSession", "AsyncSessionLocal"]
                    ]
                    cache_kwargs = {k: v for k, v in kwargs.items() if k != "db"}
                    cache_key = self._make_key(prefix, *cache_args, **cache_kwargs)

                # Try to get from cache
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    return cached_value

                # Execute function
                result = await func(*args, **kwargs)

                # Cache result
                await self.set(cache_key, result, ttl=ttl)

                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                # For sync functions, just execute without caching
                return func(*args, **kwargs)

            # Return appropriate wrapper based on function type
            import inspect
            if inspect.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def invalidate(self, prefix: str, *args, **kwargs):
        """Decorator to invalidate cache after function execution.

        Args:
            prefix: Cache key prefix to invalidate
        """
        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                result = await func(*args, **kwargs)

                # Build pattern and delete
                pattern = f"{prefix}:*"
                if args or kwargs:
                    cache_args = [
                        arg for arg in args
                        if not isinstance(arg, (type, object)) or type(arg).__name__ not in ["AsyncSession", "AsyncSessionLocal"]
                    ]
                    cache_kwargs = {k: v for k, v in kwargs.items() if k != "db"}
                    key = self._make_key(prefix, *cache_args, **cache_kwargs)
                    pattern = f"{key}*"

                await self.delete_pattern(pattern)
                return result

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                result = func(*args, **kwargs)
                # Invalidate cache for sync functions too
                return result

            import inspect
            if inspect.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator


# Global cache instance
cache = CacheService()


# Cache key prefixes for different entities
class CacheKeys:
    """Cache key prefixes."""

    WORKFLOW = "workflow"
    WORKFLOW_LIST = "workflow:list"
    WORKFLOW_STEPS = "workflow:steps"
    EXECUTION = "execution"
    EXECUTION_LIST = "execution:list"
    EXECUTION_LOGS = "execution:logs"
    ANALYTICS = "analytics"
    DASHBOARD = "dashboard"
    INTEGRATION = "integration"
    TEMPLATE = "template"
    USER = "user"
    ORG = "org"
    API_KEY = "apikey"


# TTL configurations
class CacheTTL:
    """Cache TTL configurations in seconds."""

    SHORT = 60  # 1 minute
    MEDIUM = 300  # 5 minutes
    LONG = 1800  # 30 minutes
    VERY_LONG = 3600  # 1 hour
    DASHBOARD = 120  # 2 minutes - dashboard data refreshes often
    ANALYTICS = 600  # 10 minutes - analytics can be stale
