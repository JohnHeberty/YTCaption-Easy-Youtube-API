"""
ValidateAVSyncStage - Validate audio/video synchronization (non-critical)

Ports _validate_av_sync() from legacy make_video.py.
"""

from __future__ import annotations

from typing import Any

from ..job_stage import JobStage, StageContext
from common.log_utils import get_logger

logger = get_logger(__name__)


class ValidateAVSyncStage(JobStage):
    """Stage 8.5: Validate A/V sync (non-critical)."""

    def __init__(self, video_builder) -> None:
        super().__init__(
            name="validate_av_sync",
            progress_start=96.0,
            progress_end=98.0,
        )
        self.video_builder = video_builder

    def validate(self, context: StageContext) -> None:
        if not context.final_video_path or not context.final_video_path.exists():
            pass  # non-critical, skip if missing

    async def execute(self, context: StageContext) -> dict[str, Any]:
        if not context.audio_path or not context.final_video_path:
            return {'skipped': True, 'reason': 'missing files'}

        try:
            from ...services.sync_validator import SyncValidator
            sync_validator = SyncValidator(tolerance_seconds=0.5)

            is_valid, drift, sync_metadata = await sync_validator.validate_sync(
                video_path=str(context.final_video_path),
                audio_path=str(context.audio_path),
                video_builder=self.video_builder,
                job_id=context.job_id,
            )
            logger.info(
                "A/V sync validated: drift=%.3fs (%.2f%%)",
                drift,
                sync_metadata.get('drift_percentage', 0),
            )
            return {
                'is_valid': is_valid,
                'drift': drift,
                'drift_percentage': sync_metadata.get('drift_percentage', 0),
            }
        except Exception as exc:
            logger.warning("A/V sync validation failed (non-critical): %s", exc)
            return {'skipped': True, 'reason': str(exc)}
