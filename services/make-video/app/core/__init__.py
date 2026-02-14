"""
Core module - Configuration and base models

Central configuration, constants, and data models for the make-video service.
"""

from .config import get_settings
from .constants import (
    ProcessingLimits,
    TimeoutConstants,
    ValidationThresholds,
    AspectRatios,
    FFmpegPresets,
    FileExtensions,
    HttpStatusCodes,
    ErrorMessages,
    LogMessages,
    MetricNames,
    RegexPatterns,
    CacheConstants,
)
from .models import (
    Job,
    JobStatus,
    JobResult,
    ShortInfo,
)

__all__ = [
    'get_settings',
    'ProcessingLimits',
    'TimeoutConstants',
    'ValidationThresholds',
    'AspectRatios',
    'FFmpegPresets',
    'FileExtensions',
    'HttpStatusCodes',
    'ErrorMessages',
    'LogMessages',
    'MetricNames',
    'RegexPatterns',
    'CacheConstants',
    'Job',
    'JobStatus',
    'JobResult',
    'ShortInfo',
]
