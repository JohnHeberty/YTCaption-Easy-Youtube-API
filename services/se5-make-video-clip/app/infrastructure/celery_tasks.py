"""
Celery Tasks for Make-Video Service

Tasks de processamento assíncrono para criação de vídeos.

Refactored into focused modules:
- instances.py: Global service instances management
- base.py: Job status update utility
- checkpoint.py: Checkpoint save/load/delete
- timeout.py: Dynamic timeout calculation
- circuit_breaker.py: SimpleCircuitBreaker
- metrics.py: SimpleMetrics tracking
- signals.py: Celery signal handlers
- helpers.py: Video transform/crop/validate helper
- tasks/make_video.py: process_make_video task
- tasks/download.py: process_download_pipeline task
- tasks/cleanup.py: cleanup tasks
- tasks/recovery.py: recover_orphaned_jobs task
"""
from __future__ import annotations

# Re-export all public API for backward compatibility
from .instances import get_instances
from .base import update_job_status
from .checkpoint import (
    save_checkpoint,
    load_checkpoint,
    delete_checkpoint,
    save_stage_checkpoint,
    load_stage_checkpoint,
    delete_stage_checkpoint,
)
from .timeout import calculate_stage_timeout
from .circuit_breaker import SimpleCircuitBreaker, circuit_breakers
from .simple_metrics import SimpleMetrics, simple_metrics as _metrics
from .signals import task_failure_handler
from .helpers import transform_crop_and_validate_video
from .tasks.make_video import process_make_video
from .tasks.download import process_download_pipeline
from .tasks.cleanup import cleanup_temp_files, cleanup_old_shorts
from .tasks.recovery import recover_orphaned_jobs

__all__ = [
    "get_instances",
    "update_job_status",
    "save_checkpoint",
    "load_checkpoint",
    "delete_checkpoint",
    "save_stage_checkpoint",
    "load_stage_checkpoint",
    "delete_stage_checkpoint",
    "calculate_stage_timeout",
    "SimpleCircuitBreaker",
    "circuit_breakers",
    "SimpleMetrics",
    "_metrics",
    "task_failure_handler",
    "transform_crop_and_validate_video",
    "process_make_video",
    "process_download_pipeline",
    "cleanup_temp_files",
    "cleanup_old_shorts",
    "recover_orphaned_jobs",
]
