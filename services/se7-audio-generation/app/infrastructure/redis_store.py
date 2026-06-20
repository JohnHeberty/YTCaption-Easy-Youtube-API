from typing import Optional

from common.log_utils import get_logger
from common.redis_utils.resilient_store import ResilientRedisStore, CircuitBreakerOpenError

from app.core.constants import (
    JOB_PREFIX,
    JOB_TTL_SECONDS,
    VOICE_PREFIX,
    VOICE_INDEX_KEY,
    VOICE_LIST_KEY,
)
from app.domain.models import AudioGenerationJob, VoiceProfile
from app.domain.interfaces import IJobStore, IVoiceStore

logger = get_logger(__name__)


class JobRedisStore(IJobStore):
    """Persistence layer for audio generation jobs using ResilientRedisStore."""

    def __init__(self, redis_store: ResilientRedisStore):
        self._store = redis_store
        self._list_key = VOICE_LIST_KEY.replace("voices", "jobs")

    def save_job(self, job: AudioGenerationJob) -> None:
        key = f"{JOB_PREFIX}{job.id}"
        data = job.model_dump_json()
        self._store.setex(key, JOB_TTL_SECONDS, data)
        try:
            score = job.created_at.timestamp() if job.created_at else 0
            self._store.redis.zadd(self._list_key, {job.id: score})
        except (CircuitBreakerOpenError, Exception) as e:
            logger.warning(f"Failed to add job to index: {e}")

    def get_job(self, job_id: str) -> Optional[AudioGenerationJob]:
        data = self._store.get(f"{JOB_PREFIX}{job_id}")
        if not data:
            return None
        try:
            return AudioGenerationJob.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to deserialize job {job_id}: {e}")
            return None

    def update_job(self, job: AudioGenerationJob) -> None:
        self.save_job(job)

    def list_jobs(self, limit: int = 20) -> list[AudioGenerationJob]:
        try:
            job_ids = self._store.redis.zrevrange(self._list_key, 0, limit - 1)
        except (CircuitBreakerOpenError, Exception) as e:
            logger.warning(f"Failed to list jobs from index: {e}")
            return []
        jobs = []
        for jid in job_ids:
            job = self.get_job(jid)
            if job:
                jobs.append(job)
        return jobs

    def delete_job(self, job_id: str) -> bool:
        result = self._store.delete(f"{JOB_PREFIX}{job_id}")
        try:
            self._store.redis.zrem(self._list_key, job_id)
        except (CircuitBreakerOpenError, Exception):
            pass
        return result > 0


class VoiceRedisStore(IVoiceStore):
    """Persistence layer for voice profiles using ResilientRedisStore."""

    def __init__(self, redis_store: ResilientRedisStore):
        self._store = redis_store

    def save_profile(self, profile: VoiceProfile) -> None:
        key = f"{VOICE_PREFIX}{profile.id}"
        self._store.set(key, profile.model_dump_json())
        try:
            self._store.redis.sadd(VOICE_INDEX_KEY, profile.id)
        except (CircuitBreakerOpenError, Exception) as e:
            logger.warning(f"Failed to add voice to index: {e}")

    def get_profile(self, voice_id: str) -> Optional[VoiceProfile]:
        data = self._store.get(f"{VOICE_PREFIX}{voice_id}")
        if not data:
            return None
        try:
            return VoiceProfile.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to deserialize voice profile {voice_id}: {e}")
            return None

    def list_profiles(self) -> list[VoiceProfile]:
        try:
            voice_ids = self._store.redis.smembers(VOICE_INDEX_KEY)
        except (CircuitBreakerOpenError, Exception) as e:
            logger.warning(f"Failed to list voices from index: {e}")
            return []
        profiles = []
        for vid in voice_ids:
            profile = self.get_profile(vid)
            if profile:
                profiles.append(profile)
        return profiles

    def delete_profile(self, voice_id: str) -> bool:
        try:
            self._store.redis.srem(VOICE_INDEX_KEY, voice_id)
        except (CircuitBreakerOpenError, Exception):
            pass
        return self._store.delete(f"{VOICE_PREFIX}{voice_id}") > 0

    def profile_exists(self, voice_id: str) -> bool:
        return self._store.exists(f"{VOICE_PREFIX}{voice_id}") > 0
