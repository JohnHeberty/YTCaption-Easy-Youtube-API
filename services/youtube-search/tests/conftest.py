"""
Pytest configuration for YouTube Search Service tests
"""
import pytest
import asyncio
from typing import Generator


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_video_id():
    """Sample YouTube video ID for testing"""
    return "dQw4w9WgXcQ"


@pytest.fixture
def sample_channel_id():
    """Sample YouTube channel ID for testing"""
    return "UCuAXFkgsw1L7xaCfnd5JJOw"


@pytest.fixture
def sample_playlist_id():
    """Sample YouTube playlist ID for testing"""
    return "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"
