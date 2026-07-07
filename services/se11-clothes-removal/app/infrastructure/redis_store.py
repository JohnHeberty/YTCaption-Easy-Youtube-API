"""Redis-based job store for SE11 Clothes Removal."""
from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from common.log_utils import get_logger

from app.core.config import get_settings
from app.core.constants import REDIS_KEY_PREFIX, REDIS_LIST_KEY, REDIS_JOB_TTL

if TYPE_CHECKING:
    from common.protocols import JobStoreProtocol

logger = get_logger(__name__)

_redis_store: Any = None


def get_redis() -> Any:
    """Get ResilientRedisStore instance with lazy init, fallback to in-memory."""
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

    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self._sets: dict[str, dict[str, float]] = {}

    def setex(self, key: str, time_val: int, value: str) -> None:
        self._store[key] = value

    def get(self, key: str) -> str | None:
        return self._store.get(key)

    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._store:
                del self._store[key]
                count += 1
        return count

    def zadd(self, name: str, mapping: dict[str, float]) -> None:
        if name not in self._sets:
            self._sets[name] = {}
        self._sets[name].update(mapping)

    def zrevrange(self, name: str, start: int, end: int) -> list[str]:
        s = self._sets.get(name, {})
        sorted_keys = sorted(s.keys(), key=lambda k: s[k], reverse=True)
        if end == -1:
            return sorted_keys[start:]
        return sorted_keys[start : end + 1]

    def zrem(self, name: str, *values: str) -> int:
        s = self._sets.get(name, {})
        count = 0
        for v in values:
            if v in s:
                del s[v]
                count += 1
        return count

    def mget(self, *keys: str) -> list[str | None]:
        return [self._store.get(k) for k in keys]

    def ping(self) -> bool:
        return True

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)


class _FakePipeline:
    """Fake Redis pipeline that executes operations immediately."""

    def __init__(self, fake_redis: _FakeRedis) -> None:
        self._redis = fake_redis

    def setex(self, key: str, time_val: int, value: str) -> _FakePipeline:
        self._redis.setex(key, time_val, value)
        return self

    def set(self, key: str, value: str) -> _FakePipeline:
        self._redis._store[key] = value
        return self

    def delete(self, *keys: str) -> _FakePipeline:
        self._redis.delete(*keys)
        return self

    def zadd(self, name: str, mapping: dict[str, float]) -> _FakePipeline:
        self._redis.zadd(name, mapping)
        return self

    def zrem(self, name: str, *values: str) -> _FakePipeline:
        self._redis.zrem(name, *values)
        return self

    def execute(self) -> list[Any]:
        return []


class ClothesRemovalJobStore:
    """Store for clothes removal jobs.

    Conforms to common.protocols.JobStoreProtocol.
    """

    def __init__(self) -> None:
        self.redis = get_redis()

    @property
    def _use_raw(self) -> bool:
        """True when backed by ResilientRedisStore (has .redis attribute)."""
        return hasattr(self.redis, "redis")

    def _pipe(self) -> Any:
        """Get a pipeline — works for both ResilientRedisStore and _FakeRedis."""
        return self.redis.redis.pipeline() if self._use_raw else self.redis.pipeline()

    def _get(self, key: str) -> str | None:
        """Get a value — works for both backends."""
        return self.redis.redis.get(key) if self._use_raw else self.redis.get(key)

    def _mget(self, *keys: str) -> list[str | None]:
        """Multi-get — works for both backends."""
        return self.redis.redis.mget(*keys) if self._use_raw else self.redis.mget(*keys)

    def _zrevrange(self, name: str, start: int, end: int) -> list[str]:
        """ZRANGEBYSCORE — works for both backends."""
        return self.redis.redis.zrevrange(name, start, end) if self._use_raw else self.redis.zrevrange(name, start, end)

    def _zrem(self, name: str, *values: str) -> int:
        """ZREM — works for both backends."""
        return self.redis.redis.zrem(name, *values) if self._use_raw else self.redis.zrem(name, *values)

    def save_job(self, job_id: str, job_data: dict[str, Any]) -> None:
        key = f"{REDIS_KEY_PREFIX}{job_id}"
        data = json.dumps(job_data, default=str)
        created_at = job_data.get("created_at", time.time())
        if hasattr(created_at, "timestamp"):
            created_at = created_at.timestamp()
        elif isinstance(created_at, str):
            created_at = time.time()

        pipe = self._pipe()
        pipe.setex(key, REDIS_JOB_TTL, data)
        pipe.zadd(REDIS_LIST_KEY, {job_id: float(created_at)})
        pipe.execute()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        key = f"{REDIS_KEY_PREFIX}{job_id}"
        data = self._get(key)
        if data:
            return json.loads(data)
        return None

    def delete_job(self, job_id: str) -> None:
        key = f"{REDIS_KEY_PREFIX}{job_id}"
        pipe = self._pipe()
        pipe.delete(key)
        pipe.zrem(REDIS_LIST_KEY, job_id)
        pipe.execute()

    def list_jobs(self) -> list[dict[str, Any]]:
        job_ids = self._zrevrange(REDIS_LIST_KEY, 0, -1)

        if not job_ids:
            return []

        keys = [f"{REDIS_KEY_PREFIX}{jid.decode() if isinstance(jid, bytes) else jid}" for jid in job_ids]
        raw = self._mget(*keys)

        jobs: list[dict[str, Any]] = []
        stale_ids: list[str] = []
        for jid, data in zip(job_ids, raw):
            jid_str = jid.decode() if isinstance(jid, bytes) else jid
            if data:
                jobs.append(json.loads(data))
            else:
                stale_ids.append(jid_str)

        if stale_ids:
            try:
                self._zrem(REDIS_LIST_KEY, *stale_ids)
            except Exception:
                logger.warning("Failed to clean %d stale entries from sorted set", len(stale_ids))

        return jobs
