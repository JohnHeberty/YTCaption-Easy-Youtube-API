import json
import os
from typing import Optional

import redis

from common.log_utils import get_logger

from app.core.constants import (
    JOB_PREFIX,
    JOB_TTL_SECONDS,
    VOICE_PREFIX,
    VOICE_INDEX_KEY,
)
from app.domain.models import AudioGenerationJob, VoiceProfile
from app.domain.interfaces import IJobStore, IVoiceStore

logger = get_logger(__name__)


class _RedisClientMixin:
    """Shared Redis connection logic for all stores."""

    def __init__(self, redis_url: Optional[str] = None):
        self._redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._redis: Optional[redis.Redis] = None

    def _get_client(self) -> redis.Redis:
        if self._redis is None:
            try:
                self._redis = redis.Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                )
                self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis not available at {self._redis_url}: {e}")
                self._redis = _FakeRedis()
        return self._redis


class JobRedisStore(IJobStore, _RedisClientMixin):
    """Persistence layer for audio generation jobs."""

    def save_job(self, job: AudioGenerationJob) -> None:
        client = self._get_client()
        key = f"{JOB_PREFIX}{job.id}"
        client.setex(key, JOB_TTL_SECONDS, job.model_dump_json())

    def get_job(self, job_id: str) -> Optional[AudioGenerationJob]:
        client = self._get_client()
        data = client.get(f"{JOB_PREFIX}{job_id}")
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
        client = self._get_client()
        try:
            keys = client.keys(f"{JOB_PREFIX}*")
        except Exception:
            return []
        keys = sorted(keys, reverse=True)[:limit]
        jobs = []
        for key in keys:
            data = client.get(key)
            if data:
                try:
                    jobs.append(AudioGenerationJob.model_validate_json(data))
                except Exception:
                    pass
        return jobs

    def delete_job(self, job_id: str) -> bool:
        client = self._get_client()
        return bool(client.delete(f"{JOB_PREFIX}{job_id}"))


class VoiceRedisStore(IVoiceStore, _RedisClientMixin):
    """Persistence layer for voice profiles."""

    def save_profile(self, profile: VoiceProfile) -> None:
        client = self._get_client()
        client.set(f"{VOICE_PREFIX}{profile.id}", profile.model_dump_json())
        client.sadd(VOICE_INDEX_KEY, profile.id)

    def get_profile(self, voice_id: str) -> Optional[VoiceProfile]:
        client = self._get_client()
        data = client.get(f"{VOICE_PREFIX}{voice_id}")
        if not data:
            return None
        try:
            return VoiceProfile.model_validate_json(data)
        except Exception as e:
            logger.error(f"Failed to deserialize voice profile {voice_id}: {e}")
            return None

    def list_profiles(self) -> list[VoiceProfile]:
        client = self._get_client()
        try:
            voice_ids = client.smembers(VOICE_INDEX_KEY)
        except Exception:
            return []
        profiles = []
        for vid in voice_ids:
            profile = self.get_profile(vid)
            if profile:
                profiles.append(profile)
        return profiles

    def delete_profile(self, voice_id: str) -> bool:
        client = self._get_client()
        client.srem(VOICE_INDEX_KEY, voice_id)
        return bool(client.delete(f"{VOICE_PREFIX}{voice_id}"))

    def profile_exists(self, voice_id: str) -> bool:
        client = self._get_client()
        return client.exists(f"{VOICE_PREFIX}{voice_id}") > 0


class _FakeRedis:
    """In-memory fallback when Redis is unavailable. For dev/testing only."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._sets: dict[str, set] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._data[key] = value

    def set(self, key: str, value: str) -> None:
        self._data[key] = value

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def delete(self, key: str) -> bool:
        return self._data.pop(key, None) is not None

    def exists(self, key: str) -> int:
        return 1 if key in self._data else 0

    def keys(self, pattern: str) -> list[str]:
        prefix = pattern.replace("*", "")
        return [k for k in self._data if k.startswith(prefix)]

    def sadd(self, key: str, value: str) -> int:
        self._sets.setdefault(key, set()).add(value)
        return 1

    def smembers(self, key: str) -> set:
        return self._sets.get(key, set())

    def srem(self, key: str, value: str) -> int:
        if key in self._sets:
            self._sets[key].discard(value)
            return 1
        return 0

    def ping(self) -> bool:
        return True
