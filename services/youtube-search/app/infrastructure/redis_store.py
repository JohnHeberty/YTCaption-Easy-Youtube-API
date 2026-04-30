"""
YouTube search Redis store adapter.
"""
import os
import json
from typing import Optional, List
from datetime import timedelta

from common.redis_utils import ResilientRedisStore
from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.domain.models import YouTubeSearchJob, JobStatus, JobListResponse

logger = get_logger(__name__)


class YouTubeSearchJobStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
        )
        self.redis = self._resilient.redis
        self.key_prefix = "youtube_search:job:"
        self.list_key = "youtube_search:jobs:list"
        self.ttl_hours = int(os.getenv('CACHE_TTL_HOURS', '24'))
        self.ttl_seconds = self.ttl_hours * 3600

    def _job_key(self, job_id: str) -> str:
        return f"{self.key_prefix}{job_id}"

    def save_job(self, job: YouTubeSearchJob) -> bool:
        key = self._job_key(job.id)
        data = job.model_dump_json()
        saved = self._resilient.setex(key, self.ttl_seconds, data)
        if saved:
            self.redis.zadd(self.list_key, {job.id: job.created_at.timestamp()})
        return saved

    def get_job(self, job_id: str) -> Optional[YouTubeSearchJob]:
        key = self._job_key(job_id)
        data = self._resilient.get(key)
        if data:
            return YouTubeSearchJob.model_validate_json(data)
        return None

    def update_job(self, job: YouTubeSearchJob) -> bool:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        key = self._job_key(job_id)
        deleted = self._resilient.delete(key)
        if deleted:
            self.redis.zrem(self.list_key, job_id)
        return deleted

    def list_jobs(self, limit: int = 20) -> List[YouTubeSearchJob]:
        job_ids = self.redis.zrevrange(self.list_key, 0, limit - 1)
        jobs = []
        for job_id in job_ids:
            job = self.get_job(job_id)
            if job:
                jobs.append(job)
        return jobs

    def get_stats(self) -> dict:
        total = self.redis.zcard(self.list_key)
        by_status = {}
        for job_id in self.redis.zrange(self.list_key, 0, -1):
            job = self.get_job(job_id)
            if job:
                status = job.status.value
                by_status[status] = by_status.get(status, 0) + 1
        return {"total_jobs": total, "by_status": by_status}

    def ping(self) -> bool:
        try:
            return self.redis.ping()
        except Exception:
            return False

    async def start_cleanup_task(self):
        pass

    async def stop_cleanup_task(self):
        pass