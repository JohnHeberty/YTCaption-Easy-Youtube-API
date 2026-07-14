"""
Make-video Redis store adapter using common.job_utils.
"""
from __future__ import annotations

import os
from typing import Any

from common.redis_utils import ResilientRedisStore
from common.log_utils import get_logger
from common.job_utils.store import JobRedisStore
from common.datetime_utils import now_brazil

from app.core.models import MakeVideoJob
from app.core.constants import (
    REDIS_MAX_CONNECTIONS,
    REDIS_JOB_TTL_SECONDS,
    DEFAULT_LIST_LIMIT,
    ORPHAN_AGE_MINUTES,
    ORPHAN_SCAN_MAX_JOBS,
)

logger = get_logger(__name__)

class MakeVideoJobStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=REDIS_MAX_CONNECTIONS,
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
        ttl = REDIS_JOB_TTL_SECONDS
        self._resilient.setex(key, ttl, data)
        self.redis.zadd(self.list_key, {job.id: job.created_at.timestamp()})
        return job

    def get_job(self, job_id: str) -> MakeVideoJob | None:
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

    def list_jobs(self, limit: int = DEFAULT_LIST_LIMIT) -> list[MakeVideoJob]:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        jobs = []
        for jid in all_ids[:limit]:
            job = self.get_job(str(jid))
            if job:
                jobs.append(job)
        return jobs

    def get_stats(self) -> dict[str, Any]:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        total = len(all_ids)
        by_status = {}
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job:
                s = job.status.value if hasattr(job.status, 'value') else str(job.status)
                by_status[s] = by_status.get(s, 0) + 1
        return {"total_jobs": total, "by_status": by_status}

    def find_orphaned_jobs(self, max_age_minutes: int = ORPHAN_AGE_MINUTES) -> list[MakeVideoJob]:
        all_jobs = self.list_jobs(limit=ORPHAN_SCAN_MAX_JOBS)
        orphaned = []
        for job in all_jobs:
            if job is None or job.is_terminal:
                continue
            if job.started_at:
                elapsed = (now_brazil() - job.started_at).total_seconds() / 60
                if elapsed > max_age_minutes:
                    orphaned.append(job)
            elif job.created_at:
                elapsed = (now_brazil() - job.created_at).total_seconds() / 60
                if elapsed > max_age_minutes:
                    orphaned.append(job)
        return orphaned

    def cleanup_expired(self) -> int:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        removed = 0
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.is_expired:
                self.delete_job(job.id)
                removed += 1
        return removed