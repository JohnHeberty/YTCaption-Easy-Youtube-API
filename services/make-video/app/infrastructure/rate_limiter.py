"""
Sprint-08: Rate Limiting & Backpressure

Implements sliding window rate limiting to protect system from overload.
"""

import asyncio
from datetime import datetime, timedelta
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

from collections import deque
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class SlidingWindowRateLimiter:
    """Rate limiter using sliding window algorithm"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Timestamps of requests
        self.lock = asyncio.Lock()
    
    async def is_allowed(self) -> bool:
        """
        Check if request is allowed
        
        Returns:
            bool: True if request is allowed, False if rate limit exceeded
        """
        async with self.lock:
            now = now_brazil()
            cutoff = now - timedelta(seconds=self.window_seconds)
            
            # Remove old requests outside the window
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check if limit reached
            if len(self.requests) >= self.max_requests:
                return False
            
            # Add new request
            self.requests.append(now)
            return True
    
    async def wait_if_needed(self, timeout: float = 60.0) -> bool:
        """
        Wait until rate limit allows request (with timeout)
        
        Args:
            timeout: Maximum seconds to wait
            
        Returns:
            bool: True if allowed, False if timeout exceeded
        """
        start = now_brazil()
        
        while True:
            if await self.is_allowed():
                return True
            
            # Check timeout
            elapsed = (now_brazil() - start).total_seconds()
            if elapsed > timeout:
                logger.warning(f"Rate limit wait timeout after {elapsed}s")
                return False
            
            # Wait 100ms before retry
            await asyncio.sleep(0.1)
    
    async def get_wait_time(self) -> float:
        """
        Get estimated wait time until rate limit allows request
        
        Returns:
            float: Seconds to wait (0 if allowed now)
        """
        async with self.lock:
            if len(self.requests) < self.max_requests:
                return 0.0
            
            # Get oldest request in window
            oldest = self.requests[0]
            cutoff = now_brazil() - timedelta(seconds=self.window_seconds)
            wait_seconds = (oldest - cutoff).total_seconds()
            
            return max(0.0, wait_seconds)


class GlobalRateLimiter:
    """Global rate limiter for the entire service"""
    
    def __init__(self):
        self.video_creation_limiter = SlidingWindowRateLimiter(
            max_requests=30,  # 30 requests
            window_seconds=60  # per minute
        )
        self.api_call_limiter = SlidingWindowRateLimiter(
            max_requests=100,  # 100 calls
            window_seconds=60   # per minute
        )
    
    async def check_video_rate_limit(self) -> Tuple[bool, Optional[str]]:
        """
        Check if new video creation is allowed
        
        Returns:
            (bool, str): (is_allowed, reason_if_denied)
        """
        if not await self.video_creation_limiter.is_allowed():
            wait_time = await self.video_creation_limiter.get_wait_time()
            return False, f"Rate limit: {wait_time:.1f}s wait"
        return True, None
    
    async def check_api_rate_limit(self) -> Tuple[bool, Optional[str]]:
        """
        Check if new API call is allowed
        
        Returns:
            (bool, str): (is_allowed, reason_if_denied)
        """
        if not await self.api_call_limiter.is_allowed():
            wait_time = await self.api_call_limiter.get_wait_time()
            return False, f"API rate limit: {wait_time:.1f}s wait"
        return True, None


# Global instance
_rate_limiter = None


def get_rate_limiter() -> GlobalRateLimiter:
    """Get or create global rate limiter singleton"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = GlobalRateLimiter()
    return _rate_limiter


def update_global_rate_limiter(config: dict):
    """
    Update rate limiter configuration
    
    Args:
        config: Dictionary with keys like "max_video_requests", "video_window_seconds"
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = GlobalRateLimiter()
    
    if "max_video_requests" in config:
        _rate_limiter.video_creation_limiter.max_requests = config["max_video_requests"]
    if "video_window_seconds" in config:
        _rate_limiter.video_creation_limiter.window_seconds = config["video_window_seconds"]
    if "max_api_requests" in config:
        _rate_limiter.api_call_limiter.max_requests = config["max_api_requests"]
    if "api_window_seconds" in config:
        _rate_limiter.api_call_limiter.window_seconds = config["api_window_seconds"]
