"""
Infrastructure module - Celery, Redis, Logging, Metrics

Infrastructure components for async processing, caching, observability.
"""

from .celery_config import celery_app
from .redis_store import RedisJobStore
from .file_logger import FileLogger
from .metrics import (
    get_metrics,
    downloads_skipped_total,
    vad_segments_dropped_total,
    vad_method_used_total,
    policy_decisions_total,
    subtitles_burned_total,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from .telemetry import (
    TRSDTelemetry,
    PerformanceMetrics,
    DetectionEvent,
    DebugArtifactSaver,
)

__all__ = [
    'celery_app',
    'RedisJobStore',
    'FileLogger',
    'get_metrics',
    'increment_counter',
    'record_histogram',
    'get_tracer',
    'trace_function',
]
