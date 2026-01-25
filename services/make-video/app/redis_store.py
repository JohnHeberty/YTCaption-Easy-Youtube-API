import json
import asyncio
import os
import logging
from typing import Optional, List
from datetime import datetime, timedelta

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
        return f"make_video:job:{job_id}"
    
    async def health_check(self) -> bool:
        """
        Check Redis connection health
        
        Returns:
            True if Redis is connected and responding
        """
        try:
            return await self.redis_client.health_check()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False
    
    def _serialize_job(self, job: Job) -> str:
        """Serialize Job to JSON"""
        job_dict = job.model_dump(mode='json')
        return json.dumps(job_dict)
    
    def _deserialize_job(self, data: str) -> Job:
        """Deserialize Job from JSON"""
        job_dict = json.loads(data)
        # Convert ISO strings to datetime
        for field in ['created_at', 'updated_at', 'completed_at', 'expires_at']:
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
        now = datetime.utcnow()
        expired_count = 0
        
        # Search for all job keys
        try:
            async for key in self.redis.scan_iter(match="make_video:job:*"):
                try:
                    data = await self.redis.get(key)
                    if data:
                        job = self._deserialize_job(data)
                        if job.expires_at and job.expires_at < now:
                            await self.redis.delete(key)
                            expired_count += 1
                            logger.info(f"🗑️ Removed expired job: {job.job_id}")
                except Exception as e:
                    logger.error(f"Error processing key {key}: {e}")
            
            if expired_count > 0:
                logger.info(f"🧹 Cleanup: {expired_count} expired jobs removed")
            
        except Exception as exc:
            logger.error(f"Error in cleanup: {exc}")
        
        return expired_count
    
    async def save_job(self, job: Job) -> None:
        """
        Save job to Redis
        
        Args:
            job: Job to save
        """
        key = self._job_key(job.job_id)
        data = self._serialize_job(job)
        
        # Calculate TTL in seconds
        ttl_seconds = self.cache_ttl_hours * 3600
        
        # Save with TTL
        await self.redis.setex(key, ttl_seconds, data)
        logger.debug(f"💾 Job saved: {job.job_id} (TTL: {self.cache_ttl_hours}h)")
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job from Redis
        
        Args:
            job_id: Job ID
        
        Returns:
            Job or None if not found
        """
        key = self._job_key(job_id)
        data = await self.redis.get(key)
        
        if data:
            return self._deserialize_job(data)
        return None
    
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete job from Redis
        
        Args:
            job_id: Job ID
        
        Returns:
            True if deleted, False if not found
        """
        key = self._job_key(job_id)
        result = await self.redis.delete(key)
        return result > 0
    
    async def list_jobs(self, status: Optional[str] = None, limit: int = 100) -> List[Job]:
        """
        List all jobs
        
        Args:
            status: Filter by status (optional)
            limit: Maximum number of jobs to return
        
        Returns:
            List of jobs
        """
        jobs = []
        count = 0
        
        async for key in self.redis.scan_iter(match="make_video:job:*"):
            if count >= limit:
                break
            
            try:
                data = await self.redis.get(key)
                if data:
                    job = self._deserialize_job(data)
                    if status is None or job.status == status:
                        jobs.append(job)
                        count += 1
            except Exception as e:
                logger.error(f"Error loading job from key {key}: {e}")
        
        # Sort by created_at descending
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        return jobs
