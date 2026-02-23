"""
Distributed Rate Limiter using Redis

Rate limiter distribuído para múltiplas instâncias do serviço.
Implementa sliding window counter para precisão.

Adaptado do padrão make-video para audio-transcriber.
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_REQUESTS = 100        # Requests per window
DEFAULT_WINDOW_SECONDS = 60       # 1 minute window
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
REDIS_KEY_PREFIX = "rate_limit:audio_transcriber"
REDIS_KEY_TTL_MULTIPLIER = 2      # TTL = window * 2 (cleanup old keys)


class DistributedRateLimiter:
    """
    Distributed rate limiter using Redis ZSET.
    
    Algorithm: Sliding Window Counter
    - Stores timestamp of each request in Redis ZSET
    - Removes expired requests from window
    - Counts requests in current window
    - Works across multiple service instances
    
    Use cases para audio-transcriber:
    - Limitar transcrições simultâneas por cliente
    - Prevenir abuse de API
    - Proteger GPU de sobrecarga
    - Rate limit por engine (faster-whisper, openai, whisperx)
    
    Complexity: O(log N) per check (N = requests in window)
    """
    
    def __init__(
        self,
        redis_client,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        fallback_to_allow: bool = True
    ):
        """
        Initialize distributed rate limiter
        
        Args:
            redis_client: ResilientRedisStore instance
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
            fallback_to_allow: If True, allow requests when Redis is down
                               If False, deny requests when Redis is down
        """
        self.redis_client = redis_client
        self.redis = redis_client.redis if redis_client else None
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.fallback_to_allow = fallback_to_allow
        
        if self.redis:
            logger.info(
                f"✅ DistributedRateLimiter initialized: "
                f"{max_requests} req/{window_seconds}s"
            )
        else:
            logger.warning("⚠️ Redis not available, using fallback mode")
    
    def _get_redis_key(self, client_id: str) -> str:
        """Generate Redis key for client"""
        return f"{REDIS_KEY_PREFIX}:{client_id}"
    
    def is_allowed(self, client_id: str = "global") -> bool:
        """
        Check if request is allowed for client.
        
        Args:
            client_id: Client identifier (IP, user_id, etc). Default "global"
        
        Returns:
            True if request is allowed, False if rate limited
        """
        if not self.redis:
            # Redis unavailable, use fallback
            return self.fallback_to_allow
        
        try:
            key = self._get_redis_key(client_id)
            now = time.time()
            window_start = now - self.window_seconds
            
            # Pipeline para performance
            pipe = self.redis.pipeline()
            
            # 1. Remove requests fora da janela
            pipe.zremrangebyscore(key, '-inf', window_start)
            
            # 2. Conta requests na janela atual
            pipe.zcard(key)
            
            # 3. Adiciona request atual
            pipe.zadd(key, {str(now): now})
            
            # 4. Define TTL
            ttl = self.window_seconds * REDIS_KEY_TTL_MULTIPLIER
            pipe.expire(key, ttl)
            
            # Executa pipeline
            results = pipe.execute()
            current_count = results[1]  # Resultado do zcard
            
            # Verifica se excedeu limite
            if current_count >= self.max_requests:
                logger.warning(
                    f"🚫 Rate limit exceeded for {client_id}: "
                    f"{current_count}/{self.max_requests} in {self.window_seconds}s"
                )
                # Remove a request que acabamos de adicionar
                self.redis.zrem(key, str(now))
                return False
            
            logger.debug(
                f"✅ Request allowed for {client_id}: "
                f"{current_count + 1}/{self.max_requests}"
            )
            return True
            
        except Exception as e:
            logger.error(f"❌ Rate limiter error: {e}")
            return self.fallback_to_allow
    
    def get_usage(self, client_id: str = "global") -> dict:
        """
        Get current usage for client.
        
        Args:
            client_id: Client identifier
        
        Returns:
            Dict with usage info: {
                'current': int,
                'limit': int,
                'window_seconds': int,
                'remaining': int,
                'reset_at': float (timestamp)
            }
        """
        if not self.redis:
            return {
                'current': 0,
                'limit': self.max_requests,
                'window_seconds': self.window_seconds,
                'remaining': self.max_requests,
                'reset_at': time.time() + self.window_seconds
            }
        
        try:
            key = self._get_redis_key(client_id)
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove expirados e conta
            self.redis.zremrangebyscore(key, '-inf', window_start)
            current = self.redis.zcard(key)
            
            # Calcula quando o limite reseta (request mais antigo + window)
            oldest = self.redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_timestamp = oldest[0][1]
                reset_at = oldest_timestamp + self.window_seconds
            else:
                reset_at = now + self.window_seconds
            
            return {
                'current': current,
                'limit': self.max_requests,
                'window_seconds': self.window_seconds,
                'remaining': max(0, self.max_requests - current),
                'reset_at': reset_at
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting usage: {e}")
            return {
                'current': 0,
                'limit': self.max_requests,
                'window_seconds': self.window_seconds,
                'remaining': self.max_requests,
                'reset_at': time.time() + self.window_seconds
            }
    
    def reset(self, client_id: str = "global"):
        """
        Reset rate limit for client.
        
        Args:
            client_id: Client identifier
        """
        if not self.redis:
            return
        
        try:
            key = self._get_redis_key(client_id)
            self.redis.delete(key)
            logger.info(f"🔄 Rate limit reset for {client_id}")
        except Exception as e:
            logger.error(f"❌ Error resetting rate limit: {e}")
