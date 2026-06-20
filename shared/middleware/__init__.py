"""
Shared middleware for YTCaption microservices.

Provides standardized ASGI middleware for rate limiting and request body size
enforcement, eliminating identical copies across services.
"""
from __future__ import annotations

from common.middleware.rate_limiter import RateLimiterMiddleware
from common.middleware.body_size import BodySizeMiddleware

__all__ = ["RateLimiterMiddleware", "BodySizeMiddleware"]
