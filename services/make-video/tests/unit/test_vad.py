"""
Testes para app.vad
"""

import pytest
import sys
import struct
from unittest.mock import Mock, patch, MagicMock, mock_open

# Mock webrtcvad
webrtcvad_mock = MagicMock()
sys.modules['webrtcvad'] = webrtcvad_mock

# Mock cv2/pytesseract se necessário
if 'cv2' not in sys.modules:
    sys.modules['cv2'] = MagicMock()
if 'pytesseract' not in sys.modules:
    sys.modules['pytesseract'] = MagicMock()

from app.vad import (
    VoiceActivityDetector,
    SpeechSegment,
    VADMethod
)


@pytest.fixture
def vad_detector():
    """VAD detector com WebRTC mockado"""
    detector = VoiceActivityDetector(
        frame_duration_ms=30,
        aggressiveness=3,
        energy_threshold=0.02,
        min_speech_duration=0.3,
        min_silence_duration=0.3
    )
    return detector


@pytest.fixture
def sample_audio_data():
    """Dados de áudio de exemplo (16-bit PCM)"""
    # Criar 1 segundo de áudio a 16kHz (16000 samples * 2 bytes)
    num_samples = 16000
    
    # Metade silêncio (valores baixos), metade fala (valores altos)
    silence = [100] * (num_samples // 2)  # Energia baixa
    speech = [10000] * (num_samples // 2)  # Energia alta
    
    samples = silence + speech
    
    # Pack como 16-bit signed integers
    audio_data = struct.pack(f'<{len(samples)}h', *samples)
    
    return audio_data


def test_vad_initialization():
    """Testa inicialização do VAD"""
    detector = VoiceActivityDetector(
        frame_duration_ms=20,
        aggressiveness=2,
        energy_threshold=0.03
    )
    
    assert detector.frame_duration_ms == 20
    assert detector.aggressiveness == 2
    assert detector.energy_threshold == 0.03


def test_vad_initialization_without_webrtcvad():
    """Testa inicialização sem webrtcvad disponível"""
    # Simular ImportError ao tentar importar webrtcvad
    with patch.dict('sys.modules', {'webrtcvad': None}):
        # Criar detector sem webrtcvad
        detector = VoiceActivityDetector()
        
        # Deve funcionar mesmo sem webrtcvad (fallback para energy)
        assert detector.vad is None


def test_calculate_rms_energy(vad_detector):
    """Testa cálculo de energia RMS"""
    # Frame com silêncio (valores baixos)
    silence_frame = struct.pack('<100h', *([100] * 100))
    silence_energy = vad_detector._calculate_rms_energy(silence_frame)
    
    # Frame com fala (valores altos)
    speech_frame = struct.pack('<100h', *([10000] * 100))
    speech_energy = vad_detector._calculate_rms_energy(speech_frame)
    
    # Energia de fala deve ser maior que silêncio
    assert speech_energy > silence_energy
    
    # Energia deve estar normalizada (0-1)
    assert 0.0 <= silence_energy <= 1.0
    assert 0.0 <= speech_energy <= 1.0


def test_calculate_rms_energy_empty_frame(vad_detector):
    """Testa energia RMS com frame vazio"""
    empty_frame = b''
    energy = vad_detector._calculate_rms_energy(empty_frame)
    assert energy == 0.0


def test_filter_short_segments(vad_detector):
    """Testa filtro de segmentos curtos"""
    segments = [
        SpeechSegment(0.0, 0.5, 0.9, VADMethod.WEBRTC),   # >= 0.3s ✓
        SpeechSegment(1.0, 1.1, 0.8, VADMethod.WEBRTC),   # < 0.3s ✗
        SpeechSegment(2.0, 2.4, 0.9, VADMethod.WEBRTC),   # >= 0.3s ✓
        SpeechSegment(3.0, 3.15, 0.7, VADMethod.WEBRTC),  # < 0.3s ✗
    ]
    
    filtered = vad_detector._filter_short_segments(segments)
    
    assert len(filtered) == 2
    assert filtered[0].start_time == 0.0
    assert filtered[1].start_time == 2.0


def test_merge_close_segments(vad_detector):
    """Testa merge de segmentos próximos"""
    segments = [
        SpeechSegment(0.0, 1.0, 0.9, VADMethod.WEBRTC),
        SpeechSegment(1.1, 2.0, 0.8, VADMethod.WEBRTC),  # Gap 0.1s < 0.3s → merge
        SpeechSegment(2.5, 3.0, 0.9, VADMethod.WEBRTC),  # Gap 0.5s > 0.3s → não merge
    ]
    
    merged = vad_detector._merge_close_segments(segments)
    
    assert len(merged) == 2
    # Primeiro merged: 0.0 - 2.0
    assert merged[0].start_time == 0.0
    assert merged[0].end_time == 2.0
    # Segundo: 2.5 - 3.0
    assert merged[1].start_time == 2.5
    assert merged[1].end_time == 3.0


def test_merge_close_segments_empty(vad_detector):
    """Testa merge com lista vazia"""
    merged = vad_detector._merge_close_segments([])
    assert merged == []


def test_segments_to_timestamps(vad_detector):
    """Testa conversão de segmentos para timestamps"""
    segments = [
        SpeechSegment(0.0, 1.5, 0.9, VADMethod.WEBRTC),
        SpeechSegment(2.0, 3.5, 0.8, VADMethod.ENERGY),
    ]
    
    timestamps = vad_detector.segments_to_timestamps(segments)
    
    assert timestamps == [(0.0, 1.5), (2.0, 3.5)]


@patch('wave.open')
def test_read_wave(mock_wave_open, vad_detector):
    """Testa leitura de arquivo WAV"""
    # Mock do wave file
    mock_wf = MagicMock()
    mock_wf.getframerate.return_value = 16000
    mock_wf.getnframes.return_value = 16000
    mock_wf.readframes.return_value = b'\x00\x00' * 16000
    
    mock_wave_open.return_value.__enter__.return_value = mock_wf
    
    sample_rate, audio_data = vad_detector._read_wave('/fake/audio.wav')
    
    assert sample_rate == 16000
    assert len(audio_data) == 32000  # 16000 frames * 2 bytes


def test_detect_energy(vad_detector, sample_audio_data):
    """Testa detecção por energia"""
    segments = vad_detector._detect_energy(sample_audio_data, 16000)
    
    # Deve detectar pelo menos um segmento de fala
    assert len(segments) > 0
    
    # Todos segmentos devem ser do tipo ENERGY
    for segment in segments:
        assert segment.method == VADMethod.ENERGY
        assert 0.0 <= segment.confidence <= 1.0


def test_detect_webrtc_invalid_sample_rate(vad_detector, sample_audio_data):
    """Testa WebRTC VAD com sample rate inválido"""
    # Mock do WebRTC VAD
    mock_vad = MagicMock()
    vad_detector.vad = mock_vad
    
    # Sample rate inválido (não é 8k, 16k, 32k, 48k)
    with patch.object(vad_detector, '_detect_energy') as mock_energy:
        mock_energy.return_value = []
        
        segments = vad_detector._detect_webrtc(sample_audio_data, 22050)
        
        # Deve fazer fallback para energy
        mock_energy.assert_called_once()


def test_detect_webrtc_valid(vad_detector):
    """Testa WebRTC VAD com dados válidos"""
    # Mock do WebRTC VAD
    mock_vad = MagicMock()
    
    # Padrão: True, True, False, False (fala, fala, silêncio, silêncio)
    mock_vad.is_speech.side_effect = [True, True, False, False]
    
    vad_detector.vad = mock_vad
    
    # 4 frames de 30ms cada = 960 samples * 2 bytes = 1920 bytes por frame
    frame_size = int(16000 * 30 / 1000) * 2
    audio_data = b'\x00\x00' * (frame_size * 2)  # 4 frames
    
    segments = vad_detector._detect_webrtc(audio_data, 16000)
    
    # Deve detectar 1 segmento (2 frames de fala seguidos)
    assert len(segments) >= 1
    assert segments[0].method == VADMethod.WEBRTC


@patch('wave.open')
@patch.object(VoiceActivityDetector, '_detect_energy')
def test_detect_speech_segments_energy_fallback(
    mock_detect_energy,
    mock_wave_open,
    vad_detector
):
    """Testa detecção com fallback para energia"""
    # Remover WebRTC VAD
    vad_detector.vad = None
    
    # Mock wave file
    mock_wf = MagicMock()
    mock_wf.getframerate.return_value = 16000
    mock_wf.getnframes.return_value = 16000
    mock_wf.readframes.return_value = b'\x00\x00' * 16000
    mock_wave_open.return_value.__enter__.return_value = mock_wf
    
    # Mock energy detection
    mock_detect_energy.return_value = [
        SpeechSegment(0.0, 1.0, 0.8, VADMethod.ENERGY)
    ]
    
    segments = vad_detector.detect_speech_segments('/fake/audio.wav')
    
    assert len(segments) == 1
    assert segments[0].method == VADMethod.ENERGY
    mock_detect_energy.assert_called_once()


@patch('wave.open')
def test_detect_speech_segments_webrtc(mock_wave_open, vad_detector):
    """Testa detecção com WebRTC"""
    # Mock WebRTC VAD
    mock_vad = MagicMock()
    mock_vad.is_speech.return_value = True
    vad_detector.vad = mock_vad
    
    # Mock wave file
    mock_wf = MagicMock()
    mock_wf.getframerate.return_value = 16000
    mock_wf.getnframes.return_value = 16000
    mock_wf.readframes.return_value = b'\x00\x00' * 16000
    mock_wave_open.return_value.__enter__.return_value = mock_wf
    
    segments = vad_detector.detect_speech_segments('/fake/audio.wav')
    
    # Deve ter chamado WebRTC VAD
    assert mock_vad.is_speech.called


def test_speech_segment_dataclass():
    """Testa SpeechSegment dataclass"""
    segment = SpeechSegment(
        start_time=1.5,
        end_time=3.0,
        confidence=0.85,
        method=VADMethod.WEBRTC
    )
    
    assert segment.start_time == 1.5
    assert segment.end_time == 3.0
    assert segment.confidence == 0.85
    assert segment.method == VADMethod.WEBRTC
    
    # Calcular duração
    duration = segment.end_time - segment.start_time
    assert duration == 1.5


@patch('wave.open')
@patch.object(VoiceActivityDetector, '_detect_energy')
def test_webrtc_fallback_when_not_available(
    mock_detect_energy,
    mock_wave_open,
    vad_detector
):
    """Testa fallback para energy quando WebRTC é solicitado mas não disponível"""
    # Remover WebRTC VAD
    vad_detector.vad = None
    
    # Mock wave file
    mock_wf = MagicMock()
    mock_wf.getframerate.return_value = 16000
    mock_wf.getnframes.return_value = 16000
    mock_wf.readframes.return_value = b'\x00\x00' * 16000
    mock_wave_open.return_value.__enter__.return_value = mock_wf
    
    # Mock energy detection
    mock_detect_energy.return_value = [
        SpeechSegment(0.0, 1.0, 0.8, VADMethod.ENERGY)
    ]
    
    # Solicitar WebRTC explicitamente (mas não está disponível)
    segments = vad_detector.detect_speech_segments(
        '/fake/audio.wav',
        method=VADMethod.WEBRTC
    )
    
    # Deve fazer fallback para energy
    assert len(segments) == 1
    assert segments[0].method == VADMethod.ENERGY
    mock_detect_energy.assert_called_once()
