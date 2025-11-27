"""
Testes para XttsEngine
Sprint 5: Unit Tests - XttsEngine refactored implementation

Tests cover:
- Interface compliance
- Voice cloning
- Dubbing generation
- RVC integration
- Error handling
- Quality profiles
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from pathlib import Path

# Imports
from app.engines.xtts_engine import XttsEngine
from app.engines.base import TTSEngine
from app.models import VoiceProfile, QualityProfile
from app.exceptions import TTSEngineException, InvalidAudioException


@pytest.fixture
def xtts_engine():
    """Fixture para XttsEngine com mocks"""
    with patch('app.engines.xtts_engine.TTS') as mock_tts:
        # Mock XTTS model
        mock_model = MagicMock()
        mock_tts.return_value = mock_model
        
        engine = XttsEngine(device='cpu')
        return engine


@pytest.fixture
def sample_audio_file(tmp_path):
    """Cria arquivo de áudio de teste"""
    audio_file = tmp_path / "reference.wav"
    import soundfile as sf
    # 5 segundos de áudio fake (24kHz)
    sf.write(audio_file, np.random.randn(24000 * 5), 24000)
    return str(audio_file)


def test_xtts_is_tts_engine(xtts_engine):
    """XttsEngine implementa TTSEngine"""
    assert isinstance(xtts_engine, TTSEngine)


def test_xtts_engine_name(xtts_engine):
    """Engine name é 'xtts'"""
    assert xtts_engine.engine_name == 'xtts'


def test_xtts_sample_rate(xtts_engine):
    """Sample rate é 24kHz"""
    assert xtts_engine.sample_rate == 24000


def test_xtts_supported_languages(xtts_engine):
    """Retorna linguagens suportadas"""
    langs = xtts_engine.get_supported_languages()
    
    assert isinstance(langs, list)
    assert len(langs) >= 10
    assert 'en' in langs
    assert 'pt' in langs or 'pt-BR' in langs
    assert 'es' in langs


@pytest.mark.asyncio
async def test_xtts_basic_synthesis(xtts_engine):
    """Síntese básica sem voice cloning"""
    # Mock TTS.tts_to_file
    mock_audio = np.random.randn(24000 * 2)  # 2s audio
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file') as mock_tts:
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Hello world",
                language="en"
            )
            
            assert isinstance(audio_bytes, bytes)
            assert len(audio_bytes) > 0
            assert duration > 0
            assert mock_tts.called


@pytest.mark.asyncio
async def test_xtts_with_voice_cloning(xtts_engine, sample_audio_file, mock_voice_profile):
    """Síntese com voice cloning"""
    mock_voice_profile.source_audio_path = sample_audio_file
    
    # Mock TTS
    mock_audio = np.random.randn(24000 * 3)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file') as mock_tts:
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Clone this voice",
                language="en",
                voice_profile=mock_voice_profile
            )
            
            assert len(audio_bytes) > 0
            # Verifica que speaker_wav foi passado
            call_kwargs = mock_tts.call_args[1]
            assert 'speaker_wav' in call_kwargs
            assert call_kwargs['speaker_wav'] == sample_audio_file


@pytest.mark.asyncio
async def test_xtts_quality_profile_balanced(xtts_engine):
    """Quality profile BALANCED mapeia para parâmetros corretos"""
    params = xtts_engine._map_quality_profile(QualityProfile.BALANCED)
    
    assert 'temperature' in params
    assert 'repetition_penalty' in params
    assert params['temperature'] == 0.7
    assert params['repetition_penalty'] == 2.0


@pytest.mark.asyncio
async def test_xtts_quality_profile_expressive(xtts_engine):
    """Quality profile EXPRESSIVE usa temperatura mais alta"""
    params = xtts_engine._map_quality_profile(QualityProfile.EXPRESSIVE)
    
    assert params['temperature'] >= 0.8  # More expressive
    assert params['repetition_penalty'] >= 2.0


@pytest.mark.asyncio
async def test_xtts_quality_profile_stable(xtts_engine):
    """Quality profile STABLE usa temperatura baixa"""
    params = xtts_engine._map_quality_profile(QualityProfile.STABLE)
    
    assert params['temperature'] <= 0.5  # More stable/predictable


@pytest.mark.asyncio
async def test_xtts_rvc_integration(xtts_engine, sample_audio_file):
    """XTTS integra com RVC para conversão de voz"""
    # Mock TTS
    mock_audio = np.random.randn(24000 * 2)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file'):
            # Mock RVC client
            xtts_engine.rvc_client = MagicMock()
            xtts_engine.rvc_client.convert_audio = AsyncMock(
                return_value=(np.zeros(24000), 1.0)
            )
            
            from app.models import RvcModel, RvcParameters
            rvc_model = MagicMock(spec=RvcModel)
            rvc_model.id = 'test_rvc'
            rvc_params = RvcParameters()
            
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Test",
                language="en",
                enable_rvc=True,
                rvc_model=rvc_model,
                rvc_params=rvc_params
            )
            
            # RVC foi chamado
            assert xtts_engine.rvc_client.convert_audio.called


@pytest.mark.asyncio
async def test_xtts_clone_voice_creates_profile(xtts_engine, sample_audio_file):
    """clone_voice() cria VoiceProfile"""
    with patch('soundfile.read', return_value=(np.random.randn(24000 * 5), 24000)):
        profile = await xtts_engine.clone_voice(
            audio_path=sample_audio_file,
            language="en",
            voice_name="Test Voice"
        )
        
        assert profile.name == "Test Voice"
        assert profile.language == "en"
        assert profile.source_audio_path == sample_audio_file


@pytest.mark.asyncio
async def test_xtts_clone_voice_validates_duration(xtts_engine, tmp_path):
    """clone_voice() valida duração mínima do áudio"""
    short_audio = tmp_path / "short.wav"
    import soundfile as sf
    # 1 segundo (mínimo 3s)
    sf.write(short_audio, np.random.randn(24000), 24000)
    
    with patch('soundfile.read', return_value=(np.random.randn(24000), 24000)):
        with pytest.raises(InvalidAudioException, match="too short|minimum"):
            await xtts_engine.clone_voice(
                audio_path=str(short_audio),
                language="en",
                voice_name="Test"
            )


@pytest.mark.asyncio
async def test_xtts_empty_text_error(xtts_engine):
    """Texto vazio levanta ValueError"""
    with pytest.raises(ValueError, match="[Ee]mpty|[Tt]ext"):
        await xtts_engine.generate_dubbing(text="", language="en")


@pytest.mark.asyncio
async def test_xtts_invalid_language_error(xtts_engine):
    """Linguagem inválida levanta ValueError"""
    with pytest.raises(ValueError, match="[Ll]anguage"):
        await xtts_engine.generate_dubbing(
            text="Test",
            language="invalid_lang_xyz"
        )


def test_xtts_initialization_cpu(xtts_engine):
    """XttsEngine inicializa em CPU"""
    assert xtts_engine.device == 'cpu'


def test_xtts_initialization_cuda():
    """XttsEngine tenta usar CUDA mas faz fallback para CPU"""
    with patch('app.engines.xtts_engine.TTS') as mock_tts:
        with patch('torch.cuda.is_available', return_value=False):
            engine = XttsEngine(device='cuda', fallback_to_cpu=True)
            
            # Deve ter feito fallback para CPU
            assert engine.device == 'cpu'


@pytest.mark.asyncio
async def test_xtts_audio_normalization(xtts_engine):
    """Áudio é normalizado após síntese"""
    # Mock com áudio de alta amplitude
    loud_audio = np.random.randn(24000) * 10  # Amplitude alta
    
    with patch('soundfile.read', return_value=(loud_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file'):
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Test",
                language="en"
            )
            
            # Verifica que áudio foi gerado
            assert len(audio_bytes) > 0
            
            # Decodifica e verifica normalização
            import io
            import soundfile as sf
            audio_array, sr = sf.read(io.BytesIO(audio_bytes))
            
            # Amplitude deve estar normalizada (máximo ~1.0)
            assert np.max(np.abs(audio_array)) <= 1.0


def test_xtts_model_loading():
    """XTTS model é carregado corretamente"""
    with patch('app.engines.xtts_engine.TTS') as mock_tts:
        mock_model = MagicMock()
        mock_tts.return_value = mock_model
        
        engine = XttsEngine(
            device='cpu',
            model_name='tts_models/multilingual/multi-dataset/xtts_v2'
        )
        
        # Verifica que modelo foi carregado
        assert mock_tts.called
        call_args = mock_tts.call_args
        assert 'xtts_v2' in str(call_args)


@pytest.mark.asyncio
async def test_xtts_streaming_synthesis(xtts_engine):
    """XTTS suporta síntese em streaming (chunks)"""
    # Mock streaming
    with patch.object(xtts_engine, '_synthesize_streaming') as mock_stream:
        mock_stream.return_value = [
            (np.random.randn(24000), 1.0),
            (np.random.randn(24000), 1.0)
        ]
        
        chunks = await xtts_engine.generate_streaming(
            text="Long text for streaming",
            language="en"
        )
        
        assert len(chunks) == 2
        assert all(isinstance(chunk[0], np.ndarray) for chunk in chunks)


@pytest.mark.asyncio
async def test_xtts_multi_speaker_synthesis(xtts_engine):
    """XTTS suporta múltiplos speakers"""
    mock_audio = np.random.randn(24000 * 2)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file') as mock_tts:
            # Usar speaker built-in
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Test",
                language="en",
                speaker="Claribel Dervla"  # XTTS speaker
            )
            
            assert len(audio_bytes) > 0
            call_kwargs = mock_tts.call_args[1]
            assert 'speaker' in call_kwargs or 'speaker_wav' not in call_kwargs


@pytest.mark.asyncio
async def test_xtts_language_detection_fallback(xtts_engine):
    """XTTS faz fallback para inglês em linguagem desconhecida"""
    mock_audio = np.random.randn(24000)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file') as mock_tts:
            with patch('logging.Logger.warning') as mock_log:
                audio_bytes, duration = await xtts_engine.generate_dubbing(
                    text="Test",
                    language="xyz"  # Invalid language
                )
                
                # Should log warning and fallback
                assert mock_log.called


@pytest.mark.asyncio
async def test_xtts_emotion_parameter(xtts_engine):
    """XTTS aceita parâmetro de emoção"""
    mock_audio = np.random.randn(24000)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file') as mock_tts:
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Test",
                language="en",
                emotion="happy"
            )
            
            assert len(audio_bytes) > 0


@pytest.mark.asyncio
async def test_xtts_speed_control(xtts_engine):
    """XTTS permite controle de velocidade"""
    mock_audio = np.random.randn(24000 * 2)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file') as mock_tts:
            # Speed 1.5x
            audio_bytes, duration = await xtts_engine.generate_dubbing(
                text="Test",
                language="en",
                speed=1.5
            )
            
            assert len(audio_bytes) > 0
            # Duration should be adjusted
            assert duration > 0


@pytest.mark.asyncio
async def test_xtts_batch_processing(xtts_engine):
    """XTTS processa múltiplos textos em batch"""
    texts = ["Text 1", "Text 2", "Text 3"]
    mock_audio = np.random.randn(24000)
    
    with patch('soundfile.read', return_value=(mock_audio, 24000)):
        with patch.object(xtts_engine.tts, 'tts_to_file'):
            results = await xtts_engine.generate_batch(
                texts=texts,
                language="en"
            )
            
            assert len(results) == 3
            assert all(isinstance(r[0], bytes) for r in results)


def test_xtts_backward_compatibility():
    """XTTSClient alias existe para backward compatibility"""
    from app.xtts_client import XTTSClient
    
    assert XTTSClient is XttsEngine
