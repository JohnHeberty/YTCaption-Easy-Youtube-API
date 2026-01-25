import json
import asyncio
import os
import logging
from typing import Optional, List
from datetime import datetime

# Use resilient Redis from common library
from common.redis_utils import ResilientRedisStore

from .models import Job

logger = logging.getLogger(__name__)


class RedisJobStore:
    """Shared job store using Redis (with resilience)"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize store with resilient Redis
        
        Args:
            redis_url: Redis connection URL
        """
        # Use ResilientRedisStore from common library
        self.redis_client = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
            circuit_breaker_max_failures=int(os.getenv('REDIS_CIRCUIT_BREAKER_MAX_FAILURES', '5')),
            circuit_breaker_timeout=int(os.getenv('REDIS_CIRCUIT_BREAKER_TIMEOUT', '60'))
        )
        
        # Keep compatible interface
        self.redis = self.redis_client.redis
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Read cache configurations from environment variables
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CACHE_CLEANUP_INTERVAL_MINUTES', '30'))
        
        logger.info("✅ Redis connected with resilience: %s", redis_url)
        logger.info("⏰ Cache TTL: %sh, Cleanup: %smin", 
                   self.cache_ttl_hours, self.cleanup_interval_minutes)
    
    def _job_key(self, job_id: str) -> str:
        """Generate Redis key for job"""
        return f"youtube_search:job:{job_id}"
    
    def _serialize_job(self, job: Job) -> str:
        """Serialize Job to JSON"""
        job_dict = job.model_dump(mode='json')
        return json.dumps(job_dict)
    
    def _deserialize_job(self, data: str) -> Job:
        """Deserialize Job from JSON"""
        job_dict = json.loads(data)
        # Convert ISO strings to datetime
        for field in ['created_at', 'completed_at', 'expires_at']:
            if job_dict.get(field):
                job_dict[field] = datetime.fromisoformat(job_dict[field])
        return Job(**job_dict)
    
    async def start_cleanup_task(self):
        """Start automatic cleanup task"""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("🧹 Cleanup task started")
    
    async def stop_cleanup_task(self):
        """Stop cleanup task"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("🛑 Cleanup task stopped")
    
    async def _cleanup_loop(self):
        """Cleanup loop with configurable interval"""
        cleanup_interval_seconds = self.cleanup_interval_minutes * 60
        
        while True:
            try:
                await asyncio.sleep(cleanup_interval_seconds)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in automatic cleanup: %s", exc)
    
    async def cleanup_expired(self) -> int:
        """Remove expired jobs from Redis"""
        now = datetime.now()
        expired_count = 0
        
        # Search for all job keys
        job_keys = self.redis.keys("youtube_search:job:*")
        
        for key in job_keys:
            try:
                data = self.redis.get(key)
                if not data:
                    continue
                
                job = self._deserialize_job(data)
                
                if job.expires_at < now:
                    # Remove job from Redis
                    self.redis.delete(key)
                    expired_count += 1
                    
            except Exception as exc:
                logger.error("Error processing %s: %s", key, exc)
        
        if expired_count > 0:
            logger.info("🧹 Cleanup: removed %s expired jobs", expired_count)
        
        return expired_count
    
    def save_job(self, job: Job) -> Job:
        """Save job to Redis with configurable TTL"""
        key = self._job_key(job.id)
        data = self._serialize_job(job)
        
        # Save with configurable TTL (convert hours to seconds)
        ttl_seconds = self.cache_ttl_hours * 3600
        self.redis.setex(key, ttl_seconds, data)
        
        logger.debug("💾 Job saved to Redis: %s (TTL: %sh)", job.id, self.cache_ttl_hours)
        return job
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID from Redis"""
        key = self._job_key(job_id)
        data = self.redis.get(key)
        
        if not data:
            return None
        
        try:
            return self._deserialize_job(data)
        except Exception as exc:
            logger.error("Error deserializing job %s: %s", job_id, exc)
            return None
    
    def update_job(self, job: Job) -> Job:
        """Update existing job in Redis"""
        return self.save_job(job)
    
    def delete_job(self, job_id: str) -> bool:
        """Delete job from Redis"""
        key = self._job_key(job_id)
        result = self.redis.delete(key)
        return result > 0
    
    def list_jobs(self, limit: int = 100) -> List[Job]:
        """List all jobs from Redis"""
        job_keys = self.redis.keys("youtube_search:job:*")
        jobs = []
        
        for key in job_keys[:limit]:
            try:
                data = self.redis.get(key)
                if data:
                    job = self._deserialize_job(data)
                    jobs.append(job)
            except Exception as exc:
                logger.error("Error loading job from %s: %s", key, exc)
        
        # Sort by creation date (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs
    
    def get_stats(self) -> dict:
        """Get Redis statistics"""
        job_keys = self.redis.keys("youtube_search:job:*")
        
        stats = {
            "total_jobs": len(job_keys),
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0
        }
        
        for key in job_keys:
            try:
                data = self.redis.get(key)
                if data:
                    job = self._deserialize_job(data)
                    stats[job.status.value] += 1
            except Exception:
                pass
        
        return stats
