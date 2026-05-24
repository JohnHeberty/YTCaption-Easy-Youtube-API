"""Business logic services - transcription engines and processors."""

from .processor import TranscriptionProcessor
from .faster_whisper_manager import FasterWhisperModelManager

# ModelManager e DeviceManager removidos temporariamente (requerem dependências opcionais)

__all__ = [
    "TranscriptionProcessor",
    "FasterWhisperModelManager",
]
