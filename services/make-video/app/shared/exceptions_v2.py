"""
Backward compatibility shim for exceptions_v2 imports.
All classes are re-exported from exceptions.py with aliases
matching the v2 naming convention.
"""
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
        super().__init__(message, ErrorCode.YOUTUBE_SEARCH_UNAVAILABLE, service_name="youtube-search", **kwargs)

class VideoDownloaderUnavailableException(MicroserviceException):
    def __init__(self, message: str = "Video Downloader unavailable", **kwargs):
        super().__init__(message, ErrorCode.VIDEO_DOWNLOADER_UNAVAILABLE, service_name="video-downloader", **kwargs)

class TranscriberUnavailableException(MicroserviceException):
    def __init__(self, message: str = "Transcriber unavailable", **kwargs):
        super().__init__(message, ErrorCode.AUDIO_TRANSCRIBER_UNAVAILABLE, service_name="audio-transcriber", **kwargs)

class TranscriptionTimeoutException(MicroserviceException):
    def __init__(self, message: str = "Transcription timeout", **kwargs):
        super().__init__(message, ErrorCode.TRANSCRIBER_TIMEOUT, service_name="audio-transcriber", **kwargs)

class APIRateLimitException(MicroserviceException):
    def __init__(self, message: str = "API rate limit exceeded", **kwargs):
        super().__init__(message, ErrorCode.API_RATE_LIMIT_EXCEEDED, service_name="external-api", **kwargs)

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
    "EnhancedMakeVideoException",
    "AudioProcessingException",
    "VideoProcessingException",
    "MicroserviceException",
    "SystemException",
    "MakeVideoException",
    "ErrorCode",
]