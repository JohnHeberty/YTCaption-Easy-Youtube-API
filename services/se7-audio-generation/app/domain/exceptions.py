from __future__ import annotations

from common.exception_handlers import BaseServiceException


class AudioGenerationException(BaseServiceException):
    def __init__(self, message: str = "Audio generation error") -> None:
        super().__init__(message=message, error_code="AUDIO_GENERATION_ERROR")


class VoiceProfileError(BaseServiceException):
    def __init__(self, message: str = "Voice profile error") -> None:
        super().__init__(message=message, error_code="VOICE_PROFILE_ERROR")


class VoiceProfileNotFound(VoiceProfileError):
    def __init__(self, voice_id: str) -> None:
        super().__init__(message=f"Voice profile not found: {voice_id}")
        self.error_code = "VOICE_PROFILE_NOT_FOUND"


class InvalidVoiceSample(VoiceProfileError):
    def __init__(self, reason: str) -> None:
        super().__init__(message=f"Invalid voice sample: {reason}")
        self.error_code = "INVALID_VOICE_SAMPLE"


class TextValidationError(AudioGenerationException):
    def __init__(self, message: str = "Invalid text") -> None:
        super().__init__(message=message)
        self.error_code = "TEXT_VALIDATION_ERROR"


class ModelNotAvailable(AudioGenerationException):
    def __init__(self, device: str = "unknown") -> None:
        super().__init__(message=f"TTS model not available on device: {device}")
        self.error_code = "MODEL_NOT_AVAILABLE"


class ResourceExhausted(AudioGenerationException):
    def __init__(self, message: str = "Resource exhausted") -> None:
        super().__init__(message=message)
        self.error_code = "RESOURCE_EXHAUSTED"


class GenerationTimeout(AudioGenerationException):
    def __init__(self, timeout_seconds: int) -> None:
        super().__init__(message=f"Generation timed out after {timeout_seconds}s")
        self.error_code = "GENERATION_TIMEOUT"
