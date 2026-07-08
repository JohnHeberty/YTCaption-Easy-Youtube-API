"""
Video Validator — OCR detection, approval, rejection, and validation state management.

Uses SubtitleDetectorV2 for text detection and VideoStatusStore for
approved/rejected tracking. Manages the validate/ directory lifecycle.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from app.pipeline.cleanup import PipelineCleanup

logger = get_logger(__name__)


class VideoValidator:
    """Validate videos via OCR, then approve or reject them."""

    def __init__(
        self,
        detector: Any,
        status_store: Any,
        cleanup: PipelineCleanup,
    ) -> None:
        self._detector = detector
        self._status_store = status_store
        self._cleanup = cleanup

    def move_to_validation(self, video_id: str, transform_path: str, job_id: str) -> str:
        """
        Move transformed video to validation folder with processing tag.

        Args:
            video_id: Video identifier.
            transform_path: Path to the transformed video.
            job_id: Job ID for tracking.

        Returns:
            Path to the tagged validation file.
        """
        transform_file = Path(transform_path)
        if not transform_file.exists():
            raise FileNotFoundError(f"Transform file not found: {transform_path}")

        validate_dir = Path("data/validate/in_progress")
        validate_dir.mkdir(parents=True, exist_ok=True)

        tagged_filename = f"{job_id}_{video_id}_PROCESSING_.mp4"
        tagged_path = validate_dir / tagged_filename

        logger.info("Moving to validation: %s", video_id)
        logger.debug("  From: %s", transform_path)
        logger.debug("  To: %s", tagged_path)

        transform_file.rename(tagged_path)

        logger.info("Processing tag added: %s", tagged_filename)
        return str(tagged_path)

    def finalize_validation(
        self,
        tagged_path: str,
        video_id: str,
        approved: bool,
        job_id: str | None = None,
    ) -> str | None:
        """
        Finalize validation: remove tag and move/delete based on result.

        Args:
            tagged_path: Path with _PROCESSING_ tag.
            video_id: Video identifier.
            approved: If True, move to approved; if False, delete all.
            job_id: Job ID for complete cleanup.

        Returns:
            Final path if approved, None if rejected.
        """
        tagged_file = Path(tagged_path)
        if not tagged_file.exists():
            logger.warning("Tagged file not found: %s", tagged_path)
            return None

        try:
            if approved:
                approved_dir = Path("data/approved/videos")
                approved_dir.mkdir(parents=True, exist_ok=True)
                final_path = approved_dir / f"{video_id}.mp4"

                logger.info("Validation complete, moving to approved: %s", video_id)
                tagged_file.rename(final_path)
                logger.info("  Approved: %s", final_path)

                try:
                    shorts_path = Path(self._cleanup._settings['shorts_cache_dir']) / f"{video_id}.mp4"
                    if shorts_path.exists():
                        shorts_path.unlink()
                        logger.debug("  Cleaned shorts: %s", video_id)

                    transform_dir = Path(self._cleanup._settings['transform_dir'])
                    for file_path in transform_dir.glob(f"{video_id}*.mp4"):
                        file_path.unlink()
                        logger.debug("  Cleaned transform: %s", file_path.name)
                except Exception as e:
                    logger.warning("Cleanup warning for approved video: %s", e)

                return str(final_path)
            else:
                logger.info("Validation failed, cleaning all files: %s", video_id)
                tagged_file.unlink()
                logger.info("  Rejected video deleted: %s", tagged_path)

                self._cleanup.cleanup_rejected_video(video_id, job_id)
                return None

        except Exception as e:
            logger.error("Error finalizing validation: %s", e, exc_info=True)
            try:
                if tagged_file.exists():
                    tagged_file.unlink()
                    logger.info("  Cleanup: removed %s", tagged_path)
                self._cleanup.cleanup_rejected_video(video_id, job_id)
            except Exception:
                pass
            return None

    async def validate_video(
        self,
        video_id: str,
        validation_path: str,
        aspect_ratio: str = "9:16",
        crop_position: str = "center",
    ) -> tuple[bool, dict[str, Any]]:
        """
        Run OCR text detection on video frames.

        Args:
            video_id: Video identifier.
            validation_path: Path to the video in validate/in_progress/.
            aspect_ratio: Aspect ratio (informational).
            crop_position: Crop position (informational).

        Returns:
            Tuple of (approved, metadata). approved=True means NO text found.
        """
        logger.info("VALIDATE: Detecting text in %s (OCR 100%% frames)", video_id)

        try:
            has_text, confidence, sample_text, metadata = self._detector.detect(validation_path)

            frames_processed = metadata.get('frames_processed', 0)
            if frames_processed == 0:
                logger.error("ZERO FRAMES PROCESSED: %s - corrupt or unreadible video", video_id)
                return False, {
                    'video_id': video_id,
                    'error': 'zero_frames_processed',
                    'frames_processed': 0,
                    'reason': 'Vídeo corrompido ou ilegível - nenhum frame pôde ser processado',
                }

            aprovado = not has_text

            result_meta = {
                'video_id': video_id,
                'has_text': has_text,
                'confidence': confidence,
                'sample_text': sample_text,
                'frames_processed': metadata.get('frames_processed', 0),
                'frames_with_text': metadata.get('frames_with_text', 0),
                'detection_ratio': metadata.get('detection_ratio', 0.0),
                'aspect_ratio': aspect_ratio,
                'crop_position': crop_position,
                'validated_at': now_brazil().isoformat(),
            }

            if aprovado:
                logger.info("  APPROVED: %s (NO subtitles, conf: %.2f)", video_id, confidence)
            else:
                logger.info("  REJECTED: %s (HAS subtitles, conf: %.2f)", video_id, confidence)
                logger.info("    Detected text: '%s'", sample_text[:100])

            return aprovado, result_meta

        except Exception as e:
            logger.error("Error during validation: %s", e, exc_info=True)
            return False, {'error': str(e), 'video_id': video_id}

    async def approve_video(
        self, video_id: str, transform_path: str, metadata: dict[str, Any],
    ) -> str | None:
        """
        Approve a video: move to approved/ and register in DB.

        Returns:
            Path to the approved video, or None on failure.
        """
        logger.info("APPROVE: Moving %s to approved/", video_id)

        try:
            transform_video = Path(transform_path)
            approved_path = Path(f"data/approved/videos/{video_id}.mp4")

            if transform_video.exists():
                transform_video.rename(approved_path)
                logger.info("  Moved: %s", approved_path)

            self._status_store.add_approved(
                video_id=video_id,
                title=metadata.get('title'),
                url=f"https://www.youtube.com/watch?v={video_id}",
                file_path=str(approved_path),
                metadata=metadata,
            )

            self._cleanup.cleanup_previous_stages(video_id)

            return str(approved_path)

        except Exception as e:
            logger.error("Error approving video: %s", e, exc_info=True)
            return None

    async def reject_video(self, video_id: str, metadata: dict[str, Any]) -> None:
        """Reject a video: add to blacklist and clean all stages."""
        logger.info("REJECT: Adding %s to rejected list", video_id)

        try:
            confidence = metadata.get('confidence', 0.0)
            reason = "embedded_subtitles"
            self._status_store.add_rejected(
                video_id=video_id,
                reason=reason,
                confidence=confidence,
                title=metadata.get('title'),
                url=f"https://www.youtube.com/watch?v={video_id}",
                metadata=metadata,
            )

            logger.info("  Rejected: %s (%s, conf: %.2f)", video_id, reason, confidence)

            self._cleanup.cleanup_all_stages(video_id)

        except Exception as e:
            logger.error("Error rejecting video: %s", e, exc_info=True)
