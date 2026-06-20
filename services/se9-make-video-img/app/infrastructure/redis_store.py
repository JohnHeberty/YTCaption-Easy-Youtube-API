"""Redis-based job store using ResilientRedisStore from shared library.

Uses sorted set (ZSET) for job listing instead of KEYS command.
Uses Redis pipelines for atomic multi-key operations.
"""
import json
from common.log_utils import get_logger
import time
from typing import Optional

from app.core.config import get_settings
from app.core.constants import JOB_PREFIX, JOB_TTL

logger = get_logger(__name__)

_redis_store = None
_LIST_KEY = "rbg_jobs:list"


def get_redis():
    """Get ResilientRedisStore instance with lazy initialization."""
    global _redis_store
    if _redis_store is not None:
        return _redis_store

    try:
        from common.redis_utils import ResilientRedisStore
        settings = get_settings()
        _redis_store = ResilientRedisStore(
            redis_url=settings.redis_url,
            max_connections=10,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
            circuit_breaker_enabled=True,
        )
        _redis_store.ping()
        logger.info("Connected to Redis via ResilientRedisStore")
        return _redis_store
    except Exception as e:
        logger.warning("Redis unavailable, using in-memory fallback: %s", e)
        _redis_store = _FakeRedis()
        return _redis_store


class _FakeRedis:
    """In-memory fallback when Redis unavailable."""

    def __init__(self):
        self._store: dict[str, str] = {}
        self._sets: dict[str, dict] = {}

    def setex(self, key: str, time_val: int, value: str) -> None:
        self._store[key] = value

    def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    def zadd(self, name: str, mapping: dict) -> None:
        if name not in self._sets:
            self._sets[name] = {}
        self._sets[name].update(mapping)

    def zrevrange(self, name: str, start: int, end: int) -> list[str]:
        s = self._sets.get(name, {})
        sorted_keys = sorted(s.keys(), key=lambda k: s[k], reverse=True)
        if end == -1:
            return sorted_keys[start:]
        return sorted_keys[start:end + 1]

    def zrem(self, name: str, *values: str) -> int:
        s = self._sets.get(name, {})
        count = 0
        for v in values:
            if v in s:
                del s[v]
                count += 1
        return count

    def mget(self, *keys: str) -> list[Optional[str]]:
        return [self._store.get(k) for k in keys]

    def ping(self) -> bool:
        return True

    def pipeline(self):
        """Return a fake pipeline that batches operations."""
        return _FakePipeline(self)


class _FakePipeline:
    """Fake Redis pipeline that executes operations immediately."""

    def __init__(self, fake_redis: _FakeRedis):
        self._redis = fake_redis

    def setex(self, key: str, time_val: int, value: str) -> "_FakePipeline":
        self._redis.setex(key, time_val, value)
        return self

    def set(self, key: str, value: str) -> "_FakePipeline":
        self._redis._store[key] = value
        return self

    def delete(self, *keys: str) -> "_FakePipeline":
        self._redis.delete(*keys)
        return self

    def zadd(self, name: str, mapping: dict) -> "_FakePipeline":
        self._redis.zadd(name, mapping)
        return self

    def zrem(self, name: str, *values: str) -> "_FakePipeline":
        self._redis.zrem(name, *values)
        return self

    def execute(self) -> list:
        return []


class VideoJobStore:
    """Store for video generation jobs using ResilientRedisStore."""

    def __init__(self):
        self.redis = get_redis()

    def save_job(self, job_id: str, job_data: dict) -> None:
        key = f"{JOB_PREFIX}{job_id}"
        data = json.dumps(job_data, default=str)
        created_at = job_data.get("created_at", time.time())
        if hasattr(created_at, "timestamp"):
            created_at = created_at.timestamp()
        elif isinstance(created_at, str):
            created_at = time.time()

        try:
            pipe = self.redis.redis.pipeline()
            pipe.setex(key, JOB_TTL, data)
            pipe.zadd(_LIST_KEY, {job_id: float(created_at)})
            pipe.execute()
        except AttributeError:
            pipe = self.redis.pipeline()
            pipe.setex(key, JOB_TTL, data)
            pipe.zadd(_LIST_KEY, {job_id: float(created_at)})
            pipe.execute()

    def get_job(self, job_id: str) -> Optional[dict]:
        key = f"{JOB_PREFIX}{job_id}"
        try:
            data = self.redis.redis.get(key)
        except AttributeError:
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
        try:
            pipe = self.redis.redis.pipeline()
            pipe.delete(key)
            pipe.zrem(_LIST_KEY, job_id)
            pipe.execute()
        except AttributeError:
            pipe = self.redis.pipeline()
            pipe.delete(key)
            pipe.zrem(_LIST_KEY, job_id)
            pipe.execute()

    def list_jobs(self) -> list[dict]:
        try:
            job_ids = self.redis.redis.zrevrange(_LIST_KEY, 0, -1)
        except AttributeError:
            job_ids = self.redis.zrevrange(_LIST_KEY, 0, -1)

        if not job_ids:
            return []

        # Batch fetch with MGET instead of N individual GETs
        keys = [f"{JOB_PREFIX}{jid.decode() if isinstance(jid, bytes) else jid}" for jid in job_ids]
        try:
            raw = self.redis.redis.mget(*keys)
        except AttributeError:
            raw = self.redis.mget(*keys)

        jobs = []
        stale_ids = []
        for jid, data in zip(job_ids, raw):
            jid_str = jid.decode() if isinstance(jid, bytes) else jid
            if data:
                jobs.append(json.loads(data))
            else:
                stale_ids.append(jid_str)

        # Clean stale entries from sorted set (best-effort)
        if stale_ids:
            try:
                self.redis.redis.zrem(_LIST_KEY, *stale_ids)
            except Exception:
                try:
                    self.redis.zrem(_LIST_KEY, *stale_ids)
                except Exception:
                    logger.warning("Failed to clean %d stale entries from sorted set", len(stale_ids))

        return jobs

    def get_next_queued_job(self) -> Optional[dict]:
        """Get the first queued job without scanning all jobs.

        Iterates the sorted set lazily — stops at the first QUEUED job found.
        Much more efficient than list_jobs() when there are many completed jobs.
        """
        try:
            job_ids = self.redis.redis.zrevrange(_LIST_KEY, 0, -1)
        except AttributeError:
            job_ids = self.redis.zrevrange(_LIST_KEY, 0, -1)

        for jid in job_ids:
            jid_str = jid.decode() if isinstance(jid, bytes) else jid
            key = f"{JOB_PREFIX}{jid_str}"
            try:
                data = self.redis.redis.get(key)
            except AttributeError:
                data = self.redis.get(key)
            if data:
                job = json.loads(data)
                if job.get("status") == "queued":
                    return job
        return None
