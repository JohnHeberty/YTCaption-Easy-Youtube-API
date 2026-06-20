from __future__ import annotations

"""
Re-exports from shared middleware for backward compatibility.

Services should import directly from common.middleware:
    from common.middleware import RateLimiterMiddleware
"""
from common.middleware import RateLimiterMiddleware

__all__ = ["RateLimiterMiddleware"]
