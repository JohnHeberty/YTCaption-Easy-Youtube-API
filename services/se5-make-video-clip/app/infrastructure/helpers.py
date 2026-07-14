"""Video transform/crop/validate helper."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)


async def _transform_to_h264(
    video_id: str,
    raw_video_path: str,
    video_builder: Any,
    job_logger: Any,
) -> Path | None:
    """Convert raw video to H264. Returns transform path or None on failure."""
    job_logger.info(f"   🔄 [1/5] Transforming to H264: {video_id}")
    logger.info(f"🔄 Transforming {video_id} to H264...")

    raw_path = Path(raw_video_path)
    transform_dir = Path("data/transform/videos")
    transform_dir.mkdir(parents=True, exist_ok=True)
    transform_path = transform_dir / f"{video_id}.mp4"

    await video_builder.convert_to_h264(
        input_path=str(raw_path),
        output_path=str(transform_path)
    )

    if not transform_path.exists():
        logger.error(f"❌ Transform failed: {video_id}")
        return None

    job_logger.info(f"      ✅ Transformed: {transform_path}")
    return transform_path


async def _crop_video(
    video_id: str,
    transform_path: Path,
    aspect_ratio: str,
    crop_position: str,
    video_builder: Any,
    job_logger: Any,
) -> Path | None:
    """Crop video to target aspect ratio. Returns updated transform_path or None."""
    job_logger.info(f"   ✂️  [2/5] Cropping to {aspect_ratio}: {video_id}")
    logger.info(f"✂️ Cropping {video_id} to {aspect_ratio}...")

    transform_dir = transform_path.parent
    cropped_temp = transform_dir / f"{video_id}_cropped_temp.mp4"

    await video_builder.crop_video_for_validation(
        video_path=str(transform_path),
        output_path=str(cropped_temp),
        aspect_ratio=aspect_ratio,
        crop_position=crop_position
    )

    if not cropped_temp.exists():
        logger.error(f"❌ Crop failed: {video_id}")
        if transform_path.exists():
            transform_path.unlink()
        return None

    transform_path.unlink()
    cropped_temp.rename(transform_path)
    job_logger.info(f"      ✅ Cropped (permanent): {transform_path}")
    return transform_path


async def _validate_ocr(
    video_id: str,
    validation_path: str,
    video_validator: Any,
    blacklist: Any,
    job_logger: Any,
) -> tuple[bool, float, str, int]:
    """Run OCR validation on video. Returns (approved, confidence, reason, frames_processed)."""
    job_logger.info(f"   🔍 [4/5] Validating (OCR 100% frames): {video_id}")
    logger.info(f"🔍 Validating {video_id} (OCR 100% frames)...")

    has_text, confidence, reason, frames_processed = video_validator.has_embedded_subtitles(
        video_path=validation_path,
        force_revalidation=True
    )

    if frames_processed == 0:
        logger.error(f"❌ ZERO FRAMES: {video_id} - corrupto")
        job_logger.error(f"   ❌ Zero frames processed - vídeo corrupto")
        blacklist.add(video_id, "zero_frames_processed", 0.0, {})

        if Path(validation_path).exists():
            Path(validation_path).unlink()
        return False, 0.0, "zero_frames_processed", 0

    approved = not has_text
    job_logger.info(f"      Frames processed: {frames_processed}")
    job_logger.info(f"      Has text: {'Yes' if has_text else 'No'}")
    job_logger.info(f"      Confidence: {confidence:.2f}%")

    return approved, confidence, reason, frames_processed


def _cleanup_on_error(
    video_id: str,
    validation_path: str | None,
    transform_path: Path | None,
) -> None:
    """Remove leftover files on processing error."""
    try:
        if validation_path and Path(validation_path).exists():
            Path(validation_path).unlink()
            logger.debug(f"🗑️  Cleanup: removed {validation_path}")
        elif transform_path and transform_path.exists():
            transform_path.unlink()
            logger.debug(f"🗑️  Cleanup: removed {transform_path}")
    except Exception:
        pass


async def transform_crop_and_validate_video(
    video_id: str,
    raw_video_path: str,
    job_id: str,
    aspect_ratio: str,
    crop_position: str,
    video_builder: Any,
    video_validator: Any,
    blacklist: Any,
    job_logger: Any,
) -> str | None:
    """
    Helper: Transform → Crop → Move → Validate → Finalize

    Args:
        video_id: ID do vídeo
        raw_video_path: Path do vídeo em data/raw/shorts/
        job_id: ID do job (para tag)
        aspect_ratio: Aspect ratio alvo
        crop_position: Posição do crop
        video_builder: VideoBuilder instance
        video_validator: VideoValidator instance
        blacklist: Blacklist instance
        job_logger: Logger do job

    Returns:
        Path do vídeo aprovado, ou None se rejeitado
    """
    from ..pipeline.video_pipeline import VideoPipeline

    pipeline = VideoPipeline()
    transform_path = None
    validation_path = None

    try:
        transform_path = await _transform_to_h264(video_id, raw_video_path, video_builder, job_logger)
        if not transform_path:
            return None

        transform_path = await _crop_video(
            video_id, transform_path, aspect_ratio, crop_position, video_builder, job_logger
        )
        if not transform_path:
            return None

        job_logger.info(f"   🔄 [3/5] Moving to validation: {video_id}")
        validation_path = pipeline.move_to_validation(video_id, str(transform_path), job_id)
        job_logger.info(f"      🏷️  Tagged: {Path(validation_path).name}")

        approved, confidence, reason, _ = await _validate_ocr(
            video_id, validation_path, video_validator, blacklist, job_logger
        )

        job_logger.info(f"   ✅ [5/5] Finalizing: {video_id}")

        if approved:
            final_path = pipeline.finalize_validation(validation_path, video_id, approved=True, job_id=job_id)
            if final_path:
                job_logger.info(f"      ✅ APPROVED: {video_id}")
                logger.info(f"✅ APPROVED: {video_id} → {final_path}")
                return final_path
            else:
                logger.error(f"❌ Failed to finalize approved video: {video_id}")
                return None
        else:
            pipeline.finalize_validation(validation_path, video_id, approved=False, job_id=job_id)
            blacklist.add(video_id, reason, confidence, {})
            job_logger.info(f"      ❌ REJECTED: {video_id} (reason: {reason})")
            logger.info(f"❌ REJECTED: {video_id} (reason: {reason})")
            return None

    except Exception as e:
        logger.error(f"❌ Error processing {video_id}: {e}", exc_info=True)
        job_logger.error(f"   ❌ Processing error: {e}")
        _cleanup_on_error(video_id, validation_path, transform_path)
        return None
