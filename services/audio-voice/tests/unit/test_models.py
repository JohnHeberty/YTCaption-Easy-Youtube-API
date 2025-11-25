"""
Testes unitários para models.py
"""
import pytest
from datetime import datetime, timedelta
from app.models import Job, VoiceProfile, JobMode, JobStatus


class TestJob:
    """Testes para o modelo Job"""
    
    def test_create_new_dubbing_job(self):
        """Testa criação de job de dublagem"""
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Hello world",
            source_language="en",
            voice_preset="female_generic"
        )
        
        assert job.id is not None
        assert job.mode == JobMode.DUBBING
        assert job.status == JobStatus.QUEUED
        assert job.text == "Hello world"
        assert job.source_language == "en"
        assert job.voice_preset == "female_generic"
        assert job.progress == 0.0
    
    def test_create_new_clone_job(self):
        """Testa criação de job de clonagem"""
        job = Job.create_new(
            mode=JobMode.CLONE_VOICE,
            voice_name="Test Voice",
            source_language="en"
        )
        
        assert job.mode == JobMode.CLONE_VOICE
        assert job.voice_name == "Test Voice"
    
    def test_job_expiration(self):
        """Testa expiração de job"""
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en",
            cache_ttl_hours=0  # Expira imediatamente
        )
        
        # Força expiração
        job.expires_at = datetime.now() - timedelta(hours=1)
        
        assert job.is_expired is True


class TestVoiceProfile:
    """Testes para o modelo VoiceProfile"""
    
    def test_create_new_voice_profile(self):
        """Testa criação de perfil de voz"""
        profile = VoiceProfile.create_new(
            name="Test Voice",
            language="en",
            source_audio_path="/tmp/test.wav",
            profile_path="/tmp/test.pkl",
            duration=10.0,
            sample_rate=24000
        )
        
        assert profile.id is not None
        assert profile.name == "Test Voice"
        assert profile.language == "en"
        assert profile.duration == 10.0
        assert profile.usage_count == 0
    
    def test_increment_usage(self):
        """Testa incremento de uso"""
        profile = VoiceProfile.create_new(
            name="Test Voice",
            language="en",
            source_audio_path="/tmp/test.wav",
            profile_path="/tmp/test.pkl"
        )
        
        assert profile.usage_count == 0
        profile.increment_usage()
        assert profile.usage_count == 1
        assert profile.last_used_at is not None
    
    def test_voice_profile_expiration(self):
        """Testa expiração de perfil"""
        profile = VoiceProfile.create_new(
            name="Test Voice",
            language="en",
            source_audio_path="/tmp/test.wav",
            profile_path="/tmp/test.pkl",
            ttl_days=0
        )
        
        # Força expiração
        profile.expires_at = datetime.now() - timedelta(days=1)
        
        assert profile.is_expired is True
