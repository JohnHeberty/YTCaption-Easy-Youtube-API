"""
Mock Redis using fakeredis for testing.

Usage in conftest.py:
    from common.test_utils.mock_redis import MockRedis

    @pytest.fixture
    def job_store():
        return MockRedis.create_job_store()
"""
try:
    import fakeredis

    class MockRedis:
        """Wrapper around fakeredis for testing."""

        @staticmethod
        def create_fake_redis():
            """Create a fake Redis instance."""
            return fakeredis.FakeRedis(decode_responses=True)

        @staticmethod
        def create_job_store(store_class, redis_url="redis://localhost:6379/0", **kwargs):
            """Create a job store backed by fakeredis.

            Args:
                store_class: The job store class (e.g., VideoDownloadJobStore)
                redis_url: Ignored for fake redis, kept for API compat
                **kwargs: Additional kwargs for the store class

            Returns:
                Store instance with fake Redis backend
            """
            fake_redis = fakeredis.FakeRedis(decode_responses=True)
            store = store_class(redis_url=redis_url, **kwargs)
            if hasattr(store, 'redis'):
                store.redis = fake_redis
            return store

except ImportError:
    class MockRedis:
        """Fallback when fakeredis is not installed."""

        @staticmethod
        def create_fake_redis():
            from unittest.mock import MagicMock
            mock = MagicMock()
            mock.ping.return_value = True
            mock.get.return_value = None
            mock.set.return_value = True
            mock.delete.return_value = 1
            mock.keys.return_value = []
            mock.hgetall.return_value = {}
            mock.hset.return_value = True
            mock.hdel.return_value = 1
            mock.exists.return_value = 0
            mock.expire.return_value = True
            mock.ttl.return_value = -1
            mock.incr.return_value = 1
            mock.decr.return_value = 1
            mock.lpush.return_value = 1
            mock.rpush.return_value = 1
            mock.lrange.return_value = []
            mock.llen.return_value = 0
            mock.sadd.return_value = 1
            mock.srem.return_value = 1
            mock.smembers.return_value = set()
            mock.zadd.return_value = 1
            mock.zrange.return_value = []
            mock.zrem.return_value = 1
            mock.flushdb.return_value = True
            mock.info.return_value = {}
            return mock

        @staticmethod
        def create_job_store(store_class, **kwargs):
            from unittest.mock import MagicMock
            store = MagicMock(spec=store_class)
            store.redis = MockRedis.create_fake_redis()
            store.ping.return_value = True
            return store