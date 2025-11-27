"""
Testes para interface TTSEngine
Red phase: Todos devem FALHAR (interface não existe)
"""
import pytest
from app.engines.base import TTSEngine
from app.models import VoiceProfile, QualityProfile


def test_tts_engine_is_abstract():
    """TTSEngine não pode ser instanciada diretamente"""
    with pytest.raises(TypeError):
        engine = TTSEngine()


def test_tts_engine_requires_generate_dubbing():
    """Subclasse deve implementar generate_dubbing()"""
    
    class IncompleteEngine(TTSEngine):
        pass
    
    with pytest.raises(TypeError):
        engine = IncompleteEngine()


def test_tts_engine_requires_clone_voice():
    """Subclasse deve implementar clone_voice()"""
    
    class IncompleteEngine(TTSEngine):
        async def generate_dubbing(self, *args, **kwargs):
            pass
    
    with pytest.raises(TypeError):
        engine = IncompleteEngine()


def test_tts_engine_requires_get_supported_languages():
    """Subclasse deve implementar get_supported_languages()"""
    
    class IncompleteEngine(TTSEngine):
        async def generate_dubbing(self, *args, **kwargs):
            pass
        
        async def clone_voice(self, *args, **kwargs):
            pass
    
    with pytest.raises(TypeError):
        engine = IncompleteEngine()


def test_tts_engine_complete_implementation():
    """Implementação completa deve funcionar"""
    
    class CompleteEngine(TTSEngine):
        @property
        def engine_name(self):
            return 'test'
        
        @property
        def sample_rate(self):
            return 24000
        
        async def generate_dubbing(self, *args, **kwargs):
            return b'audio', 1.0
        
        async def clone_voice(self, *args, **kwargs):
            from datetime import datetime, timedelta
            return VoiceProfile(
                id='test',
                name='Test',
                language='en',
                source_audio_path='/tmp/test.wav',
                profile_path='/tmp/test.wav',
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
        
        def get_supported_languages(self):
            return ['en', 'pt']
    
    engine = CompleteEngine()
    assert engine.engine_name == 'test'
    assert engine.sample_rate == 24000


@pytest.mark.asyncio
async def test_tts_engine_generate_dubbing_signature():
    """generate_dubbing() tem assinatura correta"""
    
    class TestEngine(TTSEngine):
        @property
        def engine_name(self):
            return 'test'
        
        @property
        def sample_rate(self):
            return 24000
        
        async def generate_dubbing(
            self,
            text: str,
            language: str,
            voice_profile = None,
            quality_profile = QualityProfile.BALANCED,
            speed: float = 1.0,
            **kwargs
        ):
            return b'', 0.0
        
        async def clone_voice(self, *args, **kwargs):
            from datetime import datetime, timedelta
            return VoiceProfile(
                id='test',
                name='Test',
                language='en',
                source_audio_path='/tmp/test.wav',
                profile_path='/tmp/test.wav',
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
        
        def get_supported_languages(self):
            return ['en']
    
    engine = TestEngine()
    audio, duration = await engine.generate_dubbing(
        text="Test",
        language="en"
    )
    assert isinstance(audio, bytes)
    assert isinstance(duration, float)


def test_tts_engine_has_engine_name_property():
    """TTSEngine deve ter propriedade engine_name"""
    
    class TestEngine(TTSEngine):
        @property
        def sample_rate(self):
            return 24000
        
        async def generate_dubbing(self, *args, **kwargs):
            return b'', 0.0
        
        async def clone_voice(self, *args, **kwargs):
            from datetime import datetime, timedelta
            return VoiceProfile(
                id='test',
                name='Test',
                language='en',
                source_audio_path='/tmp/test.wav',
                profile_path='/tmp/test.wav',
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
        
        def get_supported_languages(self):
            return ['en']
    
    # Missing engine_name property
    with pytest.raises(TypeError):
        engine = TestEngine()


def test_tts_engine_has_sample_rate_property():
    """TTSEngine deve ter propriedade sample_rate"""
    
    class TestEngine(TTSEngine):
        @property
        def engine_name(self):
            return 'test'
        
        async def generate_dubbing(self, *args, **kwargs):
            return b'', 0.0
        
        async def clone_voice(self, *args, **kwargs):
            from datetime import datetime, timedelta
            return VoiceProfile(
                id='test',
                name='Test',
                language='en',
                source_audio_path='/tmp/test.wav',
                profile_path='/tmp/test.wav',
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24)
            )
        
        def get_supported_languages(self):
            return ['en']
    
    # Missing sample_rate property
    with pytest.raises(TypeError):
        engine = TestEngine()
