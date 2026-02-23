"""
Helpers vendorizados para Voice Activity Detection (VAD).

Fornece funções compatíveis com silero-vad vendorizado (modelo JIT),
sem dependência de torch.hub em runtime.
"""

import logging
from typing import List, Dict, Optional
import subprocess
import os
import tempfile

logger = logging.getLogger(__name__)

# Lazy imports para torch (pode não estar disponível)
try:
    import torch
    import torchaudio
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("⚠️ torch/torchaudio não disponível, VAD silero-vad desabilitado")


def get_speech_timestamps(
    wav: "torch.Tensor",
    model,
    threshold: float = 0.5,
    sampling_rate: int = 16000,
    min_speech_duration_ms: int = 250,
    min_silence_duration_ms: int = 100,
    window_size_samples: int = 512,
    speech_pad_ms: int = 30
) -> List[Dict[str, int]]:
    """
    Detecta timestamps de fala usando modelo silero-vad.
    
    Compatível com modelo vendorizado (.jit).
    
    Args:
        wav: Tensor de áudio (mono, 16kHz)
        model: Modelo silero-vad carregado (torch.jit.load)
        threshold: Limiar de confiança (0-1)
        sampling_rate: Taxa de amostragem (deve ser 16000)
        min_speech_duration_ms: Duração mínima de fala (ms)
        min_silence_duration_ms: Duração mínima de silêncio (ms)
        window_size_samples: Tamanho da janela de análise
        speech_pad_ms: Padding de fala (ms)
    
    Returns:
        Lista de {'start': int, 'end': int} em samples
    """
    if not TORCH_AVAILABLE:
        logger.error("⚠️ torch não disponível, impossível usar get_speech_timestamps")
        return []
    
    if sampling_rate != 16000:
        raise ValueError("Silero-VAD requer sampling_rate=16000")
    
    # Garantir que wav está em formato correto
    if wav.dim() == 1:
        wav = wav.unsqueeze(0)  # Add batch dimension
    
    # Detectar fala
    try:
        # Modelo espera (batch, samples)
        speech_probs = []
        
        # Processar em janelas
        for i in range(0, len(wav[0]), window_size_samples):
            chunk = wav[:, i:i+window_size_samples]
            
            if len(chunk[0]) < window_size_samples:
                # Pad última chunk
                padding = window_size_samples - len(chunk[0])
                chunk = torch.nn.functional.pad(chunk, (0, padding))
            
            # Inferência
            with torch.no_grad():
                speech_prob = model(chunk, sampling_rate).item()
            
            speech_probs.append({
                'start': i,
                'end': i + window_size_samples,
                'speech_prob': speech_prob
            })
        
        # Converter probabilidades em timestamps
        timestamps = _probs_to_timestamps(
            speech_probs,
            threshold=threshold,
            sampling_rate=sampling_rate,
            min_speech_duration_ms=min_speech_duration_ms,
            min_silence_duration_ms=min_silence_duration_ms,
            speech_pad_ms=speech_pad_ms
        )
        
        return timestamps
    
    except Exception as e:
        logger.error(f"Erro em get_speech_timestamps: {e}")
        # Fallback: retornar segmento completo
        return [{'start': 0, 'end': len(wav[0]) if wav.dim() > 1 else len(wav)}]


def _probs_to_timestamps(
    speech_probs: List[Dict],
    threshold: float,
    sampling_rate: int,
    min_speech_duration_ms: int,
    min_silence_duration_ms: int,
    speech_pad_ms: int
) -> List[Dict[str, int]]:
    """
    Converte probabilidades de fala em timestamps discretos.
    
    Lógica:
    1. Marca frames com prob > threshold como "fala"
    2. Merge segmentos próximos (gap < min_silence)
    3. Remove segmentos curtos (< min_speech_duration)
    4. Aplica padding
    """
    min_speech_samples = int(min_speech_duration_ms * sampling_rate / 1000)
    min_silence_samples = int(min_silence_duration_ms * sampling_rate / 1000)
    speech_pad_samples = int(speech_pad_ms * sampling_rate / 1000)
    
    timestamps = []
    current_speech = None
    
    for prob_info in speech_probs:
        is_speech = prob_info['speech_prob'] >= threshold
        
        if is_speech:
            if current_speech is None:
                # Início de novo segmento
                current_speech = {
                    'start': max(0, prob_info['start'] - speech_pad_samples),
                    'end': prob_info['end']
                }
            else:
                # Estender segmento atual
                current_speech['end'] = prob_info['end']
        else:
            if current_speech is not None:
                # Fim de segmento, verificar se válido
                duration = current_speech['end'] - current_speech['start']
                
                if duration >= min_speech_samples:
                    # Aplicar padding final
                    current_speech['end'] += speech_pad_samples
                    timestamps.append(current_speech)
                
                current_speech = None
    
    # Adicionar último segmento se existir
    if current_speech is not None:
        duration = current_speech['end'] - current_speech['start']
        if duration >= min_speech_samples:
            current_speech['end'] += speech_pad_samples
            timestamps.append(current_speech)
    
    # Merge segmentos próximos
    merged = _merge_close_segments(timestamps, min_silence_samples)
    
    return merged


def _merge_close_segments(
    timestamps: List[Dict[str, int]],
    min_gap_samples: int
) -> List[Dict[str, int]]:
    """Merge segmentos com gap < min_gap_samples"""
    if not timestamps:
        return []
    
    merged = [timestamps[0]]
    
    for ts in timestamps[1:]:
        prev = merged[-1]
        gap = ts['start'] - prev['end']
        
        if gap < min_gap_samples:
            # Merge com anterior
            prev['end'] = ts['end']
        else:
            merged.append(ts)
    
    return merged


def load_audio_torch(
    audio_path: str,
    sampling_rate: int = 16000
) -> "torch.Tensor":
    """
    Carrega áudio usando torchaudio (compatível com silero-vad).
    
    Args:
        audio_path: Path do arquivo de áudio
        sampling_rate: Taxa de amostragem desejada
    
    Returns:
        Tensor de áudio (mono, sampling_rate)
    """
    if not TORCH_AVAILABLE:
        raise ImportError("torch/torchaudio não disponível")
    
    try:
        # Carregar com torchaudio
        waveform, sr = torchaudio.load(audio_path)
        
        # Converter para mono se necessário
        if waveform.shape[0] > 1:
            waveform = torch.mean(waveform, dim=0, keepdim=True)
        
        # Resample se necessário
        if sr != sampling_rate:
            resampler = torchaudio.transforms.Resample(
                orig_freq=sr,
                new_freq=sampling_rate
            )
            waveform = resampler(waveform)
        
        # Retornar sem batch dimension (squeeze)
        return waveform.squeeze(0)
    
    except Exception as e:
        logger.error(f"Erro ao carregar áudio com torchaudio: {e}")
        raise


def convert_to_16k_wav(
    input_path: str,
    output_path: Optional[str] = None
) -> str:
    """
    Converte áudio para formato requerido por webrtcvad: 16kHz, mono, PCM16.
    
    Args:
        input_path: Path do áudio original
        output_path: Path de saída (se None, cria tempfile)
    
    Returns:
        Path do arquivo convertido
    """
    if output_path is None:
        # Criar arquivo temporário
        fd, output_path = tempfile.mkstemp(suffix='.wav')
        os.close(fd)
    
    cmd = [
        'ffmpeg', '-y',
        '-hide_banner',
        '-nostdin',
        '-i', input_path,
        '-ar', '16000',  # 16kHz
        '-ac', '1',       # Mono
        '-sample_fmt', 's16',  # PCM16
        output_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Erro ao converter áudio para 16kHz WAV: {result.stderr[:500]}"
            )
        
        return output_path
    
    except subprocess.TimeoutExpired:
        raise RuntimeError("Timeout ao converter áudio para 16kHz WAV")
    except Exception as e:
        logger.error(f"Erro em convert_to_16k_wav: {e}")
        raise


def validate_audio_format(audio_path: str) -> Dict[str, any]:
    """
    Valida formato de áudio usando ffprobe.
    
    Returns:
        {'sample_rate': int, 'channels': int, 'codec': str, 'duration': float}
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'stream=sample_rate,channels,codec_name',
        '-show_entries', 'format=duration',
        '-of', 'json',
        audio_path
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe falhou: {result.stderr}")
        
        import json
        data = json.loads(result.stdout)
        
        stream = data['streams'][0]
        format_info = data['format']
        
        return {
            'sample_rate': int(stream.get('sample_rate', 0)),
            'channels': int(stream.get('channels', 0)),
            'codec': stream.get('codec_name', 'unknown'),
            'duration': float(format_info.get('duration', 0.0))
        }
    
    except Exception as e:
        logger.error(f"Erro ao validar formato de áudio: {e}")
        raise
