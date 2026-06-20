from __future__ import annotations

"""
Re-exports from shared middleware for backward compatibility.

Services should import directly from common.middleware:
    from common.middleware import RateLimiterMiddleware, BodySizeMiddleware
"""
from common.middleware import BodySizeMiddleware, RateLimiterMiddleware

__all__ = ["BodySizeMiddleware", "RateLimiterMiddleware"]
