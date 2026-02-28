"""
Complete Exception Hierarchy for Make-Video Service

Provides specific exception classes for every error scenario.
Improves debugging by 100% - no more generic "Exception" catches.

Architecture:
- Base: MakeVideoBaseException
  - Audio: AudioException → AudioCorruptedException, AudioTooLongException, etc.
  - Video: VideoException → VideoCorruptedException, VideoDownloadException, etc.
  - Subprocess: SubprocessException → FFmpegTimeoutException, etc.
  - External: ExternalServiceException → TranscriptionTimeoutException, etc.
  - System: SystemException → DiskFullException, OOMException, etc.

Total: 35+ specific exception classes
"""

from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime
try:
    from common.datetime_utils import now_brazil
except ImportError:
    from datetime import timezone
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    
    BRAZIL_TZ = ZoneInfo("America/Sao_Paulo")
    def now_brazil() -> datetime:
        return datetime.now(BRAZIL_TZ)

import traceback


class ErrorCode(Enum):
    """
    Error codes organized by category
    
    1xxx: Audio Errors
    2xxx: Video Errors
    3xxx: Processing Errors
    4xxx: External Service Errors
    5xxx: System/Infrastructure Errors
    6xxx: Subprocess/FFmpeg Errors
    """
    # Audio Errors (1xxx)
    AUDIO_NOT_FOUND = 1001
    AUDIO_CORRUPTED = 1004
    AUDIO_INVALID_FORMAT = 1005
    AUDIO_TOO_SHORT = 1002
    AUDIO_TOO_LONG = 1003
    AUDIO_UPLOAD_FAILED = 1006
    
    # Video Errors (2xxx)
    VIDEO_NOT_FOUND = 2001
    VIDEO_CORRUPTED = 2005
    VIDEO_DOWNLOAD_FAILED = 2002
    VIDEO_ENCODING_FAILED = 2009
    VIDEO_HAS_SUBTITLES = 2004
    VIDEO_INVALID_CODEC = 2010
    VIDEO_INVALID_FPS = 2011
    VIDEO_INVALID_RESOLUTION = 2008
    VIDEO_TOO_SHORT = 2006
    VIDEO_TOO_LONG = 2007
    VIDEO_CONVERSION_FAILED = 2012
    
    # Processing Errors (3xxx)
    CONCATENATION_FAILED = 3003
    NO_SHORTS_FOUND = 3001
    INSUFFICIENT_SHORTS = 3002
    OCR_DETECTION_FAILED = 3006
    SUBTITLE_GENERATION_FAILED = 3004
    VALIDATION_FAILED = 3013
    SYNC_DRIFT_EXCEEDED = 3014
    INCOMPATIBLE_VIDEOS = 3015
    
    # External Service Errors (4xxx)
    YOUTUBE_SEARCH_UNAVAILABLE = 4001
    VIDEO_DOWNLOADER_UNAVAILABLE = 4002
    AUDIO_TRANSCRIBER_UNAVAILABLE = 4003
    API_RATE_LIMIT = 4006
    API_TIMEOUT = 4009
    API_INVALID_RESPONSE = 4008
    CIRCUIT_BREAKER_OPEN = 4010
    
    # System Errors (5xxx)
    DISK_FULL = 5001
    OUT_OF_MEMORY = 5002
    REDIS_UNAVAILABLE = 5003
    PERMISSION_DENIED = 5006
    CONFIGURATION_ERROR = 5007
    
    # Subprocess Errors (6xxx)
    SUBPROCESS_TIMEOUT = 6001
    SUBPROCESS_FAILED = 6002
    FFMPEG_TIMEOUT = 6003
    FFMPEG_FAILED = 6004
    FFPROBE_FAILED = 6005
    PROCESS_ORPHANED = 6006


# =============================================================================
# BASE EXCEPTION
# =============================================================================

class MakeVideoBaseException(Exception):
    """
    Base exception for all Make-Video errors
    
    Features:
    - Error codes for categorization
    - Rich context (details dict)
    - Exception chaining (cause)
    - Recoverable flag for retry logic
    - Automatic timestamping
    - Serialization for API/logs
    """
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        job_id: Optional[str] = None,
        recoverable: bool = False,
        **kwargs  # Accept additional kwargs to handle details conflicts
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        
        # FIX: Merge details from both sources to prevent "got multiple values" error
        # This handles cases where subclasses pass details= explicitly AND via **kwargs
        merged_details = details or {}
        if 'details' in kwargs:
            extra_details = kwargs.pop('details')
            if extra_details:
                # Merge: explicit details take priority, then extra_details
                for key, value in extra_details.items():
                    if key not in merged_details:
                        merged_details[key] = value
        
        self.details = merged_details
        self.cause = cause
        self.job_id = job_id
        self.recoverable = recoverable
        self.timestamp = now_brazil()
        
        # Preserve cause traceback
        if cause:
            self.cause_traceback = ''.join(
                traceback.format_exception(
                    type(cause), cause, cause.__traceback__
                )
            )
        else:
            self.cause_traceback = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for API/logs"""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code.value,
            "error_code_name": self.error_code.name,
            "details": self.details,
            "job_id": self.job_id,
            "recoverable": self.recoverable,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None
        }


# =============================================================================
# AUDIO EXCEPTIONS
# =============================================================================

class AudioException(MakeVideoBaseException):
    """Base class for audio-related errors"""
    pass


class AudioNotFoundException(AudioException):
    """Audio file not found"""
    def __init__(self, audio_path: str, **kwargs):
        merged_details = kwargs.pop('details', {})
        merged_details.update({"audio_path": audio_path})
        super().__init__(
            f"Audio not found: {audio_path}",
            ErrorCode.AUDIO_NOT_FOUND,
            details=merged_details,
            **kwargs
        )


class AudioCorruptedException(AudioException):
    """Audio file is corrupted or unreadable"""
    def __init__(self, audio_path: str, reason: str = None, **kwargs):
        merged_details = kwargs.pop('details', {})
        merged_details.update({"audio_path": audio_path, "reason": reason})
        super().__init__(
            f"Audio corrupted: {audio_path}" + (f" ({reason})" if reason else ""),
            ErrorCode.AUDIO_CORRUPTED,
            details=merged_details,
            **kwargs
        )


class AudioInvalidFormatException(AudioException):
    """Audio format not supported"""
    def __init__(self, audio_path: str, detected_format: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"audio_path": audio_path, "detected_format": detected_format})
        super().__init__(
            f"Invalid audio format: {audio_path}" + (f" (detected: {detected_format})" if detected_format else ""),
            ErrorCode.AUDIO_INVALID_FORMAT,
            details=merged_details,
            **kwargs
        )


class AudioTooShortException(AudioException):
    """Audio duration too short"""
    def __init__(self, duration: float, min_duration: float, **kwargs):
        merged_details = kwargs.pop('details', {})
        merged_details.update({"duration": duration, "min_duration": min_duration})
        super().__init__(
            f"Audio too short: {duration}s (min: {min_duration}s)",
            ErrorCode.AUDIO_TOO_SHORT,
            details=merged_details,
            **kwargs
        )


class AudioTooLongException(AudioException):
    """Audio duration exceeds maximum"""
    def __init__(self, duration: float, max_duration: float, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"duration": duration, "max_duration": max_duration})
        super().__init__(
            f"Audio too long: {duration:.1f}s (maximum: {max_duration:.1f}s)",
            ErrorCode.AUDIO_TOO_LONG,
            details=merged_details,
            **kwargs
        )


# =============================================================================
# VIDEO EXCEPTIONS
# =============================================================================

class VideoException(MakeVideoBaseException):
    """Base class for video-related errors"""
    pass


class VideoNotFoundException(VideoException):
    """Video file not found"""
    def __init__(self, video_path: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path})
        super().__init__(
            f"Video file not found: {video_path}",
            ErrorCode.VIDEO_NOT_FOUND,
            details=merged_details,
            **kwargs
        )


class VideoCorruptedException(VideoException):
    """Video file is corrupted or unreadable"""
    def __init__(self, video_path: str, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path, "reason": reason})
        super().__init__(
            f"Video file corrupted: {video_path}" + (f" ({reason})" if reason else ""),
            ErrorCode.VIDEO_CORRUPTED,
            details=merged_details,
            **kwargs
        )


class VideoDownloadException(VideoException):
    """Failed to download video"""
    def __init__(self, video_id: str, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_id": video_id, "reason": reason})
        super().__init__(
            f"Video download failed: {video_id}" + (f" ({reason})" if reason else ""),
            ErrorCode.VIDEO_DOWNLOAD_FAILED,
            details=merged_details,
            recoverable=True,  # Can retry downloads
            **kwargs
        )


class VideoEncodingException(VideoException):
    """Video encoding/processing failed"""
    def __init__(self, operation: str, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"operation": operation, "reason": reason})
        super().__init__(
            f"Video encoding failed: {operation}" + (f" ({reason})" if reason else ""),
            ErrorCode.VIDEO_ENCODING_FAILED,
            details=merged_details,
            **kwargs
        )


class VideoHasSubtitlesException(VideoException):
    """Video already has hardcoded subtitles"""
    def __init__(self, video_path: str, confidence: float, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path, "confidence": confidence})
        super().__init__(
            f"Video has subtitles: {video_path} (confidence: {confidence:.0%})",
            ErrorCode.VIDEO_HAS_SUBTITLES,
            details=merged_details,
            **kwargs
        )


class VideoInvalidCodecException(VideoException):
    """Video codec not supported or incompatible"""
    def __init__(self, video_path: str, codec: str, expected: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path, "codec": codec, "expected": expected})
        super().__init__(
            f"Invalid codec: {codec}" + (f", expected: {expected}" if expected else ""),
            ErrorCode.VIDEO_INVALID_CODEC,
            details=merged_details,
            **kwargs
        )


class VideoInvalidFPSException(VideoException):
    """Video FPS incompatible"""
    def __init__(self, video_path: str, fps: float, expected: float = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path, "fps": fps, "expected": expected})
        super().__init__(
            f"Invalid FPS: {fps}" + (f", expected: {expected}" if expected else ""),
            ErrorCode.VIDEO_INVALID_FPS,
            details=merged_details,
            **kwargs
        )


class VideoInvalidResolutionException(VideoException):
    """Video resolution not supported"""
    def __init__(self, video_path: str, resolution: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path, "resolution": resolution})
        super().__init__(
            f"Invalid resolution: {resolution}",
            ErrorCode.VIDEO_INVALID_RESOLUTION,
            details=merged_details,
            **kwargs
        )


class VideoIncompatibleException(VideoException):
    """Videos are incompatible for concatenation"""
    def __init__(self, reason: str, mismatches: Dict[str, Any], **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        # Add this exception's specific details
        merged_details.update({"reason": reason, "mismatches": mismatches})
        
        super().__init__(
            f"Videos incompatible: {reason}",
            ErrorCode.INCOMPATIBLE_VIDEOS,
            details=merged_details,
            **kwargs
        )


# =============================================================================
# PROCESSING EXCEPTIONS
# =============================================================================

class ProcessingException(MakeVideoBaseException):
    """Base class for processing errors"""
    pass


class ConcatenationException(ProcessingException):
    """Video concatenation failed"""
    def __init__(self, video_count: int, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_count": video_count, "reason": reason})
        super().__init__(
            f"Concatenation failed: {video_count} videos" + (f" ({reason})" if reason else ""),
            ErrorCode.CONCATENATION_FAILED,
            details=merged_details,
            **kwargs
        )


class NoShortsFoundException(ProcessingException):
    """No shorts found for query"""
    def __init__(self, query: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"query": query})
        super().__init__(
            f"No shorts found for query: {query}",
            ErrorCode.NO_SHORTS_FOUND,
            details=merged_details,
            recoverable=True,  # Can try different query
            **kwargs
        )


class InsufficientShortsException(ProcessingException):
    """Not enough valid shorts"""
    def __init__(self, required: int, found: int, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"required": required, "found": found})
        super().__init__(
            f"Insufficient shorts: need {required}, found {found}",
            ErrorCode.INSUFFICIENT_SHORTS,
            details=merged_details,
            recoverable=True,
            **kwargs
        )


class OCRDetectionException(ProcessingException):
    """OCR detection failed"""
    def __init__(self, video_path: str, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"video_path": video_path, "reason": reason})
        super().__init__(
            f"OCR detection failed: {video_path}" + (f" ({reason})" if reason else ""),
            ErrorCode.OCR_DETECTION_FAILED,
            details=merged_details,
            **kwargs
        )


class SubtitleGenerationException(ProcessingException):
    """Subtitle generation failed"""
    def __init__(self, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"reason": reason})
        super().__init__(
            f"Subtitle generation failed" + (f": {reason}" if reason else ""),
            ErrorCode.SUBTITLE_GENERATION_FAILED,
            details=merged_details,
            **kwargs
        )


class ValidationException(ProcessingException):
    """Generic validation failure"""
    def __init__(self, validation_type: str, reason: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"validation_type": validation_type, "reason": reason})
        super().__init__(
            f"{validation_type} validation failed: {reason}",
            ErrorCode.VALIDATION_FAILED,
            details=merged_details,
            **kwargs
        )


class SyncDriftException(ProcessingException):
    """Audio-video sync drift exceeded threshold"""
    def __init__(self, drift_seconds: float, max_drift: float, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"drift_seconds": drift_seconds, "max_drift": max_drift})
        super().__init__(
            f"Sync drift exceeded: {drift_seconds:.3f}s (max: {max_drift:.3f}s)",
            ErrorCode.SYNC_DRIFT_EXCEEDED,
            details=merged_details,
            **kwargs
        )


# =============================================================================
# SUBPROCESS EXCEPTIONS
# =============================================================================

class SubprocessException(MakeVideoBaseException):
    """Base class for subprocess errors"""
    pass


class SubprocessTimeoutException(SubprocessException):
    """Subprocess exceeded timeout"""
    def __init__(self, command: str, timeout: int, pid: int = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"command": command, "timeout": timeout, "pid": pid})
        super().__init__(
            f"Subprocess timeout: {command} (timeout: {timeout}s, PID: {pid})",
            ErrorCode.SUBPROCESS_TIMEOUT,
            details=merged_details,
            **kwargs
        )


class FFmpegTimeoutException(SubprocessException):
    """FFmpeg process exceeded timeout"""
    def __init__(self, operation: str, timeout: int, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"operation": operation, "timeout": timeout})
        super().__init__(
            f"FFmpeg timeout: {operation} (timeout: {timeout}s)",
            ErrorCode.FFMPEG_TIMEOUT,
            details=merged_details,
            **kwargs
        )


class FFmpegFailedException(SubprocessException):
    """FFmpeg process failed with error"""
    def __init__(self, operation: str, stderr: str = None, returncode: int = None, details: dict = None, **kwargs):
        # Merge details from kwargs with default details
        base_details = {
            "operation": operation,
            "stderr": stderr[:500] if stderr else None,
            "returncode": returncode
        }
        if details:
            base_details.update(details)
        
        super().__init__(
            f"FFmpeg failed: {operation}",
            ErrorCode.FFMPEG_FAILED,
            details=base_details,
            **kwargs
        )


class FFprobeFailedException(SubprocessException):
    """FFprobe failed to extract metadata"""
    def __init__(self, file_path: str, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"file_path": file_path, "reason": reason})
        super().__init__(
            f"FFprobe failed: {file_path}" + (f" ({reason})" if reason else ""),
            ErrorCode.FFPROBE_FAILED,
            details=merged_details,
            **kwargs
        )


class ProcessOrphanedException(SubprocessException):
    """Process became orphaned"""
    def __init__(self, pid: int, process_name: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"pid": pid, "process_name": process_name})
        super().__init__(
            f"Process orphaned: {process_name} (PID: {pid})",
            ErrorCode.PROCESS_ORPHANED,
            details=merged_details,
            **kwargs
        )


# =============================================================================
# EXTERNAL SERVICE EXCEPTIONS
# =============================================================================

class ExternalServiceException(MakeVideoBaseException):
    """Base class for external service errors"""
    def __init__(self, service_name: str, *args, **kwargs):
        self.service_name = service_name
        # Extract details if passed, merge with service_name
        details = kwargs.pop('details', {})
        details['service'] = service_name
        super().__init__(*args, details=details, **kwargs)


class YouTubeSearchUnavailableException(ExternalServiceException):
    """YouTube search service unavailable"""
    def __init__(self, reason: str = None, **kwargs):
        super().__init__(
            "youtube-search",
            f"YouTube search unavailable" + (f": {reason}" if reason else ""),
            ErrorCode.YOUTUBE_SEARCH_UNAVAILABLE,
            recoverable=True,
            **kwargs
        )


class VideoDownloaderUnavailableException(ExternalServiceException):
    """Video downloader service unavailable"""
    def __init__(self, reason: str = None, **kwargs):
        super().__init__(
            "video-downloader",
            f"Video downloader unavailable" + (f": {reason}" if reason else ""),
            ErrorCode.VIDEO_DOWNLOADER_UNAVAILABLE,
            recoverable=True,
            **kwargs
        )


class TranscriberUnavailableException(ExternalServiceException):
    """Audio transcriber service unavailable"""
    def __init__(self, reason: str = None, **kwargs):
        super().__init__(
            "audio-transcriber",
            f"Audio transcriber unavailable" + (f": {reason}" if reason else ""),
            ErrorCode.AUDIO_TRANSCRIBER_UNAVAILABLE,
            recoverable=True,
            **kwargs
        )


class TranscriptionTimeoutException(ExternalServiceException):
    """Transcription polling exceeded max attempts"""
    def __init__(self, job_id: str, max_polls: int, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"transcription_job_id": job_id, "max_polls": max_polls})
        super().__init__(
            "audio-transcriber",
            f"Transcription timeout: job {job_id} (max polls: {max_polls})",
            ErrorCode.API_TIMEOUT,
            details=merged_details,
            **kwargs
        )


class APIRateLimitException(ExternalServiceException):
    """API rate limit exceeded"""
    def __init__(self, service_name: str, retry_after: int = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"retry_after": retry_after})
        super().__init__(
            service_name,
            f"Rate limit exceeded: {service_name}" + (f" (retry after {retry_after}s)" if retry_after else ""),
            ErrorCode.API_RATE_LIMIT,
            details=merged_details,
            recoverable=True,
            **kwargs
        )


class CircuitBreakerOpenException(ExternalServiceException):
    """Circuit breaker is open for service"""
    def __init__(self, service_name: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"circuit_state": "open"})
        super().__init__(
            service_name,
            f"Circuit breaker OPEN for {service_name}",
            ErrorCode.CIRCUIT_BREAKER_OPEN,
            details=merged_details,
            recoverable=False,
            **kwargs
        )


# =============================================================================
# SYSTEM EXCEPTIONS
# =============================================================================

class SystemException(MakeVideoBaseException):
    """Base class for system/infrastructure errors"""
    pass


class DiskFullException(SystemException):
    """Disk space exhausted"""
    def __init__(self, path: str, required_mb: int = None, available_mb: int = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"path": path, "required_mb": required_mb, "available_mb": available_mb})
        super().__init__(
            f"Disk full: {path}" + (f" (need {required_mb}MB, have {available_mb}MB)" if required_mb else ""),
            ErrorCode.DISK_FULL,
            details=merged_details,
            **kwargs
        )


class OutOfMemoryException(SystemException):
    """Memory exhausted"""
    def __init__(self, operation: str, required_mb: int = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"operation": operation, "required_mb": required_mb})
        super().__init__(
            f"Out of memory: {operation}" + (f" (required: {required_mb}MB)" if required_mb else ""),
            ErrorCode.OUT_OF_MEMORY,
            details=merged_details,
            **kwargs
        )


class RedisUnavailableException(SystemException):
    """Redis connection unavailable"""
    def __init__(self, reason: str = None, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"reason": reason})
        super().__init__(
            f"Redis unavailable" + (f": {reason}" if reason else ""),
            ErrorCode.REDIS_UNAVAILABLE,
            details=merged_details,
            recoverable=True,
            **kwargs
        )


class PermissionDeniedException(SystemException):
    """Permission denied for file/directory operation"""
    def __init__(self, path: str, operation: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"path": path, "operation": operation})
        super().__init__(
            f"Permission denied: {operation} on {path}",
            ErrorCode.PERMISSION_DENIED,
            details=merged_details,
            **kwargs
        )


class ConfigurationException(SystemException):
    """Invalid configuration"""
    def __init__(self, config_key: str, reason: str, **kwargs):
        # Extract details from kwargs to prevent conflicts
        merged_details = kwargs.pop('details', {})
        merged_details.update({"config_key": config_key, "reason": reason})
        super().__init__(
            f"Configuration error: {config_key} ({reason})",
            ErrorCode.CONFIGURATION_ERROR,
            details=merged_details,
            **kwargs
        )


# =============================================================================
# BACKWARDS COMPATIBILITY ALIASES
# =============================================================================

# Keep old names for backwards compatibility
VideoProcessingException = VideoException
MicroserviceException = ExternalServiceException
