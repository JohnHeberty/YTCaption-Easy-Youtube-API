"""
Pipeline Service — Thin orchestrator for Download → Transform → Crop → Validate → Approve.

Delegates to focused modules:
- PipelineCleanup: filesystem cleanup across stages
- ShortsDownloader: search + blacklist filter + download via SE6/SE2
- VideoProcessor: FFmpeg H264 transform + aspect-ratio crop
- VideoValidator: OCR detection, approval, rejection
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from app.core.config import get_settings
from app.video_processing.subtitle_detector_v2 import SubtitleDetectorV2
from app.services.video_status_factory import get_video_status_store
from app.services.video_builder import VideoBuilder
from app.pipeline.cleanup import PipelineCleanup
from app.pipeline.downloader import ShortsDownloader
from app.pipeline.video_processor import VideoProcessor
from app.pipeline.validator import VideoValidator

logger = get_logger(__name__)
settings = get_settings()


class VideoPipeline:
    """
    Complete pipeline for processing videos.

    Flow:
    1. Download → data/raw/shorts/
    2. Transform → data/transform/videos/ (H264)
    3. Crop → data/transform/videos/ (9:16 permanent)
    4. Validate → data/validate/ (OCR text detection)
    5. Approve/Reject → data/approved/ or blacklist + cleanup
    """

    def __init__(self) -> None:
        self.detector = SubtitleDetectorV2(show_log=True)
        self.status_store = get_video_status_store()
        self.video_builder = VideoBuilder(output_dir="data/approved/output")
        self.settings = settings

        self._cleanup = PipelineCleanup(settings)
        self._downloader = ShortsDownloader(settings, self.status_store)
        self._processor = VideoProcessor(self.video_builder)
        self._validator = VideoValidator(self.detector, self.status_store, self._cleanup)

        self._cleanup.ensure_directories()

    # ── Public interface (preserved for backward compatibility) ──────────

    def move_to_validation(self, video_id: str, transform_path: str, job_id: str) -> str:
        return self._validator.move_to_validation(video_id, transform_path, job_id)

    def finalize_validation(
        self, tagged_path: str, video_id: str, approved: bool, job_id: str | None = None,
    ) -> str | None:
        return self._validator.finalize_validation(tagged_path, video_id, approved, job_id)

    def cleanup_stale_validations(self, job_id: str, max_age_minutes: int = 30) -> None:
        self._cleanup.cleanup_stale_validations(job_id, max_age_minutes)

    def cleanup_rejected_video(self, video_id: str, job_id: str | None = None) -> None:
        self._cleanup.cleanup_rejected_video(video_id, job_id)

    def cleanup_orphaned_files(self, max_age_minutes: int = 30) -> None:
        self._cleanup.cleanup_orphaned_files(max_age_minutes)

    def cleanup_job_files(self, job_id: str) -> None:
        self._cleanup.cleanup_job_files(job_id)

    async def download_shorts(
        self, query: str, max_count: int = 50, progress_callback: Any = None,
    ) -> list[dict[str, Any]]:
        return await self._downloader.download_shorts(query, max_count, progress_callback)

    def transform_video(self, video_id: str, raw_path: str) -> str | None:
        return self._processor.transform_video(video_id, raw_path)

    async def crop_video_permanent(
        self, video_id: str, transform_path: str, aspect_ratio: str = "9:16",
        crop_position: str = "center",
    ) -> str | None:
        return await self._processor.crop_video_permanent(video_id, transform_path, aspect_ratio, crop_position)

    async def validate_video(
        self, video_id: str, validation_path: str, aspect_ratio: str = "9:16",
        crop_position: str = "center",
    ) -> tuple[bool, dict[str, Any]]:
        return await self._validator.validate_video(video_id, validation_path, aspect_ratio, crop_position)

    async def approve_video(
        self, video_id: str, transform_path: str, metadata: dict[str, Any],
    ) -> str | None:
        return await self._validator.approve_video(video_id, transform_path, metadata)

    async def reject_video(self, video_id: str, metadata: dict[str, Any]) -> None:
        await self._validator.reject_video(video_id, metadata)

    async def _cleanup_previous_stages(self, video_id: str) -> None:
        self._cleanup.cleanup_previous_stages(video_id)

    async def _cleanup_all_stages(self, video_id: str) -> None:
        self._cleanup.cleanup_all_stages(video_id)

    # ── Orchestrator ─────────────────────────────────────────────────────

    async def _report_progress(self, progress_callback: Any, progress: float, stats: dict[str, Any], total: int) -> None:
        """Report processing progress to callback."""
        if not progress_callback:
            return
        try:
            processed = stats['approved'] + stats['rejected']
            progress_pct = 50 + (processed / total * 50) if total > 0 else 50.0
            await progress_callback(
                progress=progress_pct,
                metadata={
                    'step': 'processing_videos',
                    'processed': processed,
                    'total': total,
                    'approved': stats['approved'],
                    'rejected': stats['rejected'],
                },
            )
        except Exception as e:
            logger.warning("Callback error: %s", e)

    async def process_pipeline(
        self, query: str, max_shorts: int = 50, progress_callback: Any = None,
    ) -> dict[str, Any]:
        """
        Full pipeline: Download → Transform → Crop → Validate → Approve/Reject.

        Returns:
            Pipeline statistics.
        """
        logger.info("PIPELINE STARTED: '%s' (max: %s)", query, max_shorts)

        stats: dict[str, Any] = {
            'query': query,
            'downloaded': 0,
            'transformed': 0,
            'approved': 0,
            'rejected': 0,
            'errors': 0,
            'start_time': now_brazil().isoformat(),
        }

        # 1. DOWNLOAD (10-50%)
        shorts = await self.download_shorts(query, max_shorts, progress_callback=progress_callback)
        stats['downloaded'] = len(shorts)

        if progress_callback:
            try:
                await progress_callback(progress=50.0, metadata={'step': 'download_completed', 'downloaded': len(shorts)})
            except Exception as e:
                logger.warning("Callback error: %s", e)

        if not shorts:
            logger.warning("No shorts downloaded. Pipeline finished.")
            stats['end_time'] = now_brazil().isoformat()
            return stats

        # 2-4. TRANSFORM → CROP → VALIDATE → APPROVE/REJECT
        processed_video_ids: set[str] = set()

        for short in shorts:
            video_id = short['video_id']
            raw_path = short['raw_path']

            if video_id in processed_video_ids:
                logger.info("  DUPLICATE in final pipeline (skip): %s", video_id)
                continue
            processed_video_ids.add(video_id)

            try:
                # 2. Transform (H264)
                transform_path = self.transform_video(video_id, raw_path)
                if not transform_path:
                    stats['errors'] += 1
                    await self._cleanup_all_stages(video_id)
                    continue
                stats['transformed'] += 1

                # 2.5. Crop permanent (9:16)
                cropped_path = await self.crop_video_permanent(
                    video_id=video_id, transform_path=transform_path,
                    aspect_ratio="9:16", crop_position="center",
                )
                if not cropped_path:
                    logger.error("  Permanent crop failed: %s", video_id)
                    stats['errors'] += 1
                    await self._cleanup_all_stages(video_id)
                    continue

                # 3. Validate (on already-cropped video)
                aprovado, metadata = await self.validate_video(video_id, cropped_path)

                # 4. Approve or Reject
                if aprovado:
                    await self.approve_video(video_id, cropped_path, metadata)
                    stats['approved'] += 1
                else:
                    await self.reject_video(video_id, metadata)
                    stats['rejected'] += 1

                await self._report_progress(progress_callback, 0, stats, len(shorts))

            except Exception as e:
                logger.error("Error processing %s: %s", video_id, e, exc_info=True)
                stats['errors'] += 1
                await self._cleanup_all_stages(video_id)
                continue

        stats['end_time'] = now_brazil().isoformat()

        logger.info("PIPELINE COMPLETE:")
        logger.info("  Downloaded: %d", stats['downloaded'])
        logger.info("  Transformed: %d", stats['transformed'])
        logger.info("  Approved: %d", stats['approved'])
        logger.info("  Rejected: %d", stats['rejected'])
        logger.info("  Errors: %d", stats['errors'])

        return stats
