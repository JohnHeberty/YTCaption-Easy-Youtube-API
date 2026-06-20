from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np

from common.log_utils import get_logger

from app.core.constants import SUPPORTED_AUDIO_EXTENSIONS, VOICE_SAMPLE_RATE_TARGET
from app.domain.exceptions import InvalidVoiceSample

INT16_MAX = 32767

logger = get_logger(__name__)


def validate_voice_sample(file_path: str, min_duration: float = 5.0,
                          max_duration: float = 15.0, max_size_mb: int = 10) -> dict[str, Any]:
    path = Path(file_path)
    if not path.exists():
        raise InvalidVoiceSample("File not found")

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise InvalidVoiceSample(
            f"File too large: {size_mb:.1f}MB (max {max_size_mb}MB)"
        )

    ext = path.suffix.lower()
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise InvalidVoiceSample(f"Unsupported format: {ext}")

    try:
        import soundfile as sf
        info = sf.info(str(path))
        duration = info.duration
        sample_rate = info.samplerate
        channels = info.channels
    except Exception:
        try:
            import librosa
            y, sr = librosa.load(str(path), sr=None, mono=False)
            if y.ndim == 1:
                channels = 1
            else:
                channels = y.shape[0]
            duration = y.shape[-1] / sr
            sample_rate = sr
        except Exception as e:
            raise InvalidVoiceSample(f"Cannot read audio file: {e}")

    if duration < min_duration:
        raise InvalidVoiceSample(
            f"Audio too short: {duration:.1f}s (min {min_duration}s)"
        )
    if duration > max_duration:
        raise InvalidVoiceSample(
            f"Audio too long: {duration:.1f}s (max {max_duration}s)"
        )

    return {
        "duration_seconds": duration,
        "sample_rate": sample_rate,
        "channels": channels,
        "size_mb": round(size_mb, 2),
    }


def convert_to_mono_wav(input_path: str, output_path: str,
                        target_sr: int = VOICE_SAMPLE_RATE_TARGET) -> str:
    import soundfile as sf
    import librosa

    y, sr = librosa.load(input_path, sr=target_sr, mono=True)
    sf.write(output_path, y, target_sr)
    logger.info(f"Converted {input_path} -> {output_path} ({target_sr}Hz, mono)")
    return output_path


def chunk_text(text: str, chunk_size: int = 1000) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    for para in paragraphs:
        if len(para) <= chunk_size:
            chunks.append(para)
        else:
            sentences = para.replace("! ", "!||").replace("? ", "?||").replace(". ", ".||").split("||")
            current = ""
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                if len(current) + len(sentence) + 1 <= chunk_size:
                    current = (current + " " + sentence).strip()
                else:
                    if current:
                        chunks.append(current)
                    if len(sentence) <= chunk_size:
                        current = sentence
                    else:
                        for i in range(0, len(sentence), chunk_size):
                            chunks.append(sentence[i:i + chunk_size])
                        current = ""
            if current:
                chunks.append(current)
    return chunks


def _waveform_to_audiosegment(wav: Any, sample_rate: int) -> Any:
    import tempfile
    import torch
    from pydub import AudioSegment

    if isinstance(wav, torch.Tensor):
        wav = wav.cpu().numpy()
    if isinstance(wav, np.ndarray):
        if wav.ndim > 1:
            wav = wav.squeeze()
        wav = np.clip(wav, -1.0, 1.0)
        wav_int16 = (wav * INT16_MAX).astype(np.int16)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            import soundfile as sf
            sf.write(tmp.name, wav_int16, sample_rate)
            segment = AudioSegment.from_wav(tmp.name)
        finally:
            os.unlink(tmp.name)
    else:
        segment = wav
    return segment


def assemble_audio(wave_arrays: list[Any], sample_rate: int,
                   silence_between_paras_ms: int = 0) -> bytes:
    from io import BytesIO
    from pydub import AudioSegment

    if not wave_arrays:
        return b""

    combined: Any = None
    silence = AudioSegment.silent(duration=silence_between_paras_ms)

    for wav in wave_arrays:
        segment = _waveform_to_audiosegment(wav, sample_rate)
        if combined is None:
            combined = segment
        else:
            combined += silence + segment

    if combined is None:
        return b""

    buf = BytesIO()
    combined.export(buf, format="wav")
    buf.seek(0)
    return buf.read()
