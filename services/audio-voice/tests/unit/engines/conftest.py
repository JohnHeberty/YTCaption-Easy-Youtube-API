"""
Pytest fixtures for engine tests
"""
import pytest
from unittest.mock import MagicMock


@pytest.fixture
def settings():
    """Mock settings for engine tests"""
    return {
        'tts_engine_default': 'xtts',
        'tts_engines': {
            'xtts': {
                'device': 'cpu',
                'fallback_to_cpu': True,
                'model_name': 'tts_models/multilingual/multi-dataset/xtts_v2'
            },
            'f5tts': {
                'device': 'cpu',
                'fallback_to_cpu': True,
                'model_name': 'SWivid/F5-TTS'
            }
        }
    }


@pytest.fixture
def mock_voice_profile():
    """Mock VoiceProfile for testing"""
    from app.models import VoiceProfile
    from datetime import datetime, timedelta
    
    return VoiceProfile(
        id='test-voice-123',
        name='Test Voice',
        language='en',
        source_audio_path='/tmp/reference.wav',
        profile_path='/tmp/reference.wav',
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=24)
    )
