"""
Audio-transcriber Redis store adapter using common.job_utils.
"""
import asyncio
import os
from datetime import timedelta
from typing import Optional

from common.redis_utils import ResilientRedisStore
from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.domain.models import AudioTranscriptionJob, JobStatus

logger = get_logger(__name__)


class RedisJobStore:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._resilient = ResilientRedisStore(
            redis_url=redis_url,
            max_connections=50,
            circuit_breaker_enabled=True,
        )
        self.redis = self._resilient.redis
        self.ttl_seconds = int(os.getenv("CACHE_TTL_HOURS", "24")) * 3600
        self.key_prefix = "audio_transcriber:job:"
        self.list_key = "audio_transcriber:jobs:list"
        self.queue_key = os.getenv("CELERY_DEFAULT_QUEUE", "audio_transcriber_queue")
        self._cleanup_task: Optional[asyncio.Task] = None

    @property
    def _raw_redis(self):
        return self.redis.redis if hasattr(self.redis, "redis") else self.redis

    def _job_key(self, job_id: str) -> str:
        return f"{self.key_prefix}{job_id}"

    def save_job(self, job: AudioTranscriptionJob) -> AudioTranscriptionJob:
        if hasattr(job, "updated_at"):
            job.updated_at = now_brazil()
        data = job.model_dump_json()
        key = self._job_key(job.id)
        self._raw_redis.setex(key, self.ttl_seconds, data)
        created_at = job.created_at if job.created_at else now_brazil()
        self._raw_redis.zadd(self.list_key, {job.id: created_at.timestamp()})
        return job

    def get_job(self, job_id: str) -> Optional[AudioTranscriptionJob]:
        data = self._raw_redis.get(self._job_key(job_id))
        if not data:
            return None
        try:
            return AudioTranscriptionJob.model_validate_json(data)
        except Exception as exc:
            logger.error("Error deserializing job %s: %s", job_id, exc)
            return None

    def update_job(self, job: AudioTranscriptionJob) -> AudioTranscriptionJob:
        return self.save_job(job)

    def delete_job(self, job_id: str) -> bool:
        self._raw_redis.zrem(self.list_key, job_id)
        return self._raw_redis.delete(self._job_key(job_id)) > 0

    def list_jobs(
        self,
        limit: int = 100,
        status: Optional[JobStatus] = None,
        offset: int = 0,
    ) -> list[AudioTranscriptionJob]:
        all_ids = self._raw_redis.zrevrange(self.list_key, 0, -1)
        jobs = []
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job:
                if status is not None and job.status != status:
                    continue
                jobs.append(job)
            if len(jobs) >= (offset + limit):
                break
        return jobs[offset: offset + limit]

    def get_stats(self) -> dict:
        all_ids = self._raw_redis.zrevrange(self.list_key, 0, -1)
        total = len(all_ids)
        by_status = {}
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job:
                s = job.status.value if hasattr(job.status, 'value') else str(job.status)
                by_status[s] = by_status.get(s, 0) + 1
        return {"total_jobs": total, "by_status": by_status}

    def cleanup_expired(self) -> int:
        all_ids = self._raw_redis.zrevrange(self.list_key, 0, -1)
        removed = 0
        for jid in all_ids:
            job = self.get_job(str(jid))
            if job and job.is_expired:
                self.delete_job(job.id)
                removed += 1
        return removed

    async def find_orphaned_jobs(self, max_age_minutes: int = 30) -> list[AudioTranscriptionJob]:
        now = now_brazil()
        threshold = timedelta(minutes=max_age_minutes)
        orphaned: list[AudioTranscriptionJob] = []

        for job in self.list_jobs(limit=5000):
            if job.status not in (JobStatus.PROCESSING, JobStatus.QUEUED):
                continue

            reference_time = job.started_at or job.updated_at or job.created_at
            if reference_time and (now - reference_time) > threshold:
                orphaned.append(job)

        return orphaned

    async def get_queue_info(self) -> dict:
        queue_length = self._raw_redis.llen(self.queue_key)
        return {
            "queue_name": self.queue_key,
            "pending_jobs": queue_length,
            "timestamp": now_brazil().isoformat(),
        }

    async def start_cleanup_task(self) -> None:
        if self._cleanup_task and not self._cleanup_task.done():
            return
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop_cleanup_task(self) -> None:
        if not self._cleanup_task:
            return
        self._cleanup_task.cancel()
        try:
            await self._cleanup_task
        except asyncio.CancelledError:
            pass
        finally:
            self._cleanup_task = None

    async def _cleanup_loop(self) -> None:
        interval_minutes = int(os.getenv("CACHE_CLEANUP_INTERVAL_MINUTES", "30"))
        while True:
            try:
                removed = self.cleanup_expired()
                if removed:
                    logger.info("🧹 Cleanup automático removeu %s jobs expirados", removed)
            except Exception as exc:
                logger.error("Erro no cleanup automático: %s", exc)
            await asyncio.sleep(max(interval_minutes, 1) * 60)


# Backward compatibility aliases
AudioTranscriptionJobStore = RedisJobStore