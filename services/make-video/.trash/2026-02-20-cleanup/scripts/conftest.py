"""
Pytest fixtures globais

Fixtures compartilhadas para todos os testes
"""

import pytest
import tempfile
import os
from unittest.mock import Mock


@pytest.fixture
def temp_dir():
    """Cria diretório temporário para testes"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_redis():
    """FakeRedis client for testing"""
    import fakeredis
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_logger():
    """Mock do logger"""
    mock = Mock()
    return mock


@pytest.fixture
def sample_subtitles():
    """Legendas de exemplo para testes"""
    return [
        {'start': 0.0, 'end': 2.0, 'text': 'Hello world'},
        {'start': 2.5, 'end': 5.0, 'text': 'This is a test'},
        {'start': 6.0, 'end': 8.0, 'text': 'Testing subtitles'},
    ]


@pytest.fixture
def sample_speech_segments():
    """Segmentos de fala de exemplo"""
    return [
        (0.0, 2.5),   # Overlaps with first subtitle
        (6.0, 8.5),   # Overlaps with third subtitle
        # Gap em 2.5-6.0 (sem fala)
    ]


@pytest.fixture
def mock_blacklist_manager():
    """Mock do BlacklistManager"""
    mock = Mock()
    mock.is_blacklisted.return_value = False
    mock.add.return_value = None
    mock.remove.return_value = None
    mock.get_stats.return_value = {'total_blocked': 0, 'by_reason': {}}
    return mock


@pytest.fixture
def mock_video_validator():
    """Mock do VideoValidator"""
    mock = Mock()
    mock.validate_integrity.return_value = True
    mock.has_embedded_subtitles.return_value = (False, 0.0)
    return mock


@pytest.fixture(scope='session')
def test_video_path():
    """Path para vídeo de teste (não cria arquivo real)"""
    return '/tmp/test_video.mp4'


@pytest.fixture(scope='session')
def test_audio_path():
    """Path para áudio de teste (não cria arquivo real)"""
    return '/tmp/test_audio.wav'
