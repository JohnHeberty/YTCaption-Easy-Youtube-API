"""
Orchestrator Redis store adapter using common.job_utils.
"""
import os
from typing import Optional

from common.log_utils import get_logger
from common.redis_utils import ResilientRedisStore
from common.job_utils.store import JobRedisStore

from modules.models import PipelineJobV2

logger = get_logger(__name__)

# Alias for backward compatibility
RedisStore = None  # Legacy alias, use OrchestratorJobStore


class OrchestratorJobStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
        )
        self._store = JobRedisStore(
            redis_store=self._resilient,
            service_name="orchestrator",
            ttl_hours=int(os.getenv('CACHE_TTL_HOURS', '24')),
        )
        self.redis = self._resilient.redis
        self.key_prefix = "orchestrator:job:"
        self.list_key = "orchestrator:jobs:list"

    def save_job(self, job: PipelineJobV2) -> PipelineJobV2:
        data = job.model_dump_json()
        key = f"{self.key_prefix}{job.id}"
        ttl = 24 * 3600
        self._resilient.setex(key, ttl, data)
        self.redis.zadd(self.list_key, {job.id: job.created_at.timestamp()})
        return job

    def get_job(self, job_id: str) -> Optional[PipelineJobV2]:
        key = f"{self.key_prefix}{job_id}"
        data = self._resilient.get(key)
        if not data:
            return None
        try:
            return PipelineJobV2.model_validate_json(data)
        except Exception as exc:
            logger.error("Error deserializing job %s: %s", job_id, exc)
            return None

    def update_job(self, job: PipelineJobV2) -> PipelineJobV2:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        self.redis.zrem(self.list_key, job_id)
        return self._resilient.delete(f"{self.key_prefix}{job_id}") > 0

    def list_jobs(self, limit: int = 100) -> list[PipelineJobV2]:
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

    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        all_ids = self.redis.zrevrange(self.list_key, 0, -1)
        removed = 0
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.is_expired:
                self.delete_job(job.id)
                removed += 1
        return removed

    def ping(self) -> bool:
        return self._resilient.ping()


# Factory functions for DI
_redis_store_instance = None


def get_store() -> OrchestratorJobStore:
    global _redis_store_instance
    if _redis_store_instance is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_store_instance = OrchestratorJobStore(redis_url=redis_url)
    return _redis_store_instance


# Alias for backward compatibility
RedisStore = OrchestratorJobStore