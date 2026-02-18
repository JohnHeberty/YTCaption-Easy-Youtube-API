"""
Distributed Rate Limiter usando Redis

Rate limiter distribuído com suporte a múltiplas instâncias do serviço.
Implementa sliding window counter usando Redis ZSET para precisão e performance.

Features:
- Distribuído: Funciona entre múltiplas instâncias
- Sliding Window: Janela deslizante (mais preciso que fixed window)
- Resiliente: Usa ResilientRedisStore com circuit breaker
- Por Cliente: Limites independentes por client_id
- Fallback: Degradação graceful se Redis falhar
"""

import time
import logging
from typing import Optional
from ..shared.exceptions_v2 import RedisUnavailableException

# Use resilient Redis from common library
try:
    from common.redis_utils import ResilientRedisStore
except ImportError:
    # Fallback if common library not available
    ResilientRedisStore = None

logger = logging.getLogger(__name__)

# Default configuration - Google/Netflix standards
DEFAULT_MAX_REQUESTS = 100        # Requests per window
DEFAULT_WINDOW_SECONDS = 60       # 1 minute window
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
REDIS_KEY_PREFIX = "rate_limit"
REDIS_KEY_TTL_MULTIPLIER = 2      # TTL = window * 2 (cleanup old keys)


class DistributedRateLimiter:
    """
    Distributed rate limiter using Redis ZSET
    
    Algorithm: Sliding Window Counter
    - Stores timestamp of each request in Redis ZSET
    - Removes expired requests from window
    - Counts requests in current window
    - Works across multiple service instances
    
    Complexity: O(log N) per check (N = requests in window)
    """
    
    def __init__(
        self,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        redis_url: str = DEFAULT_REDIS_URL,
        fallback_to_allow: bool = True
    ):
        """
        Initialize distributed rate limiter
        
        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
            redis_url: Redis connection URL
            fallback_to_allow: If True, allow requests when Redis is down
                               If False, deny requests when Redis is down
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.fallback_to_allow = fallback_to_allow
        
        # Initialize Redis connection
        if ResilientRedisStore is None:
            logger.warning("⚠️ ResilientRedisStore not available, using fallback mode")
            self.redis_client = None
            self.redis = None
        else:
            try:
                self.redis_client = ResilientRedisStore(
                    redis_url=redis_url,
                    max_connections=20,
                    circuit_breaker_enabled=True,
                    circuit_breaker_max_failures=3,
                    circuit_breaker_timeout=30
                )
                self.redis = self.redis_client.redis
                logger.info(
                    f"✅ DistributedRateLimiter initialized: "
                    f"{max_requests} req/{window_seconds}s (Redis: {redis_url})"
                )
            except Exception as e:
                logger.error(f"❌ Failed to initialize Redis: {e}")
                self.redis_client = None
                self.redis = None
    
    def _get_redis_key(self, client_id: str) -> str:
        """Generate Redis key for client"""
        return f"{REDIS_KEY_PREFIX}:{client_id}"
    
    def is_allowed(self, client_id: str = "global") -> bool:
        """
        Check if request is allowed (thread-safe, distributed)
        
        Args:
            client_id: Unique identifier for client (IP, user_id, API key, etc.)
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        # Fallback if Redis unavailable
        if self.redis is None:
            if self.fallback_to_allow:
                logger.warning(f"⚠️ Redis unavailable, allowing request (fallback)")
                return True
            else:
                logger.warning(f"⚠️ Redis unavailable, denying request")
                return False
        
        try:
            return self._check_rate_limit_redis(client_id)
        
        except Exception as e:
            logger.error(f"⚠️ Rate limiter error: {e}")
            
            # Fallback behavior
            if self.fallback_to_allow:
                logger.warning(f"⚠️ Allowing request due to error (fallback)")
                return True
            else:
                logger.warning(f"⚠️ Denying request due to error")
                return False
    
    def _check_rate_limit_redis(self, client_id: str) -> bool:
        """
        Check rate limit using Redis ZSET (sliding window)
        
        Algorithm:
        1. Remove expired entries (outside window)
        2. Count entries in current window
        3. If under limit, add new entry and allow
        4. If over limit, deny
        
        Redis commands used:
        - ZREMRANGEBYSCORE: Remove old entries
        - ZCARD: Count entries
        - ZADD: Add new entry
        - EXPIRE: Set TTL for cleanup
        """
        key = self._get_redis_key(client_id)
        now = time.time()
        window_start = now - self.window_seconds
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # 1. Remove expired entries (outside current window)
        pipe.zremrangebyscore(key, 0, window_start)
        
        # 2. Count current entries in window
        pipe.zcard(key)
        
        # 3. Add current request timestamp
        pipe.zadd(key, {str(now): now})
        
        # 4. Set TTL to auto-cleanup old keys (2x window duration)
        pipe.expire(key, self.window_seconds * REDIS_KEY_TTL_MULTIPLIER)
        
        # Execute pipeline
        results = pipe.execute()
        
        # Results: [removed_count, current_count, zadd_result, expire_result]
        current_count = results[1]
        
        # Check if under limit (count before adding current request)
        if current_count < self.max_requests:
            logger.debug(
                f"✅ Rate limit OK: {client_id} ({current_count + 1}/{self.max_requests})"
            )
            return True
        else:
            # Over limit - remove the entry we just added
            self.redis.zrem(key, str(now))
            logger.warning(
                f"⛔ Rate limit EXCEEDED: {client_id} ({current_count}/{self.max_requests})"
            )
            return False
    
    def get_remaining(self, client_id: str = "global") -> Optional[int]:
        """
        Get remaining requests for client
        
        Args:
            client_id: Client identifier
        
        Returns:
            Number of remaining requests, or None if Redis unavailable
        """
        if self.redis is None:
            return None
        
        try:
            key = self._get_redis_key(client_id)
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove expired and count current
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = pipe.execute()
            
            current_count = results[1]
            remaining = max(0, self.max_requests - current_count)
            
            return remaining
        
        except Exception as e:
            logger.error(f"Error getting remaining requests: {e}")
            return None
    
    def reset(self, client_id: str = "global"):
        """
        Reset rate limit for client (admin/testing only)
        
        Args:
            client_id: Client identifier
        """
        if self.redis is None:
            logger.warning("Cannot reset: Redis unavailable")
            return
        
        try:
            key = self._get_redis_key(client_id)
            self.redis.delete(key)
            logger.info(f"🔄 Rate limit reset: {client_id}")
        
        except Exception as e:
            logger.error(f"Error resetting rate limit: {e}")
    
    def get_stats(self, client_id: str = "global") -> dict:
        """
        Get detailed stats for client
        
        Args:
            client_id: Client identifier
        
        Returns:
            Dictionary with stats: current, remaining, limit, window, reset_at
        """
        if self.redis is None:
            return {
                "available": False,
                "error": "Redis unavailable"
            }
        
        try:
            key = self._get_redis_key(client_id)
            now = time.time()
            window_start = now - self.window_seconds
            
            # Get current count
            pipe = self.redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.ttl(key)
            results = pipe.execute()
            
            current_count = results[1]
            ttl = results[2]
            remaining = max(0, self.max_requests - current_count)
            
            # Calculate reset time (oldest entry + window duration)
            oldest_entries = self.redis.zrange(key, 0, 0, withscores=True)
            reset_at = None
            if oldest_entries:
                oldest_timestamp = oldest_entries[0][1]
                reset_at = oldest_timestamp + self.window_seconds
            
            return {
                "available": True,
                "current": current_count,
                "remaining": remaining,
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
                "reset_at": reset_at,
                "ttl": ttl
            }
        
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {
                "available": False,
                "error": str(e)
            }


# Factory function for easy instantiation
def create_rate_limiter(
    max_requests: int = DEFAULT_MAX_REQUESTS,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    redis_url: Optional[str] = None
) -> DistributedRateLimiter:
    """
    Factory to create DistributedRateLimiter with defaults
    
    Args:
        max_requests: Max requests per window
        window_seconds: Window duration in seconds
        redis_url: Redis URL (uses default if None)
    
    Returns:
        Configured DistributedRateLimiter instance
    """
    return DistributedRateLimiter(
        max_requests=max_requests,
        window_seconds=window_seconds,
        redis_url=redis_url or DEFAULT_REDIS_URL,
        fallback_to_allow=True  # Allow requests if Redis down
    )
