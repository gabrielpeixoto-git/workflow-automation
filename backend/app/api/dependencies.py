"""API dependencies and middleware."""

from typing import Callable

from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import get_logger
from app.services.cache_service import CacheKeys, CacheTTL, cache

logger = get_logger(__name__)


class CacheMiddleware(BaseHTTPMiddleware):
    """Middleware to cache API responses."""

    def __init__(
        self,
        app,
        ttl: int = CacheTTL.MEDIUM,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.ttl = ttl
        self.exclude_paths = exclude_paths or [
            "/api/auth/login",
            "/api/auth/register",
            "/api/health",
            "/api/docs",
            "/api/openapi.json",
            "/docs",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with caching."""
        # Skip non-GET requests
        if request.method != "GET":
            return await call_next(request)

        # Skip excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)

        # Build cache key
        cache_key = f"api:response:{path}:{hash(str(request.query_params))}"

        # Try to get from cache
        cached_response = await cache.get(cache_key)
        if cached_response:
            logger.debug("api_cache_hit", path=path)
            return Response(
                content=cached_response["body"],
                status_code=cached_response["status_code"],
                headers=cached_response["headers"],
                media_type=cached_response["media_type"],
            )

        # Execute request
        response = await call_next(request)

        # Cache successful responses
        if response.status_code == 200:
            body = b""
            async for chunk in response.body_iterator:
                body += chunk

            # Store in cache
            cached_data = {
                "body": body,
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "media_type": response.media_type,
            }
            await cache.set(cache_key, cached_data, ttl=self.ttl)
            logger.debug("api_cache_set", path=path, ttl=self.ttl)

            # Return new response with cached body
            return Response(
                content=body,
                status_code=response.status_code,
                headers=response.headers,
                media_type=response.media_type,
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware using Redis."""

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.exclude_paths = exclude_paths or [
            "/api/health",
            "/api/docs",
            "/docs",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check rate limit before processing."""
        # Skip excluded paths
        path = request.url.path
        if any(path.startswith(excluded) for excluded in self.exclude_paths):
            return await call_next(request)

        # Get client identifier
        client_id = request.client.host if request.client else "unknown"
        key = f"rate_limit:{client_id}:{path}"

        # Check current count
        current = await cache.incr(key)

        # Set expiration on first request
        if current == 1:
            await cache.expire(key, 60)

        # Check limit
        if current > self.requests_per_minute:
            logger.warning(
                "rate_limit_exceeded",
                client=client_id,
                path=path,
                count=current,
            )
            return Response(
                content='{"detail": "Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
            )

        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self.requests_per_minute - current)
        )

        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to add response timing headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add timing information to response."""
        import time

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Process-Time"] = str(process_time)
        return response
