"""
Sliding-window in-memory rate limiter middleware.

Counts requests per remote IP within a rolling time window.
When the limit is exceeded the middleware returns HTTP 429 immediately,
without forwarding the request to the application.

Usage (in main.py)::

    from .middleware.rate_limiter import RateLimiterMiddleware

    if settings.get('rate_limit_enabled', False):
        app.add_middleware(
            RateLimiterMiddleware,
            max_requests=settings['rate_limit_requests'],   # e.g. 100
            window_seconds=settings['rate_limit_period'],   # e.g. 60
        )
"""
import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Dict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class _IPBucket:
    """Sliding-window counter for a single IP address."""

    __slots__ = ("timestamps", "lock")

    def __init__(self) -> None:
        self.timestamps: deque = deque()
        self.lock = asyncio.Lock()

    async def is_allowed(self, max_requests: int, window: timedelta) -> bool:
        async with self.lock:
            now = datetime.utcnow()
            cutoff = now - window
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()
            if len(self.timestamps) >= max_requests:
                return False
            self.timestamps.append(now)
            return True


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter ASGI middleware.

    Args:
        app:             The ASGI application.
        max_requests:    Maximum number of requests allowed per IP within
                         *window_seconds*.  Default: 100.
        window_seconds:  Rolling time window in seconds.  Default: 60.
        exclude_paths:   Iterable of path prefixes that bypass rate limiting
                         (e.g. ``["/health", "/metrics"]``).  Default: health
                         and metrics endpoints are excluded.
    """

    def __init__(
        self,
        app,
        max_requests: int = 100,
        window_seconds: int = 60,
        exclude_paths: tuple = ("/health", "/metrics", "/docs", "/openapi.json"),
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.exclude_paths = tuple(exclude_paths)
        self._buckets: Dict[str, _IPBucket] = {}
        self._buckets_lock = asyncio.Lock()

    async def _get_bucket(self, ip: str) -> _IPBucket:
        async with self._buckets_lock:
            if ip not in self._buckets:
                self._buckets[ip] = _IPBucket()
            return self._buckets[ip]

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for excluded paths
        if request.url.path.startswith(self.exclude_paths):
            return await call_next(request)

        ip = (request.client.host if request.client else "unknown")
        bucket = await self._get_bucket(ip)
        allowed = await bucket.is_allowed(self.max_requests, self.window)

        if not allowed:
            logger.warning(
                "Rate limit exceeded | ip=%s path=%s",
                ip,
                request.url.path,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Rate limit exceeded. Max {self.max_requests} requests "
                        f"per {int(self.window.total_seconds())}s."
                    ),
                    "error_code": "RATE_LIMIT_EXCEEDED",
                },
                headers={"Retry-After": str(int(self.window.total_seconds()))},
            )

        return await call_next(request)
