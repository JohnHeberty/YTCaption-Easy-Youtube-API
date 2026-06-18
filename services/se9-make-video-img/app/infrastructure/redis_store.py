"""Redis-based job store with in-memory fallback."""
import json
import logging
from typing import Optional

from app.core.constants import JOB_PREFIX, JOB_TTL

logger = logging.getLogger(__name__)

_redis_client = None


def get_redis():
    """Get Redis client with lazy initialization."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        from app.core.config import settings
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        _redis_client.ping()
        logger.info("Connected to Redis")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis unavailable, using in-memory fallback: {e}")
        _redis_client = _FakeRedis()
        return _redis_client


class _FakeRedis:
    """In-memory fallback when Redis is unavailable."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._ttls: dict[str, float] = {}

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self._store[key] = value
        if ex:
            import time
            self._ttls[key] = time.time() + ex

    def get(self, key: str) -> Optional[str]:
        if key in self._ttls:
            import time
            if time.time() > self._ttls[key]:
                del self._store[key]
                del self._ttls[key]
                return None
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._ttls.pop(key, None)

    def keys(self, pattern: str = "*") -> list[str]:
        prefix = pattern.replace("*", "")
        return [k for k in self._store.keys() if k.startswith(prefix)]

    def ping(self) -> bool:
        return True


class VideoJobStore:
    """Store for video generation jobs."""

    def __init__(self):
        self.redis = get_redis()

    def save_job(self, job_id: str, job_data: dict) -> None:
        key = f"{JOB_PREFIX}{job_id}"
        self.redis.set(key, json.dumps(job_data, default=str), ex=JOB_TTL)

    def get_job(self, job_id: str) -> Optional[dict]:
        key = f"{JOB_PREFIX}{job_id}"
        data = self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    def update_job(self, job_id: str, updates: dict) -> None:
        job = self.get_job(job_id)
        if job:
            job.update(updates)
            self.save_job(job_id, job)

    def delete_job(self, job_id: str) -> None:
        key = f"{JOB_PREFIX}{job_id}"
        self.redis.delete(key)

    def list_jobs(self) -> list[dict]:
        keys = self.redis.keys(f"{JOB_PREFIX}*")
        jobs = []
        for key in keys:
            data = self.redis.get(key)
            if data:
                jobs.append(json.loads(data))
        return jobs
