from __future__ import annotations

import subprocess
import json
import wave
import os
from dataclasses import dataclass

import numpy as np

from common.log_utils import get_logger

logger = get_logger(__name__)

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("⚠️ torch não disponível, VAD silero-vad desabilitado")

try:
    from app.vad_utils import (
        get_speech_timestamps,
        load_audio_torch,
        convert_to_16k_wav,
        validate_audio_format,
    )
    VAD_UTILS_AVAILABLE = True
except ImportError:
    VAD_UTILS_AVAILABLE = False
    logger.warning("⚠️ vad_utils não disponível")


@dataclass
class SpeechSegment:
    start: float
    end: float
    confidence: float


def _get_audio_duration_ffprobe(audio_path: str) -> float:
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'json', audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except Exception:
        return 300.0


def _detect_with_silero(audio_path: str, model: object, vad_threshold: float) -> list[SpeechSegment]:
    if not TORCH_AVAILABLE or not VAD_UTILS_AVAILABLE:
        logger.error("⚠️ torch ou vad_utils não disponível para silero-vad")
        return []

    wav = load_audio_torch(audio_path, sampling_rate=16000)
    speech_timestamps = get_speech_timestamps(
        wav,
        model,
        threshold=vad_threshold,
        sampling_rate=16000,
        min_speech_duration_ms=250,
        min_silence_duration_ms=100,
    )

    segments: list[SpeechSegment] = []
    for ts in speech_timestamps:
        segments.append(SpeechSegment(
            start=ts['start'] / 16000.0,
            end=ts['end'] / 16000.0,
            confidence=1.0,
        ))
    return segments


def _detect_with_webrtc(audio_path: str, webrtc_vad: object) -> list[SpeechSegment]:
    if not VAD_UTILS_AVAILABLE:
        logger.error("⚠️ vad_utils não disponível")
        return []

    wav_path = convert_to_16k_wav(audio_path)
    segments: list[SpeechSegment] = []

    try:
        with wave.open(wav_path, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            sample_rate = wf.getframerate()

            frame_duration = 30
            frame_size = int(sample_rate * frame_duration / 1000) * 2

            speech_start = None
            for i in range(0, len(frames), frame_size):
                frame = frames[i:i + frame_size]
                if len(frame) < frame_size:
                    break

                is_speech = webrtc_vad.is_speech(frame, sample_rate)
                timestamp = i / (sample_rate * 2)

                if is_speech and speech_start is None:
                    speech_start = timestamp
                elif not is_speech and speech_start is not None:
                    segments.append(SpeechSegment(
                        start=speech_start,
                        end=timestamp,
                        confidence=0.8,
                    ))
                    speech_start = None

            if speech_start is not None:
                duration = validate_audio_format(audio_path)['duration']
                segments.append(SpeechSegment(
                    start=speech_start,
                    end=duration,
                    confidence=0.8,
                ))
    finally:
        if wav_path != audio_path and os.path.exists(wav_path):
            os.remove(wav_path)

    return segments


def _detect_with_rms(audio_path: str) -> list[SpeechSegment]:
    try:
        import librosa
    except ImportError:
        logger.error("⚠️ librosa não disponível, impossível usar RMS fallback")
        if VAD_UTILS_AVAILABLE:
            duration = validate_audio_format(audio_path)['duration']
        else:
            duration = _get_audio_duration_ffprobe(audio_path)
        return [SpeechSegment(start=0.0, end=duration, confidence=0.1)]

    y, sr = librosa.load(audio_path, sr=16000)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]

    threshold = np.max(rms) * 0.1

    segments: list[SpeechSegment] = []
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
                confidence=0.5,
            ))
            in_speech = False

    if in_speech:
        duration = len(y) / sr
        segments.append(SpeechSegment(
            start=speech_start,
            end=duration,
            confidence=0.5,
        ))

    return segments
