"""
Testes para F5TtsEngine
Red phase: Testes devem FALHAR (engine não existe)

Sprint 2: Implementação F5-TTS Multi-Engine
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from pathlib import Path

# Imports que serão testados (vão falhar inicialmente - RED phase)
from app.engines.f5tts_engine import F5TtsEngine
from app.engines.base import TTSEngine
from app.models import VoiceProfile, QualityProfile
from app.exceptions import TTSEngineException, InvalidAudioException


@pytest.fixture
def f5tts_engine():
    """Fixture para F5TtsEngine com mocks"""
    with patch('app.engines.f5tts_engine.F5TTS') as mock_f5tts:
        # Mock F5-TTS model
        mock_model = MagicMock()
        mock_f5tts.return_value = mock_model
        
        engine = F5TtsEngine(device='cpu')
        return engine


@pytest.fixture
def sample_audio_file(tmp_path):
    """Cria arquivo de áudio de teste"""
    audio_file = tmp_path / "reference.wav"
    import soundfile as sf
    # 5 segundos de áudio fake (24kHz)
    sf.write(audio_file, np.random.randn(24000 * 5), 24000)
    return str(audio_file)


def test_f5tts_is_tts_engine(f5tts_engine):
    """F5TtsEngine implementa TTSEngine"""
    assert isinstance(f5tts_engine, TTSEngine)


def test_f5tts_engine_name(f5tts_engine):
    """Engine name é 'f5tts'"""
    assert f5tts_engine.engine_name == 'f5tts'


def test_f5tts_sample_rate(f5tts_engine):
    """Sample rate é 24kHz"""
    assert f5tts_engine.sample_rate == 24000


def test_f5tts_supported_languages(f5tts_engine):
    """Retorna linguagens suportadas"""
    langs = f5tts_engine.get_supported_languages()
    
    # F5-TTS é multilíngue (100+ idiomas)
    assert isinstance(langs, list)
    assert len(langs) >= 10
    assert 'en' in langs
    assert 'pt' in langs or 'pt-BR' in langs
    assert 'zh' in langs  # Treinado em chinês


@pytest.mark.asyncio
async def test_f5tts_basic_synthesis(f5tts_engine):
    """Síntese básica sem voice cloning"""
    # Mock TTS.infer
    mock_audio = np.random.randn(24000 * 2)  # 2s audio
    f5tts_engine.tts.infer = MagicMock(return_value=mock_audio)
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
        text="Hello world",
        language="en"
    )
    
    assert isinstance(audio_bytes, bytes)
    assert len(audio_bytes) > 0
    assert duration > 0
    assert f5tts_engine.tts.infer.called


@pytest.mark.asyncio
async def test_f5tts_with_voice_cloning(f5tts_engine, sample_audio_file, mock_voice_profile):
    """Síntese com voice cloning usando ref_text"""
    # Adiciona ref_text ao profile
    mock_voice_profile.ref_text = "This is reference text"
    mock_voice_profile.source_audio_path = sample_audio_file
    
    # Mock TTS.infer
    mock_audio = np.random.randn(24000 * 3)
    f5tts_engine.tts.infer = MagicMock(return_value=mock_audio)
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
        text="Clone this voice",
        language="en",
        voice_profile=mock_voice_profile
    )
    
    assert len(audio_bytes) > 0
    # Verifica que ref_text foi passado para F5-TTS
    call_kwargs = f5tts_engine.tts.infer.call_args[1]
    assert 'ref_text' in call_kwargs
    assert call_kwargs['ref_text'] == "This is reference text"


@pytest.mark.asyncio
async def test_f5tts_auto_transcribe_when_no_ref_text(f5tts_engine, sample_audio_file, mock_voice_profile):
    """Auto-transcreve quando VoiceProfile.ref_text=None"""
    mock_voice_profile.ref_text = None
    mock_voice_profile.source_audio_path = sample_audio_file
    
    # Mock auto-transcription
    with patch.object(f5tts_engine, '_auto_transcribe', new_callable=AsyncMock) as mock_transcribe:
        mock_transcribe.return_value = "Auto transcribed text"
        
        # Mock TTS
        f5tts_engine.tts.infer = MagicMock(return_value=np.zeros(24000))
        
        await f5tts_engine.generate_dubbing(
            text="Test",
            language="en",
            voice_profile=mock_voice_profile
        )
        
        # Verifica que auto-transcrição foi chamada
        assert mock_transcribe.called
        assert mock_transcribe.call_args[0][0] == sample_audio_file


@pytest.mark.asyncio
async def test_f5tts_quality_profile_balanced(f5tts_engine):
    """Quality profile BALANCED mapeia para parâmetros corretos"""
    params = f5tts_engine._map_quality_profile(QualityProfile.BALANCED)
    
    assert 'nfe_step' in params
    assert 'cfg_strength' in params
    assert params['nfe_step'] == 32
    assert params['cfg_strength'] == 2.0


@pytest.mark.asyncio
async def test_f5tts_quality_profile_expressive(f5tts_engine):
    """Quality profile EXPRESSIVE usa mais steps"""
    params = f5tts_engine._map_quality_profile(QualityProfile.EXPRESSIVE)
    
    assert params['nfe_step'] >= 50  # Higher quality
    assert params['cfg_strength'] >= 2.0


@pytest.mark.asyncio
async def test_f5tts_quality_profile_stable(f5tts_engine):
    """Quality profile STABLE usa menos steps (mais rápido)"""
    params = f5tts_engine._map_quality_profile(QualityProfile.STABLE)
    
    assert params['nfe_step'] <= 20  # Faster


@pytest.mark.asyncio
async def test_f5tts_rvc_integration(f5tts_engine):
    """F5-TTS integra com RVC para conversão de voz"""
    # Mock TTS
    f5tts_engine.tts.infer = MagicMock(return_value=np.zeros(24000))
    
    # Mock RVC client
    f5tts_engine.rvc_client = MagicMock()
    f5tts_engine.rvc_client.convert_audio = AsyncMock(
        return_value=(np.zeros(24000), 1.0)
    )
    
    from app.models import RvcModel, RvcParameters
    rvc_model = MagicMock(spec=RvcModel)
    rvc_model.id = 'test_rvc'
    rvc_params = RvcParameters()
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
        text="Test",
        language="en",
        enable_rvc=True,
        rvc_model=rvc_model,
        rvc_params=rvc_params
    )
    
    # RVC foi chamado
    assert f5tts_engine.rvc_client.convert_audio.called


@pytest.mark.asyncio
async def test_f5tts_clone_voice_with_ref_text(f5tts_engine, sample_audio_file):
    """clone_voice() cria VoiceProfile com ref_text"""
    profile = await f5tts_engine.clone_voice(
        audio_path=sample_audio_file,
        language="en",
        voice_name="Test Voice",
        ref_text="This is the reference text"
    )
    
    assert profile.ref_text == "This is the reference text"
    assert profile.name == "Test Voice"
    assert profile.language == "en"
    assert profile.source_audio_path == sample_audio_file


@pytest.mark.asyncio
async def test_f5tts_clone_voice_auto_transcribe(f5tts_engine, sample_audio_file):
    """clone_voice() auto-transcreve quando ref_text=None"""
    with patch.object(f5tts_engine, '_auto_transcribe', new_callable=AsyncMock) as mock:
        mock.return_value = "Auto transcribed"
        
        profile = await f5tts_engine.clone_voice(
            audio_path=sample_audio_file,
            language="en",
            voice_name="Test",
            ref_text=None
        )
        
        assert mock.called
        assert profile.ref_text == "Auto transcribed"


@pytest.mark.asyncio
async def test_f5tts_invalid_audio_too_short(f5tts_engine, tmp_path):
    """Áudio muito curto levanta InvalidAudioException"""
    short_audio = tmp_path / "short.wav"
    import soundfile as sf
    sf.write(short_audio, np.random.randn(24000), 24000)  # 1s (mínimo 3s)
    
    with pytest.raises(InvalidAudioException, match="too short|minimum"):
        await f5tts_engine.clone_voice(
            audio_path=str(short_audio),
            language="en",
            voice_name="Test"
        )


@pytest.mark.asyncio
async def test_f5tts_empty_text_error(f5tts_engine):
    """Texto vazio levanta ValueError"""
    with pytest.raises(ValueError, match="[Ee]mpty|[Tt]ext"):
        await f5tts_engine.generate_dubbing(text="", language="en")


@pytest.mark.asyncio
async def test_f5tts_invalid_language_error(f5tts_engine):
    """Linguagem inválida levanta ValueError"""
    with pytest.raises(ValueError, match="[Ll]anguage"):
        await f5tts_engine.generate_dubbing(
            text="Test",
            language="invalid_lang_xyz"
        )


def test_f5tts_initialization_cpu(f5tts_engine):
    """F5TtsEngine inicializa em CPU"""
    assert f5tts_engine.device == 'cpu'


def test_f5tts_initialization_cuda():
    """F5TtsEngine tenta usar CUDA mas faz fallback para CPU"""
    with patch('app.engines.f5tts_engine.F5TTS') as mock_f5tts:
        with patch('torch.cuda.is_available', return_value=False):
            engine = F5TtsEngine(device='cuda', fallback_to_cpu=True)
            
            # Deve ter feito fallback para CPU
            assert engine.device == 'cpu'


@pytest.mark.asyncio
async def test_f5tts_whisper_auto_transcription(f5tts_engine, sample_audio_file):
    """Whisper auto-transcription funciona"""
    with patch('app.engines.f5tts_engine.WhisperModel') as mock_whisper:
        mock_model = MagicMock()
        mock_whisper.return_value = mock_model
        
        # Mock transcription result
        mock_segment = MagicMock()
        mock_segment.text = "Transcribed text"
        mock_model.transcribe.return_value = ([mock_segment], None)
        
        result = await f5tts_engine._auto_transcribe(sample_audio_file, "en")
        
        assert result == "Transcribed text"
        assert mock_model.transcribe.called


@pytest.mark.asyncio
async def test_f5tts_audio_normalization(f5tts_engine):
    """Áudio é normalizado antes de síntese"""
    # Mock com áudio de alta amplitude
    loud_audio = np.random.randn(24000) * 10  # Amplitude alta
    
    f5tts_engine.tts.infer = MagicMock(return_value=loud_audio)
    
    audio_bytes, duration = await f5tts_engine.generate_dubbing(
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


def test_f5tts_model_loading():
    """F5-TTS model é carregado corretamente"""
    with patch('app.engines.f5tts_engine.F5TTS') as mock_f5tts:
        mock_model = MagicMock()
        mock_f5tts.from_pretrained.return_value = mock_model
        
        engine = F5TtsEngine(
            device='cpu',
            model_name='SWivid/F5-TTS'
        )
        
        # Verifica que modelo foi carregado
        assert mock_f5tts.from_pretrained.called
        call_args = mock_f5tts.from_pretrained.call_args
        assert 'SWivid/F5-TTS' in str(call_args)
