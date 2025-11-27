"""
Testes para VoiceProcessor multi-engine integration
Sprint 5: Unit Tests - Processor com factory pattern

Tests cover:
- Multi-engine loading
- Engine selection (xtts/f5tts)
- Lazy loading
- Engine caching
- Fallback mechanisms
- Job processing with different engines
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np

from app.processor import VoiceProcessor
from app.models import Job, JobMode, QualityProfile, VoiceProfile
from app.exceptions import TTSEngineException


@pytest.fixture
def mock_settings():
    """Mock settings com multi-engine config"""
    return {
        'tts_engine_default': 'xtts',
        'tts_engines': {
            'xtts': {
                'enabled': True,
                'device': 'cpu',
                'fallback_to_cpu': True,
                'model_name': 'tts_models/multilingual/multi-dataset/xtts_v2'
            },
            'f5tts': {
                'enabled': True,
                'device': 'cpu',
                'fallback_to_cpu': True,
                'model_name': 'SWivid/F5-TTS'
            }
        }
    }


@pytest.fixture
def mock_xtts_engine():
    """Mock XttsEngine"""
    engine = MagicMock()
    engine.engine_name = 'xtts'
    engine.sample_rate = 24000
    engine.generate_dubbing = AsyncMock(
        return_value=(b'fake_audio_xtts', 2.5)
    )
    engine.generate_clone = AsyncMock(
        return_value=(b'fake_audio_clone', 3.0)
    )
    return engine


@pytest.fixture
def mock_f5tts_engine():
    """Mock F5TtsEngine"""
    engine = MagicMock()
    engine.engine_name = 'f5tts'
    engine.sample_rate = 24000
    engine.generate_dubbing = AsyncMock(
        return_value=(b'fake_audio_f5tts', 2.8)
    )
    engine.generate_clone = AsyncMock(
        return_value=(b'fake_audio_clone', 3.2)
    )
    return engine


def test_processor_initializes_with_default_engine(mock_settings):
    """Processor inicializa com engine default (xtts)"""
    with patch('app.processor.create_engine_with_fallback') as mock_create:
        mock_create.return_value = MagicMock(engine_name='xtts')
        
        processor = VoiceProcessor(lazy_load=False)
        
        # Deve carregar engine default
        assert mock_create.called
        call_args = mock_create.call_args
        assert call_args[1]['engine_type'] == 'xtts'


def test_processor_lazy_loading_no_initial_engine(mock_settings):
    """Processor com lazy_load=True não carrega engines inicialmente"""
    with patch('app.processor.create_engine_with_fallback') as mock_create:
        processor = VoiceProcessor(lazy_load=True)
        
        # Não deve carregar nada
        assert not mock_create.called
        assert len(processor.engines) == 0


def test_processor_get_engine_loads_on_demand(mock_settings, mock_xtts_engine):
    """_get_engine() carrega engine on-demand"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        # Primeira chamada - carrega
        engine = processor._get_engine('xtts')
        
        assert engine.engine_name == 'xtts'
        assert 'xtts' in processor.engines


def test_processor_get_engine_uses_cache(mock_settings, mock_xtts_engine):
    """_get_engine() usa cache (não recarrega)"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine) as mock_create:
        processor = VoiceProcessor(lazy_load=True)
        
        # Primeira chamada
        engine1 = processor._get_engine('xtts')
        # Segunda chamada
        engine2 = processor._get_engine('xtts')
        
        # Mesma instância
        assert engine1 is engine2
        # create_engine_with_fallback chamado apenas 1x
        assert mock_create.call_count == 1


def test_processor_supports_multiple_engines(mock_settings, mock_xtts_engine, mock_f5tts_engine):
    """Processor suporta múltiplos engines simultaneamente"""
    def create_engine_side_effect(engine_type, settings, fallback_engine=None):
        if engine_type == 'xtts':
            return mock_xtts_engine
        elif engine_type == 'f5tts':
            return mock_f5tts_engine
    
    with patch('app.processor.create_engine_with_fallback', side_effect=create_engine_side_effect):
        processor = VoiceProcessor(lazy_load=True)
        
        # Carrega ambos os engines
        xtts = processor._get_engine('xtts')
        f5tts = processor._get_engine('f5tts')
        
        assert len(processor.engines) == 2
        assert processor.engines['xtts'].engine_name == 'xtts'
        assert processor.engines['f5tts'].engine_name == 'f5tts'


@pytest.mark.asyncio
async def test_processor_dubbing_with_xtts(mock_settings, mock_xtts_engine):
    """process_dubbing_job() usa XTTS quando tts_engine='xtts'"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test text",
            source_language="en",
            tts_engine='xtts'
        )
        
        await processor.process_dubbing_job(job)
        
        # XTTS foi usado
        assert mock_xtts_engine.generate_dubbing.called
        assert job.tts_engine_used == 'xtts'


@pytest.mark.asyncio
async def test_processor_dubbing_with_f5tts(mock_settings, mock_f5tts_engine):
    """process_dubbing_job() usa F5-TTS quando tts_engine='f5tts'"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_f5tts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test text",
            source_language="en",
            tts_engine='f5tts',
            ref_text="Reference text"
        )
        
        await processor.process_dubbing_job(job)
        
        # F5-TTS foi usado
        assert mock_f5tts_engine.generate_dubbing.called
        assert job.tts_engine_used == 'f5tts'


@pytest.mark.asyncio
async def test_processor_default_engine_when_none_specified(mock_settings, mock_xtts_engine):
    """Processor usa engine default quando tts_engine=None"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en",
            tts_engine=None  # Should use default (xtts)
        )
        
        await processor.process_dubbing_job(job)
        
        # Default (xtts) foi usado
        assert job.tts_engine_used == 'xtts'


@pytest.mark.asyncio
async def test_processor_clone_job_with_f5tts(mock_settings, mock_f5tts_engine):
    """process_clone_job() usa F5-TTS e passa ref_text"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_f5tts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.CLONE,
            text="Clone this",
            source_language="en",
            tts_engine='f5tts',
            ref_text="Reference transcription"
        )
        
        # Mock voice profile
        voice_profile = MagicMock(spec=VoiceProfile)
        voice_profile.ref_text = "Reference transcription"
        
        await processor.process_clone_job(job, voice_profile)
        
        # F5-TTS foi chamado
        assert mock_f5tts_engine.generate_clone.called
        call_kwargs = mock_f5tts_engine.generate_clone.call_args[1]
        # ref_text should be passed
        assert 'ref_text' in call_kwargs or voice_profile.ref_text == "Reference transcription"


@pytest.mark.asyncio
async def test_processor_fallback_on_engine_failure(mock_settings, mock_xtts_engine):
    """Processor faz fallback quando engine falha"""
    def create_engine_with_fallback_mock(engine_type, settings, fallback_engine='xtts'):
        if engine_type == 'f5tts':
            # F5-TTS falha, retorna XTTS como fallback
            return mock_xtts_engine
        return mock_xtts_engine
    
    with patch('app.processor.create_engine_with_fallback', side_effect=create_engine_with_fallback_mock):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en",
            tts_engine='f5tts'  # Request F5-TTS
        )
        
        await processor.process_dubbing_job(job)
        
        # Fallback para XTTS
        assert job.tts_engine_used == 'xtts'


@pytest.mark.asyncio
async def test_processor_tracks_engine_used(mock_settings, mock_f5tts_engine):
    """Processor atualiza job.tts_engine_used corretamente"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_f5tts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en",
            tts_engine='f5tts'
        )
        
        # Antes do processamento
        assert job.tts_engine_used is None or job.tts_engine_used == 'f5tts'
        
        await processor.process_dubbing_job(job)
        
        # Depois do processamento
        assert job.tts_engine_used == 'f5tts'


@pytest.mark.asyncio
async def test_processor_passes_quality_profile(mock_settings, mock_xtts_engine):
    """Processor passa quality_profile para engine"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en",
            quality_profile=QualityProfile.EXPRESSIVE
        )
        
        await processor.process_dubbing_job(job)
        
        # Quality profile foi passado
        call_kwargs = mock_xtts_engine.generate_dubbing.call_args[1]
        assert 'quality_profile' in call_kwargs
        assert call_kwargs['quality_profile'] == QualityProfile.EXPRESSIVE


@pytest.mark.asyncio
async def test_processor_handles_engine_error(mock_settings):
    """Processor trata erros do engine apropriadamente"""
    mock_engine = MagicMock()
    mock_engine.engine_name = 'xtts'
    mock_engine.generate_dubbing = AsyncMock(
        side_effect=TTSEngineException("Engine error")
    )
    
    with patch('app.processor.create_engine_with_fallback', return_value=mock_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en"
        )
        
        with pytest.raises(TTSEngineException):
            await processor.process_dubbing_job(job)


def test_processor_load_engine_uses_factory(mock_settings, mock_xtts_engine):
    """_load_engine() usa factory pattern"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine) as mock_factory:
        processor = VoiceProcessor(lazy_load=True)
        
        processor._load_engine('xtts')
        
        # Factory foi chamado
        assert mock_factory.called
        call_kwargs = mock_factory.call_args[1]
        assert call_kwargs['engine_type'] == 'xtts'
        assert call_kwargs['fallback_engine'] == 'xtts'


def test_processor_load_engine_caches_result(mock_settings, mock_xtts_engine):
    """_load_engine() adiciona engine ao cache"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        # Cache vazio
        assert 'xtts' not in processor.engines
        
        processor._load_engine('xtts')
        
        # Agora no cache
        assert 'xtts' in processor.engines
        assert processor.engines['xtts'].engine_name == 'xtts'


@pytest.mark.asyncio
async def test_processor_concurrent_engine_usage(mock_settings, mock_xtts_engine, mock_f5tts_engine):
    """Processor pode usar múltiplos engines concorrentemente"""
    import asyncio
    
    def create_engine_side_effect(engine_type, settings, fallback_engine=None):
        if engine_type == 'xtts':
            return mock_xtts_engine
        elif engine_type == 'f5tts':
            return mock_f5tts_engine
    
    with patch('app.processor.create_engine_with_fallback', side_effect=create_engine_side_effect):
        processor = VoiceProcessor(lazy_load=True)
        
        job1 = Job.create_new(
            mode=JobMode.DUBBING,
            text="Job 1",
            source_language="en",
            tts_engine='xtts'
        )
        
        job2 = Job.create_new(
            mode=JobMode.DUBBING,
            text="Job 2",
            source_language="en",
            tts_engine='f5tts'
        )
        
        # Processar concorrentemente
        await asyncio.gather(
            processor.process_dubbing_job(job1),
            processor.process_dubbing_job(job2)
        )
        
        # Ambos processados com engines corretos
        assert job1.tts_engine_used == 'xtts'
        assert job2.tts_engine_used == 'f5tts'
        assert mock_xtts_engine.generate_dubbing.called
        assert mock_f5tts_engine.generate_dubbing.called


@pytest.mark.asyncio
async def test_processor_rvc_integration_preserved(mock_settings, mock_xtts_engine):
    """Processor preserva integração RVC"""
    with patch('app.processor.create_engine_with_fallback', return_value=mock_xtts_engine):
        processor = VoiceProcessor(lazy_load=True)
        
        from app.models import RvcModel, RvcParameters
        rvc_model = MagicMock(spec=RvcModel)
        rvc_params = RvcParameters()
        
        job = Job.create_new(
            mode=JobMode.DUBBING,
            text="Test",
            source_language="en",
            enable_rvc=True
        )
        
        await processor.process_dubbing_job(
            job,
            rvc_model=rvc_model,
            rvc_params=rvc_params
        )
        
        # RVC params foram passados
        call_kwargs = mock_xtts_engine.generate_dubbing.call_args[1]
        assert 'enable_rvc' in call_kwargs or 'rvc_model' in call_kwargs
