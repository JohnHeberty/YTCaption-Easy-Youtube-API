"""
Shared test utilities for YTCaption microservices.

Provides:
- MockRedis: fakeredis-based mock for Redis stores
- MockHTTPClient: respx-based mock for HTTP clients
- MockCelery: Mock for Celery app and tasks
- Common fixtures: client, job_store, settings
"""
from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app, MockCeleryTask

__all__ = [
    "MockRedis",
    "mock_celery_app",
    "MockCeleryTask",
]