"""
Redis store adapter that delegates to common JobRedisStore
while preserving the service-specific VideoDownloadJob model
and backward-compatible API.
"""
import os
import json
import asyncio
from typing import Optional
from datetime import datetime, timedelta

from common.log_utils import get_logger
from common.redis_utils import ResilientRedisStore
from common.job_utils.store import JobRedisStore
from common.job_utils.models import StandardJob
from common.datetime_utils import now_brazil, ensure_timezone_aware

from app.core.models import VideoDownloadJob

logger = get_logger(__name__)


class VideoDownloadJobStore:
    """
    Redis store for VideoDownloadJob that delegates persistence
    to the common JobRedisStore while adding service-specific methods.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
            circuit_breaker_max_failures=int(os.getenv('REDIS_CIRCUIT_BREAKER_MAX_FAILURES', '5')),
            circuit_breaker_timeout=int(os.getenv('REDIS_CIRCUIT_BREAKER_TIMEOUT', '60')),
        )
        self._store = JobRedisStore(
            redis_store=self._resilient,
            service_name="video_downloader",
            ttl_hours=int(os.getenv('CACHE_TTL_HOURS', '24')),
        )
        self.redis = self._resilient.redis
        self._cleanup_task: Optional[asyncio.Task] = None
        self.cache_ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))

    def save_job(self, job: VideoDownloadJob) -> VideoDownloadJob:
        data = job.model_dump_json()
        key = f"job:{job.id}"
        ttl = self.cache_ttl_hours * 3600
        self._resilient.setex(key, ttl, data)
        self.redis.zadd("video_downloader:jobs:list", {job.id: job.created_at.timestamp()})
        return job

    def get_job(self, job_id: str) -> Optional[VideoDownloadJob]:
        key = f"job:{job_id}"
        data = self._resilient.get(key)
        if not data:
            return None
        try:
            return VideoDownloadJob.model_validate_json(data)
        except Exception as exc:
            logger.error("Error deserializing job %s: %s", job_id, exc)
            return None

    def update_job(self, job: VideoDownloadJob) -> VideoDownloadJob:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        key = f"job:{job_id}"
        self.redis.zrem("video_downloader:jobs:list", job_id)
        result = self._resilient.delete(key)
        return result > 0

    def list_jobs(self, limit: int = 100) -> list[VideoDownloadJob]:
        all_ids = self.redis.zrevrange("video_downloader:jobs:list", 0, -1)
        jobs = []
        for jid in all_ids[:limit * 2]:
            job = self.get_job(str(jid))
            if job:
                jobs.append(job)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def get_stats(self) -> dict:
        all_ids = self.redis.zrevrange("video_downloader:jobs:list", 0, -1)
        total = len(all_ids)
        by_status = {}
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job:
                status = job.status.value if hasattr(job.status, 'value') else str(job.status)
                by_status[status] = by_status.get(status, 0) + 1
        return {
            "total_jobs": total,
            "by_status": by_status,
            "cleanup_active": self._cleanup_task is not None,
            "redis_connected": self._resilient.ping(),
        }

    async def start_cleanup_task(self):
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Cleanup task started")

    async def stop_cleanup_task(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Cleanup task stopped")

    async def _cleanup_loop(self):
        interval = self.cleanup_interval_minutes * 60
        while True:
            try:
                await asyncio.sleep(interval)
                await self.cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Cleanup loop error: %s", exc)

    async def cleanup_expired(self) -> int:
        from pathlib import Path
        now = now_brazil()
        expired_count = 0
        all_ids = self.redis.zrevrange("video_downloader:jobs:list", 0, -1)
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.is_expired:
                if job.file_path:
                    fp = Path(job.file_path)
                    if fp.exists():
                        try:
                            fp.unlink()
                        except Exception:
                            pass
                self.delete_job(job.id)
                expired_count += 1
        return expired_count

    async def find_orphaned_jobs(self, max_age_minutes: int = 30) -> list[VideoDownloadJob]:
        orphaned = []
        now = now_brazil()
        max_age = timedelta(minutes=max_age_minutes)
        all_ids = self.redis.zrevrange("video_downloader:jobs:list", 0, -1)
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.started_at:
                age = now - job.started_at
                if age > max_age and job.status not in (
                    "completed", "failed", "cancelled"
                ):
                    orphaned.append(job)
        return orphaned

    async def get_queue_info(self) -> dict:
        jobs = self.list_jobs(limit=10000)
        queue_info = {
            "total_jobs": len(jobs),
            "by_status": {"queued": 0, "processing": 0, "completed": 0, "failed": 0},
            "oldest_job": None,
            "newest_job": None,
        }
        for job in jobs:
            s = job.status.value if hasattr(job.status, 'value') else str(job.status)
            if s in queue_info["by_status"]:
                queue_info["by_status"][s] += 1
        if jobs:
            newest = jobs[0]
            oldest = jobs[-1]
            queue_info["newest_job"] = {"job_id": newest.id, "created_at": newest.created_at.isoformat(), "status": newest.status.value}
            queue_info["oldest_job"] = {"job_id": oldest.id, "created_at": oldest.created_at.isoformat(), "status": oldest.status.value}
        return queue_info