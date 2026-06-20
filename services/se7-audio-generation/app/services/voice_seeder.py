from __future__ import annotations

"""Seed built-in voice profiles on first startup."""
from pathlib import Path
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)

BUILTIN_VOICES: list[dict[str, str]] = [
    {
        "id": "builtin_feminino",
        "name": "Feminino (Padrão)",
        "description": "Voz feminina brasileira padrão do Chatterbox",
        "filename": "builtin_feminino.wav",
    },
    {
        "id": "builtin_masculino",
        "name": "Masculino",
        "description": "Voz masculina brasileira",
        "filename": "builtin_masculino.wav",
    },
]

MAX_DURATION = 12.0


def _trim_audio(src: Path, dst: Path, max_dur: float = MAX_DURATION) -> None:
    """Trim audio to max_dur seconds and convert to mono 24kHz WAV."""
    import soundfile as sf
    import numpy as np

    y, sr = sf.read(str(src))
    if y.ndim > 1:
        y = y.mean(axis=1)

    max_samples = int(max_dur * sr)
    if len(y) > max_samples:
        y = y[:max_samples]

    sf.write(str(dst), y, sr)


def seed_builtin_voices(voice_manager: Any, voices_dir: str) -> None:
    """Register built-in voice profiles if they don't already exist."""
    from app.services.audio_utils import validate_voice_sample, convert_to_mono_wav
    from app.domain.models import VoiceProfile

    voices_path = Path(voices_dir)
    builtin_dir = voices_path / "_builtin"
    existing = {p.id for p in voice_manager.list_profiles()}

    for voice in BUILTIN_VOICES:
        if voice["id"] in existing:
            logger.debug(f"Builtin voice '{voice['id']}' already exists, skipping")
            continue

        src_path = builtin_dir / voice["filename"]
        if not src_path.exists():
            logger.warning(f"Builtin voice file not found: {src_path}")
            continue

        try:
            final_path = voices_path / f"{voice['id']}.wav"

            trimmed_path = voices_path / f"_trim_{voice['id']}.wav"
            _trim_audio(src_path, trimmed_path)

            convert_to_mono_wav(str(trimmed_path), str(final_path), target_sr=24000)
            trimmed_path.unlink(missing_ok=True)

            info = validate_voice_sample(str(final_path))

            profile = VoiceProfile(
                id=voice["id"],
                name=voice["name"],
                description=voice["description"],
                audio_path=str(final_path),
                duration_seconds=info["duration_seconds"],
                sample_rate=24000,
                status="active",
            )
            voice_manager._store.save_profile(profile)
            logger.info(f"Seeded builtin voice: {voice['id']} ({voice['name']})")
        except Exception as e:
            logger.error(f"Failed to seed builtin voice '{voice['id']}': {e}")
