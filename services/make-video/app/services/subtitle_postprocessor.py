"""
Speech-Gated Subtitles: Garante que legendas só aparecem quando há fala.

Pipeline:
1. VAD detecta segmentos de fala no áudio final
2. Clamp cues para dentro dos speech segments
3. Drop cues que não intersectam nenhum segment
4. Merge cues próximos (gap < 120ms)
5. Enforce duração mínima (120ms)
"""

import numpy as np
import logging
from typing import List, Dict, Tuple, Optional
import subprocess
import json
import tempfile
import os
import wave
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Lazy imports para torch (podem não estar disponíveis em ambiente de teste)
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("⚠️ torch não disponível, VAD silero-vad desabilitado")

# Import helpers vendorizados (também com lazy loading)
try:
    from app.vad_utils import (
        get_speech_timestamps,
        load_audio_torch,
        convert_to_16k_wav,
        validate_audio_format
    )
    VAD_UTILS_AVAILABLE = True
except ImportError:
    VAD_UTILS_AVAILABLE = False
    logger.warning("⚠️ vad_utils não disponível")


@dataclass
class SpeechSegment:
    """Segmento de fala detectado por VAD"""
    start: float
    end: float
    confidence: float


@dataclass
class SubtitleCue:
    """Cue de legenda individual"""
    index: int
    start: float
    end: float
    text: str


class SpeechGatedSubtitles:
    """
    Garante que legendas só aparecem quando há fala.
    
    Parâmetros:
    - pre_pad: 60ms (cue pode começar antes do fonema)
    - post_pad: 120ms (cue fica após fonema, melhor legibilidade)
    - min_duration: 120ms (mínimo para ser legível)
    - merge_gap: 120ms (se gap < 120ms, juntar cues)
    """
    
    def __init__(
        self,
        pre_pad: float = 0.06,
        post_pad: float = 0.12,
        word_post_pad: float = 0.03,  # 🆕 Micro folga por palavra
        min_duration: float = 0.12,
        merge_gap: float = 0.12,
        vad_threshold: float = 0.5,
        model_path: str = '/app/models/silero_vad.jit'
    ):
        self.pre_pad = pre_pad
        self.post_pad = post_pad
        self.word_post_pad = word_post_pad  # 🆕 Novo parâmetro
        self.min_duration = min_duration
        self.merge_gap = merge_gap
        self.vad_threshold = vad_threshold
        self.model_path = model_path
        
        # Carregar modelo VAD vendorizado (não torch.hub runtime)
        self.model = None
        self.vad_available = False
        self.webrtc_vad = None
        
        self._load_vad_model()
    
    def _load_vad_model(self):
        """Carrega modelo VAD com fallbacks"""
        if not TORCH_AVAILABLE:
            logger.warning("⚠️ torch não disponível, pulando silero-vad")
            self._load_fallback_vad()
            return
        
        try:
            # Tentar carregar silero-vad vendorizado
            if os.path.exists(self.model_path):
                self.model = torch.jit.load(self.model_path)
                self.vad_available = True
                logger.info("✅ Silero-VAD carregado (vendorizado)")
                return
            else:
                logger.warning(
                    f"⚠️ Modelo silero-vad não encontrado em {self.model_path}"
                )
        except Exception as e:
            logger.warning(f"⚠️ Erro ao carregar silero-vad: {e}")
        
        self._load_fallback_vad()
    
    def _load_fallback_vad(self):
        """Carrega VAD fallback (webrtcvad ou RMS)"""
        # Fallback 1: webrtcvad (leve)
        try:
            import webrtcvad
            self.webrtc_vad = webrtcvad.Vad(2)  # Agressividade média
            logger.info("✅ Usando webrtcvad (fallback)")
            return
        except ImportError:
            logger.warning("⚠️ webrtcvad não disponível")
        
        # Fallback 2: RMS simples (degradado)
        logger.warning("⚠️ VAD total fallback: usando RMS simples")
    
    def detect_speech_segments(
        self,
        audio_path: str
    ) -> Tuple[List[SpeechSegment], bool]:
        """
        Detecta segmentos de fala usando VAD (silero-vad ou webrtcvad).
        
        Returns:
            (segments: List[SpeechSegment], vad_ok: bool)
            vad_ok=False indica fallback usado
        """
        if self.model is not None:
            # Silero-VAD (preferível)
            segments = self._detect_with_silero(audio_path)
            logger.info(f"🎙️ Detectados {len(segments)} segmentos de fala (silero)")
            return segments, True
        
        elif self.webrtc_vad is not None:
            # Fallback: webrtcvad (leve)
            logger.info("🔄 Usando webrtcvad (fallback)")
            segments = self._detect_with_webrtc(audio_path)
            return segments, False
        
        else:
            # Último recurso: RMS simples
            logger.warning("⚠️ VAD total fallback: usando RMS simples")
            segments = self._detect_with_rms(audio_path)
            return segments, False
    
    def _detect_with_silero(self, audio_path: str) -> List[SpeechSegment]:
        """Detecção com silero-vad"""
        if not TORCH_AVAILABLE or not VAD_UTILS_AVAILABLE:
            logger.error("⚠️ torch ou vad_utils não disponível para silero-vad")
            return []
        
        wav = load_audio_torch(audio_path, sampling_rate=16000)
        
        speech_timestamps = get_speech_timestamps(
            wav,
            self.model,
            threshold=self.vad_threshold,
            sampling_rate=16000,
            min_speech_duration_ms=250,
            min_silence_duration_ms=100
        )
        
        segments = []
        for ts in speech_timestamps:
            segments.append(SpeechSegment(
                start=ts['start'] / 16000.0,
                end=ts['end'] / 16000.0,
                confidence=1.0
            ))
        
        return segments
    
    def _detect_with_webrtc(self, audio_path: str) -> List[SpeechSegment]:
        """Fallback com webrtcvad (leve)"""
        if not VAD_UTILS_AVAILABLE:
            logger.error("⚠️ vad_utils não disponível")
            return []
        
        # Converter para 16kHz mono WAV (requerido por webrtcvad)
        wav_path = convert_to_16k_wav(audio_path)
        
        segments = []
        try:
            with wave.open(wav_path, 'rb') as wf:
                frames = wf.readframes(wf.getnframes())
                sample_rate = wf.getframerate()
                
                # Processar em chunks de 30ms
                frame_duration = 30  # ms
                frame_size = int(sample_rate * frame_duration / 1000) * 2
                
                speech_start = None
                for i in range(0, len(frames), frame_size):
                    frame = frames[i:i+frame_size]
                    if len(frame) < frame_size:
                        break
                    
                    is_speech = self.webrtc_vad.is_speech(frame, sample_rate)
                    timestamp = i / (sample_rate * 2)  # bytes to seconds
                    
                    if is_speech and speech_start is None:
                        speech_start = timestamp
                    elif not is_speech and speech_start is not None:
                        segments.append(SpeechSegment(
                            start=speech_start,
                            end=timestamp,
                            confidence=0.8  # Lower confidence for fallback
                        ))
                        speech_start = None
                
                # Adicionar último segmento se existir
                if speech_start is not None:
                    duration = validate_audio_format(audio_path)['duration']
                    segments.append(SpeechSegment(
                        start=speech_start,
                        end=duration,
                        confidence=0.8
                    ))
        
        finally:
            # Limpar arquivo temporário
            if wav_path != audio_path and os.path.exists(wav_path):
                os.remove(wav_path)
        
        return segments
    
    def _detect_with_rms(self, audio_path: str) -> List[SpeechSegment]:
        """Fallback RMS simples (degradado)"""
        try:
            import librosa
        except ImportError:
            logger.error("⚠️ librosa não disponível, impossível usar RMS fallback")
            # Fallback extremo: retornar áudio completo
            if VAD_UTILS_AVAILABLE:
                duration = validate_audio_format(audio_path)['duration']
            else:
                # Sem vad_utils, tentar ffprobe direto
                try:
                    cmd = ['ffprobe', '-v', 'error', '-show_entries', 
                           'format=duration', '-of', 'json', audio_path]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                    data = json.loads(result.stdout)
                    duration = float(data['format']['duration'])
                except Exception:
                    duration = 300.0  # 5min default
            
            return [SpeechSegment(start=0.0, end=duration, confidence=0.1)]
        
        y, sr = librosa.load(audio_path, sr=16000)
        rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
        
        # Threshold: 10% do RMS máximo
        threshold = np.max(rms) * 0.1
        
        segments = []
        in_speech = False
        speech_start = None
        
        for i, r in enumerate(rms):
            timestamp = i * 512 / sr
            
            if r > threshold and not in_speech:
                speech_start = timestamp
                in_speech = True
            elif r <= threshold and in_speech:
                segments.append(SpeechSegment(
                    start=speech_start,
                    end=timestamp,
                    confidence=0.5  # Muito baixa confidence
                ))
                in_speech = False
        
        # Adicionar último segmento se existir
        if in_speech:
            duration = len(y) / sr
            segments.append(SpeechSegment(
                start=speech_start,
                end=duration,
                confidence=0.5
            ))
        
        return segments
    
    def gate_subtitles(
        self,
        cues: List[SubtitleCue],
        speech_segments: List[SpeechSegment],
        audio_duration: float
    ) -> List[SubtitleCue]:
        """
        Aplica gating: remove/clamp cues para dentro dos speech segments.
        
        Args:
            audio_duration: Duração total do áudio (para clamp final)
        
        Regras:
        1. Se cue NÃO intersecta nenhum segment → DROP
        2. Se intersecta → CLAMP dentro do segment (com padding)
        3. Se duração < min_duration → ajustar
        4. Se gap entre cues < merge_gap → MERGE
        """
        gated_cues = []
        dropped_count = 0
        
        for cue in cues:
            # Encontrar speech segment que intersecta
            intersecting_segment = self._find_intersecting_segment(
                cue, speech_segments
            )
            
            if intersecting_segment is None:
                # DROP: cue fora de fala
                logger.debug(f"⚠️ DROP cue '{cue.text}' (fora de fala)")
                dropped_count += 1
                continue
            
            # ────────────────────────────────────────────────────────────
            # CLAMP: ajustar start/end para dentro do segment (com padding)
            # ────────────────────────────────────────────────────────────
            # 🔧 CORREÇÃO: RESPEITAR cue.end original (não estender demais)
            # Problema anterior: clamped_end ia até segment.end + post_pad,
            # fazendo palavras "durarem demais" e causando sobreposição
            
            # Limites permitidos pelo speech segment
            allowed_start = max(0.0, intersecting_segment.start - self.pre_pad)
            allowed_end = min(audio_duration, intersecting_segment.end + self.post_pad)
            
            # Start: limitar ao range permitido
            clamped_start = max(allowed_start, cue.start)
            
            # End: usar o MENOR entre:
            #   1. cue.end + word_post_pad (micro folga)
            #   2. allowed_end (fim do speech segment + post_pad)
            # Isso evita que palavras "se estendam" até o fim da fala
            clamped_end = min(allowed_end, cue.end + self.word_post_pad)
            
            # Garantir duração mínima
            if clamped_end - clamped_start < self.min_duration:
                clamped_end = min(allowed_end, clamped_start + self.min_duration)
            
            # Garantia final: end >= start
            if clamped_end <= clamped_start:
                clamped_end = min(allowed_end, clamped_start + self.min_duration)
            
            gated_cues.append(SubtitleCue(
                index=cue.index,
                start=clamped_start,
                end=clamped_end,
                text=cue.text
            ))
        
        # MERGE: juntar cues próximos
        merged_cues = self._merge_close_cues(gated_cues)
        
        merged_count = len(gated_cues) - len(merged_cues)
        logger.info(
            f"✅ Speech gating: {len(merged_cues)}/{len(cues)} cues finais, "
            f"{dropped_count} dropped, {merged_count} merged"
        )
        
        return merged_cues
    
    def _find_intersecting_segment(
        self,
        cue: SubtitleCue,
        segments: List[SpeechSegment]
    ) -> Optional[SpeechSegment]:
        """Encontra speech segment que intersecta o cue"""
        for segment in segments:
            if self._intervals_intersect(
                cue.start, cue.end,
                segment.start, segment.end
            ):
                return segment
        return None
    
    def _intervals_intersect(
        self,
        a_start: float, a_end: float,
        b_start: float, b_end: float
    ) -> bool:
        """Verifica se dois intervalos intersectam"""
        return not (a_end < b_start or b_end < a_start)
    
    def _merge_close_cues(self, cues: List[SubtitleCue]) -> List[SubtitleCue]:
        """Merge cues se gap < merge_gap"""
        if not cues:
            return []
        
        merged = [cues[0]]
        
        for cue in cues[1:]:
            prev = merged[-1]
            gap = cue.start - prev.end
            
            if gap < self.merge_gap:
                # MERGE: juntar com anterior
                merged[-1] = SubtitleCue(
                    index=prev.index,
                    start=prev.start,
                    end=cue.end,
                    text=f"{prev.text} {cue.text}"
                )
            else:
                merged.append(cue)
        
        return merged
    
    def validate_speech_gating(
        self,
        cues: List[SubtitleCue],
        speech_segments: List[SpeechSegment],
        vad_ok: bool
    ) -> Dict[str, any]:
        """
        Valida que cues estão alinhados com fala.
        
        Métrica: % de cues fora de fala = 0% (quando VAD OK)
        """
        if not cues:
            return {
                'total_cues': 0,
                'cues_outside_speech': 0,
                'pct_outside_speech': 0.0,
                'vad_ok': vad_ok,
                'passed': True,
                'target': '0% quando VAD OK'
            }
        
        cues_outside_speech = 0
        
        for cue in cues:
            has_speech = self._find_intersecting_segment(cue, speech_segments) is not None
            
            if not has_speech:
                cues_outside_speech += 1
                logger.warning(
                    f"⚠️ Cue fora de fala: '{cue.text}' @ {cue.start:.2f}s"
                )
        
        pct_outside = (cues_outside_speech / len(cues) * 100)
        
        # Métrica condicionada: 0% apenas quando VAD OK
        passed = (pct_outside == 0) if vad_ok else None
        
        return {
            'total_cues': len(cues),
            'cues_outside_speech': cues_outside_speech,
            'pct_outside_speech': pct_outside,
            'vad_ok': vad_ok,
            'passed': passed,  # None = não aplicável (fallback)
            'target': '0% quando VAD OK; fallback_rate < 5%'
        }


def process_subtitles_with_vad(
    audio_path: str,
    raw_cues: List[Dict]
) -> Tuple[List[Dict], bool]:
    """
    Pipeline completo: raw cues → VAD gating → cues finais.
    
    Returns:
        (gated_cues, vad_ok)
    """
    processor = SpeechGatedSubtitles(
        pre_pad=0.06,
        post_pad=0.12,
        min_duration=0.12,
        merge_gap=0.12
    )
    
    # 1. Detectar speech segments
    speech_segments, vad_ok = processor.detect_speech_segments(audio_path)
    
    if not vad_ok:
        logger.warning("⚠️ VAD fallback usado, qualidade de gating degradada")
    
    # 2. Obter duração do áudio
    if VAD_UTILS_AVAILABLE:
        audio_duration = validate_audio_format(audio_path)['duration']
    else:
        # Fallback sem vad_utils
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 
                   'format=duration', '-of', 'json', audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            data = json.loads(result.stdout)
            audio_duration = float(data['format']['duration'])
        except Exception as e:
            logger.error(f"⚠️ Erro ao obter duração do áudio: {e}")
            audio_duration = 300.0  # 5min default
    
    # 3. Converter raw cues para SubtitleCue
    cues = [
        SubtitleCue(i, c['start'], c['end'], c['text'])
        for i, c in enumerate(raw_cues)
    ]
    
    # 4. Aplicar gating
    gated_cues = processor.gate_subtitles(cues, speech_segments, audio_duration)
    
    # 5. Converter de volta para dict
    return [
        {'start': c.start, 'end': c.end, 'text': c.text}
        for c in gated_cues
    ], vad_ok
