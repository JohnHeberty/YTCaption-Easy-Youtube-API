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
        JobStatus.ANALYZING_AUDIO: 30,
        JobStatus.FETCHING_SHORTS: 60,
        JobStatus.DOWNLOADING_SHORTS: 300,
        JobStatus.SELECTING_SHORTS: 10,
        JobStatus.ASSEMBLING_VIDEO: 120,
        JobStatus.GENERATING_SUBTITLES: 180,
        JobStatus.FINAL_COMPOSITION: 300,
    }

    base = base_timeouts.get(stage, 300)

    if stage == JobStatus.ANALYZING_AUDIO:
        timeout = base + int(audio_duration * 2)
    elif stage == JobStatus.FETCHING_SHORTS:
        timeout = base + (max_shorts * 5)
    elif stage == JobStatus.DOWNLOADING_SHORTS:
        timeout = base + (max_shorts * 10)
    elif stage == JobStatus.GENERATING_SUBTITLES:
        timeout = base + int(audio_duration * 30)
    elif stage == JobStatus.FINAL_COMPOSITION:
        timeout = base + int(audio_duration * 10)
    else:
        timeout = base

    timeout = int(timeout * (1.5 ** retry_count))
    return min(timeout, 1800)
