from typing import Optional


class _FakeRedis:
    """In-memory fallback when Redis is unavailable. For dev/testing only."""

    def __init__(self):
        self._data: dict[str, str] = {}
        self._sets: dict[str, set] = {}
        self._sorted_sets: dict[str, dict] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._data[key] = value

    def set(self, key: str, value: str, **kwargs) -> None:
        self._data[key] = value

    def get(self, key: str) -> Optional[str]:
        return self._data.get(key)

    def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                count += 1
        return count

    def exists(self, *keys: str) -> int:
        return sum(1 for k in keys if k in self._data)

    def ping(self) -> bool:
        return True

    def zadd(self, name: str, mapping: dict) -> int:
        if name not in self._sorted_sets:
            self._sorted_sets[name] = {}
        self._sorted_sets[name].update(mapping)
        return len(mapping)

    def zrevrange(self, name: str, start: int, end: int) -> list[str]:
        if name not in self._sorted_sets:
            return []
        items = sorted(
            self._sorted_sets[name].items(), key=lambda x: x[1], reverse=True
        )
        return [item[0] for item in items[start:end + 1]]

    def zrem(self, name: str, *members: str) -> int:
        if name not in self._sorted_sets:
            return 0
        count = 0
        for m in members:
            if m in self._sorted_sets[name]:
                del self._sorted_sets[name][m]
                count += 1
        return count

    def sadd(self, key: str, *values: str) -> int:
        self._sets.setdefault(key, set()).update(values)
        return len(values)

    def smembers(self, key: str) -> set:
        return self._sets.get(key, set())

    def srem(self, key: str, *values: str) -> int:
        if key not in self._sets:
            return 0
        count = 0
        for v in values:
            if v in self._sets[key]:
                self._sets[key].discard(v)
                count += 1
        return count


def create_fake_store():
    """Create a fake ResilientRedisStore wrapping _FakeRedis for testing."""
    from common.redis_utils.resilient_store import ResilientRedisStore

    fake = _FakeRedis()

    class _FakeResilientStore:
        def __init__(self):
            self.redis = fake

        def ping(self) -> bool:
            return True

        def get(self, key: str) -> Optional[str]:
            return fake.get(key)

        def set(self, key: str, value: str, **kwargs) -> bool:
            fake.set(key, value)
            return True

        def setex(self, key: str, time: int, value: str) -> bool:
            fake.setex(key, time, value)
            return True

        def delete(self, *keys: str) -> int:
            return fake.delete(*keys)

        def exists(self, *keys: str) -> int:
            return fake.exists(*keys)

        def close(self):
            pass

    return _FakeResilientStore()
