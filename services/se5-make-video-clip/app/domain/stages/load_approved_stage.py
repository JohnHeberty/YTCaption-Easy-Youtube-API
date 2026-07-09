"""
LoadApprovedVideosStage - Load pre-approved videos from disk

Replaces FetchShortsStage + DownloadShortsStage for the legacy workflow.
Reads video files from data/approved/videos/ and loads metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..job_stage import JobStage, StageContext
from ...shared.exceptions import VideoProcessingException, ErrorCode
from common.log_utils import get_logger

logger = get_logger(__name__)

CONCAT_TOLERANCE = 2.0


class LoadApprovedVideosStage(JobStage):
    """Stage 2-3 combined: Load approved videos from disk."""

    def __init__(self, video_builder) -> None:
        super().__init__(
            name="load_approved",
            progress_start=15.0,
            progress_end=30.0,
        )
        self.video_builder = video_builder

    def validate(self, context: StageContext) -> None:
        approved_dir = Path(context.settings.get('approved_dir', './data/approved/videos'))
        if not approved_dir.exists():
            raise VideoProcessingException(
                "No approved videos folder found. Run /download first.",
                error_code=ErrorCode.NO_SHORTS_FOUND,
                job_id=context.job_id,
            )
        files = list(approved_dir.glob("*.mp4"))
        if not files:
            raise VideoProcessingException(
                "No approved videos available. Run /download first.",
                error_code=ErrorCode.NO_SHORTS_FOUND,
                job_id=context.job_id,
            )

    async def execute(self, context: StageContext) -> dict[str, Any]:
        approved_dir = Path(context.settings.get('approved_dir', './data/approved/videos'))
        approved_files = list(approved_dir.glob("*.mp4"))

        logger.info(
            "Found %d approved videos in %s", len(approved_files), approved_dir
        )

        loaded: list[dict[str, Any]] = []
        for video_file in approved_files:
            video_id = video_file.stem
            try:
                info = await self.video_builder.get_video_info(str(video_file))
                loaded.append({
                    'video_id': video_id,
                    'duration_seconds': info['duration'],
                    'file_path': str(video_file),
                    'resolution': info.get('resolution', '1080x1920'),
                    'fps': int(info.get('fps', 30)),
                    'title': f'Approved short: {video_id}',
                })
            except Exception as exc:
                logger.warning("Error reading video %s: %s", video_id, exc)
                continue

        if not loaded:
            raise VideoProcessingException(
                "No approved videos could be loaded",
                error_code=ErrorCode.NO_VALID_SHORTS,
                job_id=context.job_id,
            )

        logger.info("Loaded %d approved videos", len(loaded))
        context.downloaded_shorts = loaded
        return {
            'downloaded_count': len(loaded),
            'approved_dir': str(approved_dir),
        }
