"""
Common pytest fixtures for all services.

Import this in conftest.py:
    pytest_plugins = ["common.test_utils.fixtures"]
"""
import pytest
from unittest.mock import MagicMock

from common.test_utils.mock_redis import MockRedis
from common.test_utils.mock_celery import mock_celery_app


@pytest.fixture
def fake_redis():
    """Provide a fake Redis instance."""
    return MockRedis.create_fake_redis()


@pytest.fixture
def celery_app():
    """Provide a mock Celery app."""
    return mock_celery_app()