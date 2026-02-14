"""
Voice Activity Detection (VAD)

Detecta segmentos de fala em áudio usando WebRTC VAD e análise de energia
"""

import logging
import wave
import struct
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

from app.infrastructure.metrics import vad_method_used_total

logger = logging.getLogger(__name__)


class VADMethod(Enum):
    """Método VAD usado"""
    WEBRTC = "webrtc"
    ENERGY = "energy"
    NONE = "none"


@dataclass
class SpeechSegment:
    """Segmento de fala detectado"""
    start_time: float  # Segundos
    end_time: float    # Segundos
    confidence: float  # 0.0 - 1.0
    method: VADMethod


class VoiceActivityDetector:
    """
    Detector de atividade de voz
    
    Usa WebRTC VAD como método primário e fallback para análise de energia
    """
    
    def __init__(
        self,
        frame_duration_ms: int = 30,
        aggressiveness: int = 3,
        energy_threshold: float = 0.02,
        min_speech_duration: float = 0.3,
        min_silence_duration: float = 0.3
    ):
        """
        Args:
            frame_duration_ms: Duração do frame (10, 20 ou 30ms)
            aggressiveness: Nível WebRTC VAD (0-3, 3 = mais agressivo)
            energy_threshold: Threshold de energia (0.0-1.0)
            min_speech_duration: Duração mínima de fala (segundos)
            min_silence_duration: Duração mínima de silêncio (segundos)
        """
        self.frame_duration_ms = frame_duration_ms
        self.aggressiveness = aggressiveness
        self.energy_threshold = energy_threshold
        self.min_speech_duration = min_speech_duration
        self.min_silence_duration = min_silence_duration
        
        # Tentar importar webrtcvad
        self.vad = None
        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(aggressiveness)
            logger.info(f"WebRTC VAD initialized (aggressiveness={aggressiveness})")
        except ImportError:
            logger.warning("webrtcvad not available, using energy-based VAD")
        
        logger.info(
            f"VoiceActivityDetector initialized "
            f"(frame={frame_duration_ms}ms, energy_threshold={energy_threshold})"
        )
    
    def detect_speech_segments(
        self,
        audio_path: str,
        method: Optional[VADMethod] = None
    ) -> List[SpeechSegment]:
        """
        Detecta segmentos de fala no áudio
        
        Args:
            audio_path: Path do arquivo de áudio WAV
            method: Método VAD (None = auto-detect)
        
        Returns:
            Lista de segmentos de fala
        """
        # Auto-detectar método
        if method is None:
            method = VADMethod.WEBRTC if self.vad else VADMethod.ENERGY
        
        logger.info(f"Detecting speech segments using {method.value} method")
        vad_method_used_total.labels(method=method.value).inc()
        
        # Ler áudio
        sample_rate, audio_frames = self._read_wave(audio_path)
        
        # Escolher método com fallback
        if method == VADMethod.WEBRTC and self.vad:
            segments = self._detect_webrtc(audio_frames, sample_rate)
        elif method == VADMethod.WEBRTC and not self.vad:
            # Fallback: WebRTC solicitado mas não disponível
            logger.warning("WebRTC VAD requested but not available, using energy fallback")
            segments = self._detect_energy(audio_frames, sample_rate)
        elif method == VADMethod.ENERGY:
            segments = self._detect_energy(audio_frames, sample_rate)
        else:
            logger.warning("No VAD method available, returning empty segments")
            return []
        
        # Filtrar segmentos muito curtos
        segments = self._filter_short_segments(segments)
        
        # Merge segmentos próximos
        segments = self._merge_close_segments(segments)
        
        logger.info(f"Detected {len(segments)} speech segments")
        
        return segments
    
    def _read_wave(self, audio_path: str) -> Tuple[int, bytes]:
        """
        Lê arquivo WAV
        
        Returns:
            (sample_rate, audio_data)
        """
        with wave.open(audio_path, 'rb') as wf:
            sample_rate = wf.getframerate()
            num_frames = wf.getnframes()
            audio_data = wf.readframes(num_frames)
            
            logger.debug(
                f"Audio loaded: {sample_rate}Hz, {num_frames} frames, "
                f"{len(audio_data)} bytes"
            )
            
            return sample_rate, audio_data
    
    def _detect_webrtc(
        self,
        audio_data: bytes,
        sample_rate: int
    ) -> List[SpeechSegment]:
        """
        Detecta fala usando WebRTC VAD
        
        Args:
            audio_data: Dados de áudio raw (16-bit PCM)
            sample_rate: Sample rate (deve ser 8000, 16000, 32000 ou 48000)
        
        Returns:
            Lista de segmentos
        """
        if not self.vad:
            return []
        
        # Validar sample rate
        if sample_rate not in [8000, 16000, 32000, 48000]:
            logger.warning(f"Invalid sample rate {sample_rate}Hz for WebRTC VAD")
            return self._detect_energy(audio_data, sample_rate)
        
        # Calcular tamanho do frame em bytes
        frame_size = int(sample_rate * self.frame_duration_ms / 1000) * 2  # 2 bytes per sample
        
        segments = []
        speech_start = None
        
        # Processar frames
        for i in range(0, len(audio_data) - frame_size, frame_size):
            frame = audio_data[i:i + frame_size]
            
            # Verificar se é fala
            is_speech = self.vad.is_speech(frame, sample_rate)
            
            timestamp = i / (sample_rate * 2)  # 2 bytes per sample
            
            if is_speech and speech_start is None:
                # Início de fala
                speech_start = timestamp
            elif not is_speech and speech_start is not None:
                # Fim de fala
                segments.append(SpeechSegment(
                    start_time=speech_start,
                    end_time=timestamp,
                    confidence=0.9,  # WebRTC não fornece confidence, usar alto
                    method=VADMethod.WEBRTC
                ))
                speech_start = None
        
        # Adicionar último segmento se ainda em fala
        if speech_start is not None:
            segments.append(SpeechSegment(
                start_time=speech_start,
                end_time=len(audio_data) / (sample_rate * 2),
                confidence=0.9,
                method=VADMethod.WEBRTC
            ))
        
        return segments
    
    def _detect_energy(
        self,
        audio_data: bytes,
        sample_rate: int
    ) -> List[SpeechSegment]:
        """
        Detecta fala usando análise de energia
        
        Args:
            audio_data: Dados de áudio raw (16-bit PCM)
            sample_rate: Sample rate
        
        Returns:
            Lista de segmentos
        """
        # Calcular tamanho do frame
        frame_size = int(sample_rate * self.frame_duration_ms / 1000) * 2
        
        segments = []
        speech_start = None
        
        # Processar frames
        for i in range(0, len(audio_data) - frame_size, frame_size):
            frame = audio_data[i:i + frame_size]
            
            # Calcular energia RMS
            energy = self._calculate_rms_energy(frame)
            
            is_speech = energy > self.energy_threshold
            
            timestamp = i / (sample_rate * 2)
            
            if is_speech and speech_start is None:
                # Início de fala
                speech_start = timestamp
            elif not is_speech and speech_start is not None:
                # Fim de fala
                confidence = min(energy / self.energy_threshold, 1.0)
                segments.append(SpeechSegment(
                    start_time=speech_start,
                    end_time=timestamp,
                    confidence=confidence,
                    method=VADMethod.ENERGY
                ))
                speech_start = None
        
        # Adicionar último segmento
        if speech_start is not None:
            segments.append(SpeechSegment(
                start_time=speech_start,
                end_time=len(audio_data) / (sample_rate * 2),
                confidence=0.7,
                method=VADMethod.ENERGY
            ))
        
        return segments
    
    def _calculate_rms_energy(self, frame: bytes) -> float:
        """
        Calcula energia RMS do frame
        
        Args:
            frame: Frame de áudio (16-bit PCM)
        
        Returns:
            Energia RMS normalizada (0.0 - 1.0)
        """
        # Converter bytes para samples int16
        num_samples = len(frame) // 2
        
        if num_samples == 0:
            return 0.0
        
        # Unpack como shorts (16-bit signed integers)
        samples = struct.unpack(f'<{num_samples}h', frame)
        
        # Calcular RMS
        sum_squares = sum(s * s for s in samples)
        rms = (sum_squares / num_samples) ** 0.5
        
        # Normalizar (max 16-bit = 32768)
        normalized = rms / 32768.0
        
        return normalized
    
    def _filter_short_segments(
        self,
        segments: List[SpeechSegment]
    ) -> List[SpeechSegment]:
        """
        Remove segmentos muito curtos
        
        Args:
            segments: Lista de segmentos
        
        Returns:
            Segmentos filtrados
        """
        filtered = []
        
        for segment in segments:
            duration = segment.end_time - segment.start_time
            
            if duration >= self.min_speech_duration:
                filtered.append(segment)
            else:
                logger.debug(
                    f"Filtered short segment: {segment.start_time:.2f}s - "
                    f"{segment.end_time:.2f}s (duration={duration:.2f}s)"
                )
        
        return filtered
    
    def _merge_close_segments(
        self,
        segments: List[SpeechSegment]
    ) -> List[SpeechSegment]:
        """
        Merge segmentos com silêncio curto entre eles
        
        Args:
            segments: Lista de segmentos
        
        Returns:
            Segmentos merged
        """
        if not segments:
            return []
        
        merged = [segments[0]]
        
        for segment in segments[1:]:
            last_segment = merged[-1]
            
            # Calcular gap entre segmentos
            gap = segment.start_time - last_segment.end_time
            
            if gap < self.min_silence_duration:
                # Merge: estender segmento anterior
                merged[-1] = SpeechSegment(
                    start_time=last_segment.start_time,
                    end_time=segment.end_time,
                    confidence=max(last_segment.confidence, segment.confidence),
                    method=last_segment.method
                )
                logger.debug(f"Merged segments with gap={gap:.2f}s")
            else:
                # Adicionar novo segmento
                merged.append(segment)
        
        return merged
    
    def segments_to_timestamps(
        self,
        segments: List[SpeechSegment]
    ) -> List[Tuple[float, float]]:
        """
        Converte segmentos para lista de tuplas (start, end)
        
        Args:
            segments: Lista de segmentos
        
        Returns:
            Lista de (start_time, end_time)
        """
        return [(s.start_time, s.end_time) for s in segments]
