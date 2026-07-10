"""Dynamic timeout calculation for pipeline stages (Sprint-03)."""
from __future__ import annotations

from ..core.models import JobStatus


def calculate_stage_timeout(
    stage: JobStatus,
    audio_duration: float = 0.0,
    max_shorts: int = 10,
    retry_count: int = 0
) -> int:
    """Calculate dynamic timeout for stage."""

    base_timeouts = {
        JobStatus.QUEUED: 10,
        JobStatus.PROCESSING: 300,
    }

    base = base_timeouts.get(stage, 300)

    if stage == JobStatus.PROCESSING:
        timeout = base + int(audio_duration * 30)
    else:
        timeout = base

    timeout = int(timeout * (1.5 ** retry_count))
    return min(timeout, 1800)
