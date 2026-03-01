"""
Pytest configuration for datetime_utils tests
"""
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo


@pytest.fixture
def brazil_tz():
    """Brazil timezone fixture"""
    return ZoneInfo("America/Sao_Paulo")


@pytest.fixture
def sample_naive_datetime():
    """Sample naive datetime for testing"""
    return datetime(2026, 2, 28, 15, 30, 0)


@pytest.fixture
def sample_aware_datetime(brazil_tz):
    """Sample aware datetime for testing"""
    return datetime(2026, 2, 28, 15, 30, 0, tzinfo=brazil_tz)
