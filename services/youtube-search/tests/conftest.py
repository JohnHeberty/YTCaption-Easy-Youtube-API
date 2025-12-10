"""
Test configuration
"""
import pytest
import sys
from pathlib import Path

# Add app directory to Python path
app_dir = Path(__file__).parent.parent
sys.path.insert(0, str(app_dir))


@pytest.fixture(scope="session")
def test_video_id():
    """Sample YouTube video ID for testing"""
    return "dQw4w9WgXcQ"


@pytest.fixture(scope="session")
def test_channel_id():
    """Sample YouTube channel ID for testing"""
    return "UCuAXFkgsw1L7xaCfnd5JJOw"


@pytest.fixture(scope="session")
def test_playlist_id():
    """Sample YouTube playlist ID for testing"""
    return "PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf"


@pytest.fixture(scope="session")
def test_query():
    """Sample search query for testing"""
    return "python tutorial"
