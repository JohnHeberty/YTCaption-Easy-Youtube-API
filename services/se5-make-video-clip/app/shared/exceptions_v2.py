"""
Backward compatibility shim for exceptions_v2 imports.
All classes are re-exported from exceptions.py with aliases
matching the v2 naming convention.
"""
from __future__ import annotations

from .exceptions import (
    EnhancedMakeVideoException,
    AudioProcessingException,
    VideoProcessingException,
    MicroserviceException,
    SystemException,
    MakeVideoException,
    ErrorCode,
    create_audio_error,
    create_video_error,
    create_api_error,
)

MakeVideoBaseException = EnhancedMakeVideoException
AudioException = AudioProcessingException
VideoException = VideoProcessingException

class ValidationException(EnhancedMakeVideoException):
    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCode.INVALID_QUERY, **kwargs)

class VideoCorruptedException(VideoProcessingException):
    def __init__(self, message: str = "Video corrupted", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_CORRUPTED, **kwargs)

class VideoEncodingException(VideoProcessingException):
    def __init__(self, message: str = "Video encoding failed", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_ENCODING_FAILED, **kwargs)

class VideoInvalidResolutionException(VideoProcessingException):
    def __init__(self, message: str = "Invalid resolution", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_INVALID_RESOLUTION, **kwargs)

class VideoNotFoundException(VideoProcessingException):
    def __init__(self, message: str = "Video not found", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_FILE_NOT_FOUND, **kwargs)

class VideoIncompatibleException(VideoProcessingException):
    def __init__(self, message: str = "Video incompatible", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_VALIDATION_FAILED, **kwargs)

class VideoDownloadException(VideoProcessingException):
    def __init__(self, message: str = "Video download failed", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_DOWNLOAD_FAILED, **kwargs)

class ConcatenationException(VideoProcessingException):
    def __init__(self, message: str = "Concatenation failed", **kwargs):
        super().__init__(message, ErrorCode.CONCATENATION_FAILED, **kwargs)

class SubtitleGenerationException(VideoProcessingException):
    def __init__(self, message: str = "Subtitle generation failed", **kwargs):
        super().__init__(message, ErrorCode.SUBTITLE_GENERATION_FAILED, **kwargs)

class AudioNotFoundException(AudioProcessingException):
    def __init__(self, message: str = "Audio not found", **kwargs):
        super().__init__(message, ErrorCode.AUDIO_FILE_NOT_FOUND, **kwargs)

class AudioCorruptedException(AudioProcessingException):
    def __init__(self, message: str = "Audio corrupted", **kwargs):
        super().__init__(message, ErrorCode.AUDIO_CORRUPTED, **kwargs)

class FFmpegTimeoutException(SystemException):
    def __init__(self, message: str = "FFmpeg timeout", **kwargs):
        super().__init__(message, ErrorCode.TEMP_FILE_ERROR, **kwargs)

class FFmpegFailedException(SystemException):
    def __init__(self, message: str = "FFmpeg failed", **kwargs):
        super().__init__(message, ErrorCode.TEMP_FILE_ERROR, **kwargs)

class FFprobeFailedException(SystemException):
    def __init__(self, message: str = "FFprobe failed", **kwargs):
        super().__init__(message, ErrorCode.TEMP_FILE_ERROR, **kwargs)

class SubprocessTimeoutException(SystemException):
    def __init__(self, message: str = "Subprocess timeout", **kwargs):
        super().__init__(message, ErrorCode.TEMP_FILE_ERROR, **kwargs)

class RedisUnavailableException(SystemException):
    def __init__(self, message: str = "Redis unavailable", **kwargs):
        super().__init__(message, ErrorCode.REDIS_UNAVAILABLE, **kwargs)

class SyncDriftException(EnhancedMakeVideoException):
    def __init__(self, message: str = "Sync drift detected", **kwargs):
        super().__init__(message, ErrorCode.PROCESSING_FAILED, **kwargs)

class NoShortsFoundException(VideoProcessingException):
    def __init__(self, message: str = "No shorts found", **kwargs):
        super().__init__(message, ErrorCode.NO_SHORTS_FOUND, **kwargs)

class YouTubeSearchUnavailableException(MicroserviceException):
    def __init__(self, message: str = "YouTube Search unavailable", **kwargs):
        super().__init__(message, ErrorCode.YOUTUBE_SEARCH_UNAVAILABLE, service_name="se6-youtube-search", **kwargs)


class VideoDownloaderUnavailableException(MicroserviceException):
    def __init__(self, message: str = "Video downloader unavailable", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_DOWNLOADER_UNAVAILABLE, service_name="se2-video-downloader", **kwargs)


class AudioTranscriberUnavailableException(MicroserviceException):
    def __init__(self, message: str = "Audio transcriber unavailable", reason: str | None = None, **kwargs):
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message, ErrorCode.AUDIO_TRANSCRIBER_UNAVAILABLE, service_name="se4-audio-transcriber", **kwargs)

# Alias for backward compat
TranscriberUnavailableException = AudioTranscriberUnavailableException


class TranscriptionTimeoutException(MicroserviceException):
    def __init__(self, job_id: str | None = None, max_polls: int | None = None, **kwargs):
        message = f"Transcription timeout: job {job_id} (max polls: {max_polls})"
        kwargs.setdefault("recoverable", False)
        super().__init__(message, ErrorCode.API_TIMEOUT, service_name="se4-audio-transcriber", **kwargs)
        if job_id:
            self.details["transcription_job_id"] = job_id
        if max_polls:
            self.details["max_polls"] = max_polls

class APIRateLimitException(MicroserviceException):
    def __init__(self, service_name: str = "external-api", retry_after: int | None = None, **kwargs):
        message = f"Rate limit exceeded: {service_name}" + (f" (retry after {retry_after}s)" if retry_after else "")
        super().__init__(message, ErrorCode.API_RATE_LIMIT, service_name=service_name, **kwargs)
        if retry_after:
            self.details["retry_after"] = retry_after


class ExternalServiceException(EnhancedMakeVideoException):
    def __init__(self, service_name: str, message: str, error_code: ErrorCode, details: dict | None = None, **kwargs):
        merged = dict(details or {})
        merged["service"] = service_name
        super().__init__(message, error_code, details=merged, **kwargs)


class CircuitBreakerOpenException(MicroserviceException):
    def __init__(self, service_name: str, **kwargs):
        message = f"Circuit breaker OPEN for {service_name}"
        super().__init__(message, ErrorCode.CIRCUIT_BREAKER_OPEN, service_name=service_name, recoverable=False, **kwargs)
        self.details["circuit_state"] = "open"


class AudioInvalidFormatException(AudioProcessingException):
    def __init__(self, message: str = "Audio invalid format", audio_path: str | None = None, reason: str | None = None, **kwargs):
        super().__init__(message, ErrorCode.AUDIO_INVALID_FORMAT, audio_path=audio_path, **kwargs)
        if reason:
            self.details["reason"] = reason


class AudioTooShortException(AudioProcessingException):
    def __init__(self, duration: float, min_duration: float, **kwargs):
        message = f"Audio too short: {duration}s (min: {min_duration}s)"
        super().__init__(message, ErrorCode.AUDIO_TOO_SHORT, **kwargs)
        self.details["duration"] = duration
        self.details["min_duration"] = min_duration


class AudioTooLongException(AudioProcessingException):
    def __init__(self, duration: float, max_duration: float, **kwargs):
        message = f"Audio too long: {duration}s (max: {max_duration}s)"
        super().__init__(message, ErrorCode.AUDIO_TOO_LONG, **kwargs)
        self.details["duration"] = duration
        self.details["max_duration"] = max_duration


__all__ = [
    "MakeVideoBaseException",
    "AudioException",
    "VideoException",
    "ValidationException",
    "VideoCorruptedException",
    "VideoEncodingException",
    "VideoInvalidResolutionException",
    "VideoNotFoundException",
    "VideoIncompatibleException",
    "VideoDownloadException",
    "ConcatenationException",
    "SubtitleGenerationException",
    "AudioNotFoundException",
    "AudioCorruptedException",
    "FFmpegTimeoutException",
    "FFmpegFailedException",
    "FFprobeFailedException",
    "SubprocessTimeoutException",
    "RedisUnavailableException",
    "SyncDriftException",
    "NoShortsFoundException",
    "YouTubeSearchUnavailableException",
    "VideoDownloaderUnavailableException",
    "TranscriberUnavailableException",
    "TranscriptionTimeoutException",
    "APIRateLimitException",
    "ExternalServiceException",
    "CircuitBreakerOpenException",
    "AudioInvalidFormatException",
    "AudioTooShortException",
    "AudioTooLongException",
    "EnhancedMakeVideoException",
    "AudioProcessingException",
    "VideoProcessingException",
    "MicroserviceException",
    "SystemException",
    "MakeVideoException",
    "ErrorCode",
]