import json
import asyncio
import os
import logging
from typing import Optional, List
from datetime import datetime, timedelta

# Use resilient Redis from common library
from common.redis_utils import ResilientRedisStore

from ..core.models import Job

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
        
        # Keep compatible interface - Redis client síncrono
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
            # Redis operations são síncronas no ResilientRedisStore
            self.redis.ping()
            return True
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
        
        # Search for all job keys (operação síncrona)
        try:
            for key in self.redis.scan_iter(match="make_video:job:*"):
                try:
                    data = self.redis.get(key)
                    if data:
                        job = self._deserialize_job(data)
                        if job.expires_at and job.expires_at < now:
                            self.redis.delete(key)
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
        
        # Save with TTL (operação síncrona)
        self.redis.setex(key, ttl_seconds, data)
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
        data = self.redis.get(key)  # Operação síncrona
        
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
        result = self.redis.delete(key)  # Operação síncrona
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
        
        # Operações síncronas
        for key in self.redis.scan_iter(match="make_video:job:*"):
            if count >= limit:
                break
            
            try:
                data = self.redis.get(key)
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
    
    def get_stats(self) -> dict:
        """
        Get statistics about jobs in Redis
        
        Returns:
            Dictionary with job counts by status
        """
        stats = {
            "queued": 0,
            "processing": 0,
            "completed": 0,
            "failed": 0,
            "total": 0
        }
        
        try:
            for key in self.redis.scan_iter(match="make_video:job:*"):
                try:
                    data = self.redis.get(key)
                    if data:
                        job = self._deserialize_job(data)
                        stats["total"] += 1
                        
                        # Count by status
                        if job.status == "queued":
                            stats["queued"] += 1
                        elif job.status == "processing":
                            stats["processing"] += 1
                        elif job.status == "completed":
                            stats["completed"] += 1
                        elif job.status == "failed":
                            stats["failed"] += 1
                except Exception as e:
                    logger.debug(f"Error processing key {key} for stats: {e}")
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
        
        return stats
    
    async def cleanup_all_jobs(self) -> int:
        """
        Remove ALL jobs from Redis (DANGEROUS - use with caution)
        
        Returns:
            Number of jobs removed
        """
        removed_count = 0
        
        try:
            keys = list(self.redis.scan_iter(match="make_video:job:*"))
            if keys:
                removed_count = self.redis.delete(*keys)
                logger.warning(f"🔥 ALL JOBS REMOVED: {removed_count} jobs deleted")
        except Exception as e:
            logger.error(f"Error removing all jobs: {e}")
        
        return removed_count
    
    async def find_orphaned_jobs(self, max_age_minutes: int = 30) -> List[Job]:
        """
        Find jobs that are stuck in processing state for too long
        
        Args:
            max_age_minutes: Maximum time a job can be processing
        
        Returns:
            List of orphaned jobs
        """
        orphaned = []
        now = datetime.utcnow()
        max_age = timedelta(minutes=max_age_minutes)
        
        try:
            for key in self.redis.scan_iter(match="make_video:job:*"):
                try:
                    data = self.redis.get(key)
                    if data:
                        job = self._deserialize_job(data)
                        
                        # Check if processing for too long
                        if job.status == "processing":
                            age = now - job.updated_at
                            if age > max_age:
                                orphaned.append(job)
                                logger.warning(
                                    f"⚠️ Orphaned job found: {job.job_id} "
                                    f"(processing for {age.total_seconds()/60:.1f} minutes)"
                                )
                except Exception as e:
                    logger.debug(f"Error processing key {key}: {e}")
        except Exception as e:
            logger.error(f"Error finding orphaned jobs: {e}")
        
        return orphaned
    
    async def get_queue_info(self) -> dict:
        """
        Get information about the job queue
        
        Returns:
            Dictionary with queue statistics
        """
        queue_info = {
            "total_jobs": 0,
            "by_status": {
                "queued": 0,
                "processing": 0,
                "completed": 0,
                "failed": 0
            },
            "oldest_job": None,
            "newest_job": None
        }
        
        try:
            jobs = await self.list_jobs(limit=10000)  # Get all jobs
            queue_info["total_jobs"] = len(jobs)
            
            # Count by status
            for job in jobs:
                if job.status in queue_info["by_status"]:
                    queue_info["by_status"][job.status] += 1
            
            # Find oldest and newest
            if jobs:
                # Jobs are already sorted by created_at descending
                queue_info["newest_job"] = {
                    "job_id": jobs[0].job_id,
                    "created_at": jobs[0].created_at.isoformat(),
                    "status": jobs[0].status
                }
                queue_info["oldest_job"] = {
                    "job_id": jobs[-1].job_id,
                    "created_at": jobs[-1].created_at.isoformat(),
                    "status": jobs[-1].status
                }
        
        except Exception as e:
            logger.error(f"Error getting queue info: {e}")
        
        return queue_info
    
    async def delete_job(self, job_id: str) -> bool:
        """
        Delete a job from Redis
        
        Args:
            job_id: Job ID to delete
        
        Returns:
            True if deleted, False if not found
        """
        try:
            key = self._job_key(job_id)
            result = self.redis.delete(key)
            if result > 0:
                logger.info(f"Job deleted: {job_id}")
                return True
            else:
                logger.warning(f"Job not found for deletion: {job_id}")
                return False
        except Exception as e:
            logger.error(f"Error deleting job {job_id}: {e}")
            return False
