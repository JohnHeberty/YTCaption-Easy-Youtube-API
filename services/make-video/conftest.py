"""
Test configuration and fixtures
"""

import pytest
import os
import tempfile
from pathlib import Path

# Test environment
os.environ.update({
    'REDIS_URL': 'redis://localhost:6379/15',  # Test DB
    'YOUTUBE_SEARCH_URL': 'http://localhost:8003',
    'VIDEO_DOWNLOADER_URL': 'http://localhost:8002',
    'AUDIO_TRANSCRIBER_URL': 'http://localhost:8005',
})


@pytest.fixture
def temp_storage_dirs():
    """Create temporary storage directories for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        dirs = {
            'audio': tmpdir / 'audio',
            'shorts': tmpdir / 'shorts',
            'temp': tmpdir / 'temp',
            'output': tmpdir / 'output',
        }
        
        for dir_path in dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        
        yield dirs


@pytest.fixture
def sample_audio_file(temp_storage_dirs):
    """Create a sample audio file for testing"""
    audio_path = temp_storage_dirs['audio'] / 'test_audio.mp3'
    
    # Create a small valid MP3 file (silence)
    # For real tests, you'd use pydub or similar
    audio_path.write_bytes(b'\x00' * 1024)  # Placeholder
    
    return audio_path


@pytest.fixture
def redis_store():
    """Create Redis store for testing"""
    from app.redis_store import RedisJobStore
    
    store = RedisJobStore(redis_url=os.getenv('REDIS_URL'))
    
    yield store
    
    # Cleanup: flush test database
    # asyncio.run(store.redis.flushdb())
