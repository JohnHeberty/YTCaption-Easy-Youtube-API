"""
Make-video Redis store adapter using common.job_utils.
"""
import os
from typing import Optional

from common.redis_utils import ResilientRedisStore
from common.log_utils import get_logger
from common.job_utils.store import JobRedisStore
from common.datetime_utils import now_brazil

from app.core.models import MakeVideoJob

logger = get_logger(__name__)

class MakeVideoJobStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
        )
        self._store = JobRedisStore(
            redis_store=self._resilient,
            service_name="make_video",
            ttl_hours=int(os.getenv('CACHE_TTL_HOURS', '24')),
        )
        self.redis = self._resilient.redis
        self.key_prefix = "make_video:job:"
        self.list_key = "make_video:jobs:list"

    def save_job(self, job: MakeVideoJob) -> MakeVideoJob:
        data = job.model_dump_json()
        key = f"{self.key_prefix}{job.id}"
        ttl = 24 * 3600
        self._resilient.setex(key, ttl, data)
        self.redis.zadd(self.list_key, {job.id: job.created_at.timestamp()})
        return job

    def get_job(self, job_id: str) -> Optional[MakeVideoJob]:
        key = f"{self.key_prefix}{job_id}"
        data = self._resilient.get(key)
        if not data:
            return None
        try:
            return MakeVideoJob.model_validate_json(data)
        except Exception as exc:
            logger.error("Error deserializing job %s: %s", job_id, exc)
            return None

    def update_job(self, job: MakeVideoJob) -> MakeVideoJob:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        self.redis.zrem(self.list_key, job_id)
        return self._resilient.delete(f"{self.key_prefix}{job_id}") > 0

    def list_jobs(self, limit: int = 100) -> list[MakeVideoJob]:
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