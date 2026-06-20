"""
Standard Redis store for job persistence.

Provides a unified interface for saving, retrieving, updating,
and deleting jobs in Redis with consistent key naming and TTL.
"""
from __future__ import annotations

import json
import logging

from common.redis_utils import ResilientRedisStore
from common.job_utils.models import StandardJob, JobStatus

logger = logging.getLogger(__name__)


class JobRedisStore:
    def __init__(
        self,
        redis_store: ResilientRedisStore,
        service_name: str,
        ttl_hours: int = 24,
    ) -> None:
        self.redis = redis_store
        self.service_name = service_name
        self.key_prefix = f"{service_name}:job:"
        self.list_key = f"{service_name}:jobs:list"
        self.ttl_seconds = ttl_hours * 3600

    def _job_key(self, job_id: str) -> str:
        return f"{self.key_prefix}{job_id}"

    def save_job(self, job: StandardJob) -> bool:
        key = self._job_key(job.id)
        data = job.model_dump_json()
        saved = self.redis.setex(key, self.ttl_seconds, data)
        if saved:
            self.redis.redis.zadd(self.list_key, {job.id: job.created_at.timestamp()})
        return saved

    def get_job(self, job_id: str) -> StandardJob | None:
        key = self._job_key(job_id)
        data = self.redis.get(key)
        if not data:
            return None
        try:
            return StandardJob.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to deserialize job {job_id}: {e}")
            return None

    def update_job(self, job: StandardJob) -> bool:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        key = self._job_key(job_id)
        self.redis.redis.zrem(self.list_key, job_id)
        deleted = self.redis.delete(key)
        return deleted > 0

    def list_job_ids(self) -> list[str]:
        ids = self.redis.redis.zrevrange(self.list_key, 0, -1)
        return [str(jid) for jid in ids]

    def list_jobs(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[StandardJob]:
        all_ids = self.list_job_ids()
        jobs: list[StandardJob] = []
        for job_id in all_ids:
            job = self.get_job(job_id)
            if job is None:
                continue
            if status and job.status != status:
                continue
            jobs.append(job)
            if len(jobs) >= limit:
                break
        return jobs[offset : offset + limit] if offset else jobs[:limit]

    def get_stats(self) -> dict[str, int | dict[str, int]]:
        all_ids = self.list_job_ids()
        total = len(all_ids)
        by_status: dict[str, int] = {}
        for job_id in all_ids:
            job = self.get_job(job_id)
            if job:
                by_status[job.status] = by_status.get(job.status, 0) + 1
        return {"total_jobs": total, "by_status": by_status}

    def cleanup_expired(self) -> int:
        all_ids = self.list_job_ids()
        removed = 0
        for job_id in all_ids:
            job = self.get_job(job_id)
            if job and job.is_expired:
                if self.delete_job(job_id):
                    removed += 1
        return removed

    def find_orphaned(self, max_age_hours: int = 2) -> list[StandardJob]:
        all_ids = self.list_job_ids()
        orphaned: list[StandardJob] = []
        for job_id in all_ids:
            job = self.get_job(job_id)
            if job and not job.is_terminal:
                age = (job.created_at - job.created_at.__class__.now()).total_seconds()
                started = job.started_at
                if started:
                    elapsed_hours = (
                        (job.started_at.__class__.now() - started).total_seconds() / 3600
                    )
                    if elapsed_hours > max_age_hours:
                        orphaned.append(job)
        return orphaned
