from __future__ import annotations

import os
from typing import Any

from app.services.vad_detectors import (
    SpeechSegment,
    TORCH_AVAILABLE,
    VAD_UTILS_AVAILABLE,
    _detect_with_silero,
    _detect_with_webrtc,
    _detect_with_rms,
    _get_audio_duration_ffprobe,
)
from app.services.subtitle_gating import (
    SubtitleCue,
    gate_subtitles,
    validate_speech_gating,
)
from common.log_utils import get_logger

logger = get_logger(__name__)


class SpeechGatedSubtitles:
    def __init__(
        self,
        pre_pad: float = 0.06,
        post_pad: float = 0.12,
        word_post_pad: float = 0.03,
        min_duration: float = 0.12,
        merge_gap: float = 0.12,
        vad_threshold: float = 0.5,
        model_path: str = '/app/models/silero_vad.jit',
    ) -> None:
        self.pre_pad = pre_pad
        self.post_pad = post_pad
        self.word_post_pad = word_post_pad
        self.min_duration = min_duration
        self.merge_gap = merge_gap
        self.vad_threshold = vad_threshold
        self.model_path = model_path

        self.model = None
        self.vad_available = False
        self.webrtc_vad = None
        self._load_vad_model()

    def _load_vad_model(self) -> None:
        if not TORCH_AVAILABLE:
            logger.warning("⚠️ torch não disponível, pulando silero-vad")
            self._load_fallback_vad()
            return

        try:
            if os.path.exists(self.model_path):
                import torch
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

    def _load_fallback_vad(self) -> None:
        try:
            import webrtcvad
            self.webrtc_vad = webrtcvad.Vad(2)
            logger.info("✅ Usando webrtcvad (fallback)")
            return
        except ImportError:
            logger.warning("⚠️ webrtcvad não disponível")

        logger.warning("⚠️ VAD total fallback: usando RMS simples")

    def detect_speech_segments(
        self,
        audio_path: str,
    ) -> tuple[list[SpeechSegment], bool]:
        if self.model is not None:
            segments = _detect_with_silero(audio_path, self.model, self.vad_threshold)
            logger.info(f"🎙️ Detectados {len(segments)} segmentos de fala (silero)")
            return segments, True

        elif self.webrtc_vad is not None:
            logger.info("🔄 Usando webrtcvad (fallback)")
            segments = _detect_with_webrtc(audio_path, self.webrtc_vad)
            return segments, False

        else:
            logger.warning("⚠️ VAD total fallback: usando RMS simples")
            segments = _detect_with_rms(audio_path)
            return segments, False

    def gate_subtitles(
        self,
        cues: list[SubtitleCue],
        speech_segments: list[SpeechSegment],
        audio_duration: float,
    ) -> list[SubtitleCue]:
        return gate_subtitles(
            cues, speech_segments, audio_duration,
            self.pre_pad, self.post_pad, self.word_post_pad,
            self.min_duration, self.merge_gap,
        )

    def validate_speech_gating(
        self,
        cues: list[SubtitleCue],
        speech_segments: list[SpeechSegment],
        vad_ok: bool,
    ) -> dict[str, Any]:
        return validate_speech_gating(cues, speech_segments, vad_ok)


def process_subtitles_with_vad(
    audio_path: str,
    raw_cues: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    processor = SpeechGatedSubtitles(
        pre_pad=0.06,
        post_pad=0.12,
        min_duration=0.12,
        merge_gap=0.12,
    )

    speech_segments, vad_ok = processor.detect_speech_segments(audio_path)

    if not vad_ok:
        logger.warning("⚠️ VAD fallback usado, qualidade de gating degradada")

    if not vad_ok and len(speech_segments) == 0:
        logger.warning(
            "⚠️ VAD fallback não detectou fala! "
            "Retornando raw_cues SEM gating (bypass)"
        )
        return raw_cues, False

    if not vad_ok and len(speech_segments) > 0:
        audio_dur = _get_audio_duration_ffprobe(audio_path)
        speech_dur = sum(seg.end - seg.start for seg in speech_segments)
        speech_ratio = speech_dur / audio_dur

        if speech_ratio < 0.1:
            logger.warning(
                f"⚠️ VAD fallback detectou apenas {speech_ratio * 100:.1f}% de fala! "
                f"Usando áudio completo como segment (bypass)"
            )
            speech_segments = [SpeechSegment(start=0.0, end=audio_dur, confidence=0.1)]

    if VAD_UTILS_AVAILABLE:
        from app.vad_utils import validate_audio_format
        audio_duration = validate_audio_format(audio_path)['duration']
    else:
        audio_duration = _get_audio_duration_ffprobe(audio_path)

    cues = [
        SubtitleCue(i, c['start'], c['end'], c['text'])
        for i, c in enumerate(raw_cues)
    ]

    gated_cues = processor.gate_subtitles(cues, speech_segments, audio_duration)

    return [
        {'start': c.start, 'end': c.end, 'text': c.text}
        for c in gated_cues
    ], vad_ok
