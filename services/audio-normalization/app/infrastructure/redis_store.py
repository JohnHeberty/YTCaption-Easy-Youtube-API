"""
Audio-normalization Redis store adapter using common.job_utils.
"""
import os
from typing import Optional

from common.redis_utils import ResilientRedisStore
from common.log_utils import get_logger
from common.job_utils.store import JobRedisStore
from common.job_utils.models import StandardJob
from common.datetime_utils import now_brazil

from app.core.models import AudioNormJob

logger = get_logger(__name__)

class AudioNormJobStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
        )
        self._store = JobRedisStore(
            redis_store=self._resilient,
            service_name="audio_normalization",
            ttl_hours=int(os.getenv('CACHE_TTL_HOURS', '24')),
        )
        self.redis = self._resilient.redis
        self.key_prefix = "audio_normalization:job:"
        self.list_key = "audio_normalization:jobs:list"
        self._cleanup_task = None
        self.cleanup_interval_minutes = int(os.getenv('CLEANUP_INTERVAL_MINUTES', '30'))

    def save_job(self, job: AudioNormJob) -> AudioNormJob:
        data = job.model_dump_json()
        key = f"{self.key_prefix}{job.id}"
        ttl = 24 * 3600
        self._resilient.setex(key, ttl, data)
        self.redis.zadd(self.list_key, {job.id: job.created_at.timestamp()})
        return job

    def get_job(self, job_id: str) -> Optional[AudioNormJob]:
        key = f"{self.key_prefix}{job_id}"
        data = self._resilient.get(key)
        if not data:
            return None
        try:
            return AudioNormJob.model_validate_json(data)
        except Exception as exc:
            logger.error("Error deserializing job %s: %s", job_id, exc)
            return None

    def update_job(self, job: AudioNormJob) -> AudioNormJob:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        self.redis.zrem(self.list_key, job_id)
        return self._resilient.delete(f"{self.key_prefix}{job_id}") > 0

    def list_jobs(self, limit: int = 100) -> list[AudioNormJob]:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        jobs = []
        for jid in all_ids[:limit]:
            job = self.get_job(str(jid))
            if job:
                jobs.append(job)
        return jobs

    def get_stats(self) -> dict:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        total = len(all_ids)
        by_status = {}
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job:
                s = job.status.value if hasattr(job.status, 'value') else str(job.status)
                by_status[s] = by_status.get(s, 0) + 1
        return {"total_jobs": total, "by_status": by_status}

    def cleanup_expired(self) -> int:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        removed = 0
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.is_expired:
                self.delete_job(job.id)
                removed += 1
        return removed

    def find_orphaned_jobs(self, max_age_minutes: int = 30) -> list[AudioNormJob]:
        from datetime import timedelta
        orphaned = []
        now = now_brazil()
        max_age = timedelta(minutes=max_age_minutes)
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.started_at and not job.is_terminal:
                age = now - job.started_at
                if age > max_age:
                    orphaned.append(job)
        return orphaned

    async def start_cleanup_task(self):
        import asyncio
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self):
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except Exception:
                pass
            self._cleanup_task = None

    async def _cleanup_loop(self):
        import asyncio
        while True:
            try:
                await asyncio.sleep(self.cleanup_interval_minutes * 60)
                self.cleanup_expired()
            except asyncio.CancelledError:
                break

    async def get_queue_info(self) -> dict:
        jobs = self.list_jobs(limit=10000)
        by_status = {"queued": 0, "processing": 0, "completed": 0, "failed": 0}
        for job in jobs:
            s = job.status.value if hasattr(job.status, 'value') else str(job.status)
            if s in by_status:
                by_status[s] += 1
        return {
            "total_jobs": len(jobs),
            "by_status": by_status,
            "oldest_job": {
                "job_id": jobs[-1].id,
                "created_at": jobs[-1].created_at.isoformat(),
                "status": jobs[-1].status.value if hasattr(jobs[-1].status, 'value') else str(jobs[-1].status),
            } if jobs else None,
            "newest_job": {
                "job_id": jobs[0].id,
                "created_at": jobs[0].created_at.isoformat(),
                "status": jobs[0].status.value if hasattr(jobs[0].status, 'value') else str(jobs[0].status),
            } if jobs else None,
        }


# Backward-compatible alias expected by older modules
RedisJobStore = AudioNormJobStore