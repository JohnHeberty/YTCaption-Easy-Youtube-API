"""Dynamic timeout calculation for pipeline stages (Sprint-03)."""
from __future__ import annotations

from ..core.models import JobStatus
from ..core.constants import (
    STAGE_TIMEOUT_QUEUED,
    STAGE_TIMEOUT_PROCESSING,
    STAGE_TIMEOUT_DEFAULT,
    AUDIO_TIMEOUT_MULTIPLIER,
    TIMEOUT_BACKOFF_BASE,
    MAX_STAGE_TIMEOUT,
)


def calculate_stage_timeout(
    stage: JobStatus,
    audio_duration: float = 0.0,
    max_shorts: int = 10,
    retry_count: int = 0
) -> int:
    """Calculate dynamic timeout for stage."""

    base_timeouts = {
        JobStatus.QUEUED: STAGE_TIMEOUT_QUEUED,
        JobStatus.PROCESSING: STAGE_TIMEOUT_PROCESSING,
    }

    base = base_timeouts.get(stage, STAGE_TIMEOUT_DEFAULT)

    if stage == JobStatus.PROCESSING:
        timeout = base + int(audio_duration * AUDIO_TIMEOUT_MULTIPLIER)
    else:
        timeout = base

    timeout = int(timeout * (TIMEOUT_BACKOFF_BASE ** retry_count))
    return min(timeout, MAX_STAGE_TIMEOUT)
