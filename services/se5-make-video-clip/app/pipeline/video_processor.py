"""
Video Processor — FFmpeg transform and crop operations.

Handles H264 conversion and permanent aspect-ratio cropping via
subprocess calls and VideoBuilder delegation.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)

FFMPEG_TRANSFORM_TIMEOUT = 120


class VideoProcessor:
    """Transform raw videos to H264 and crop to target aspect ratio."""

    def __init__(self, video_builder: Any) -> None:
        self._video_builder = video_builder

    def transform_video(self, video_id: str, raw_path: str) -> str | None:
        """
        Convert raw video to H264-compatible format.

        Args:
            video_id: Video identifier.
            raw_path: Path to the raw video file.

        Returns:
            Path to the transformed video, or None on failure.
        """
        logger.info("TRANSFORM: Converting %s to H264", video_id)

        try:
            raw_video = Path(raw_path)
            if not raw_video.exists():
                logger.error("File not found: %s", raw_path)
                return None

            transform_path = Path(f"data/transform/videos/{video_id}.mp4")

            cmd = [
                'ffmpeg',
                '-i', str(raw_video),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-crf', '23',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                '-y',
                str(transform_path),
            ]

            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=FFMPEG_TRANSFORM_TIMEOUT,
            )

            if result.returncode == 0 and transform_path.exists():
                logger.info("Converted: %s", transform_path)
                return str(transform_path)
            else:
                stderr_output = (
                    result.stderr.decode('utf-8', errors='ignore') if result.stderr else 'No stderr'
                )
                logger.error("Conversion failed (code %d)", result.returncode)
                logger.error("FFmpeg stderr: %s", stderr_output[-500:])
                return None

        except Exception as e:
            logger.error("Error during conversion: %s", e, exc_info=True)
            return None

    async def crop_video_permanent(
        self,
        video_id: str,
        transform_path: str,
        aspect_ratio: str = "9:16",
        crop_position: str = "center",
    ) -> str | None:
        """
        Permanently crop video to target aspect ratio via VideoBuilder.

        The cropped video replaces the original transform file.
        This crop happens BEFORE OCR validation.

        Args:
            video_id: Video identifier.
            transform_path: Path to the H264-transformed video.
            aspect_ratio: Target aspect ratio ("9:16", "16:9", "1:1", "4:5").
            crop_position: Crop anchor ("center", "top", "bottom").

        Returns:
            Path to the cropped video (same as transform_path), or None on failure.
        """
        logger.info("CROP: Applying permanent %s crop to %s", aspect_ratio, video_id)

        cropped_temp = None
        try:
            cropped_temp = Path(f"data/transform/videos/{video_id}_cropped_temp.mp4")

            await self._video_builder.crop_video_for_validation(
                video_path=transform_path,
                output_path=str(cropped_temp),
                aspect_ratio=aspect_ratio,
                crop_position=crop_position,
            )

            if not cropped_temp.exists():
                logger.error("Crop failed: file not created")
                return None

            transform_file = Path(transform_path)
            if transform_file.exists():
                transform_file.unlink()

            cropped_temp.rename(transform_file)

            logger.info("Permanently cropped: %s (%s)", transform_path, aspect_ratio)
            return str(transform_file)

        except Exception as e:
            logger.error("Error during permanent crop: %s", e, exc_info=True)
            if cropped_temp and cropped_temp.exists():
                cropped_temp.unlink()
            return None
