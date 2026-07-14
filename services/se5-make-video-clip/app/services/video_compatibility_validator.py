"""
Video Compatibility Validator

Validates that videos can be safely concatenated without FFmpeg errors.
Prevents incompatibility issues (codec, FPS, resolution) before concatenation.
"""
from __future__ import annotations

from typing import Any
from pathlib import Path

from ..shared.exceptions_v2 import VideoIncompatibleException
from common.log_utils import get_logger

logger = get_logger(__name__)

class VideoCompatibilityValidator:
    """
    Validates video compatibility for concatenation

    Checks:
    - Codec consistency (all must use same codec)
    - FPS consistency (frame rate must match)
    - Resolution consistency (width x height must match)

    Prevents FFmpeg concatenation errors caused by incompatible streams.

    Example:
        result = await VideoCompatibilityValidator.validate_concat_compatibility(
            video_files=["/tmp/video1.mp4", "/tmp/video2.mp4"],
            video_builder=builder,
            strict=True
        )
    """

    @staticmethod
    async def _extract_videos_metadata(
        video_files: list[str],
        video_builder: Any,
    ) -> list[dict[str, Any]]:
        """Extract metadata from all video files."""
        videos_metadata: list[dict[str, Any]] = []
        for idx, video_path in enumerate(video_files):
            video_path_obj = Path(video_path)
            if not video_path_obj.exists():
                logger.error(f"Video file not found: {video_path}")
                raise FileNotFoundError(f"Video file not found: {video_path}")
            try:
                info = await video_builder.get_video_info(str(video_path))
                metadata = {
                    "index": idx,
                    "path": str(video_path),
                    "filename": video_path_obj.name,
                    "codec": info.get('codec', 'unknown'),
                    "fps": float(info.get('fps', 0)),
                    "width": int(info.get('width', 0)),
                    "height": int(info.get('height', 0)),
                    "duration": float(info.get('duration', 0)),
                    "resolution": f"{info.get('width')}x{info.get('height')}"
                }
                videos_metadata.append(metadata)
            except Exception:
                logger.error(
                    f"Failed to extract metadata from video {idx}: {video_path}",
                    exc_info=True
                )
                raise
        return videos_metadata

    @staticmethod
    def _validate_against_reference(
        videos_metadata: list[dict[str, Any]],
        reference: dict[str, Any],
        fps_tolerance: float,
    ) -> list[dict[str, Any]]:
        """Compare each video against reference for codec/FPS/resolution mismatches."""
        incompatibilities: list[dict[str, Any]] = []
        for video_meta in videos_metadata[1:]:
            issues: list[dict[str, Any]] = []
            if video_meta['codec'] != reference['codec']:
                issues.append({
                    "type": "codec",
                    "expected": reference['codec'],
                    "actual": video_meta['codec'],
                    "severity": "high"
                })
                logger.warning(
                    f"⚠️ Video {video_meta['index']} codec mismatch",
                    extra={
                        "video": video_meta['filename'],
                        "expected": reference['codec'],
                        "actual": video_meta['codec']
                    }
                )
            fps_diff = abs(video_meta['fps'] - reference['fps'])
            if fps_diff > fps_tolerance:
                issues.append({
                    "type": "fps",
                    "expected": reference['fps'],
                    "actual": video_meta['fps'],
                    "diff": fps_diff,
                    "tolerance": fps_tolerance,
                    "severity": "high"
                })
                logger.warning(
                    f"⚠️ Video {video_meta['index']} FPS mismatch",
                    extra={
                        "video": video_meta['filename'],
                        "expected": reference['fps'],
                        "actual": video_meta['fps'],
                        "diff": fps_diff
                    }
                )
            if (video_meta['width'] != reference['width'] or
                video_meta['height'] != reference['height']):
                issues.append({
                    "type": "resolution",
                    "expected": reference['resolution'],
                    "actual": video_meta['resolution'],
                    "severity": "high"
                })
                logger.warning(
                    f"⚠️ Video {video_meta['index']} resolution mismatch",
                    extra={
                        "video": video_meta['filename'],
                        "expected": reference['resolution'],
                        "actual": video_meta['resolution']
                    }
                )
            if issues:
                incompatibilities.append({
                    "video_index": video_meta['index'],
                    "video_path": video_meta['path'],
                    "video_filename": video_meta['filename'],
                    "issues": issues
                })
        return incompatibilities

    @staticmethod
    def _raise_if_strict(
        strict: bool,
        is_compatible: bool,
        incompatibilities: list[dict[str, Any]],
        reference: dict[str, Any],
    ) -> None:
        """Raise VideoIncompatibleException when strict mode and incompatibilities found."""
        if not strict or is_compatible:
            return
        first_incompat = incompatibilities[0]
        first_issue = first_incompat['issues'][0]
        raise VideoIncompatibleException(
            reason=f"Video {first_incompat['video_index']} ({first_incompat['video_filename']}) has incompatible {first_issue['type']}",
            mismatches={
                "video_index": first_incompat['video_index'],
                "video_path": first_incompat['video_path'],
                "issues": first_incompat['issues'],
                "reference": {
                    "codec": reference['codec'],
                    "fps": reference['fps'],
                    "resolution": reference['resolution']
                }
            },
            details={
                "incompatibility_type": first_issue['type'],
                "expected": first_issue['expected'],
                "actual": first_issue['actual'],
                "total_incompatibilities": len(incompatibilities)
            }
        )

    @staticmethod
    async def validate_concat_compatibility(
        video_files: list[str],
        video_builder,  # VideoBuilder instance (avoid circular import)
        strict: bool = True,
        fps_tolerance: float = 0.1
    ) -> dict[str, Any]:
        """
        Validate that videos are compatible for concatenation

        Compares all videos against first video (reference) and detects:
        - Codec mismatches (h264 vs vp9, etc)
        - FPS mismatches (30fps vs 60fps, etc)
        - Resolution mismatches (1080x1920 vs 1080x1080, etc)

        Args:
            video_files: List of video file paths to validate
            video_builder: VideoBuilder instance for metadata extraction
            strict: If True, raises exception on first incompatibility
                   If False, returns warnings but doesn't fail
            fps_tolerance: Maximum acceptable FPS difference (default: 0.1)

        Returns:
            Dict with:
            - is_compatible: bool
            - total_videos: int
            - reference_video: dict (metadata of first video)
            - incompatibilities: list of detected issues

        Raises:
            VideoIncompatibleException: If incompatibility detected (strict=True)
            ValueError: If video_files is empty
        """
        if not video_files:
            raise ValueError("No video files to validate")

        if len(video_files) == 1:
            logger.info("Single video - compatibility check skipped")
            return {
                "is_compatible": True,
                "total_videos": 1,
                "reference_video": None,
                "incompatibilities": []
            }

        logger.info(
            f"🔍 Validating compatibility of {len(video_files)} videos for concatenation"
        )

        videos_metadata = await VideoCompatibilityValidator._extract_videos_metadata(video_files, video_builder)

        reference = videos_metadata[0]
        logger.info(
            f"📐 Reference video (video 0):",
            extra={
                "codec": reference['codec'],
                "fps": reference['fps'],
                "resolution": reference['resolution'],
                "duration": reference['duration']
            }
        )

        incompatibilities = VideoCompatibilityValidator._validate_against_reference(
            videos_metadata, reference, fps_tolerance
        )

        is_compatible = len(incompatibilities) == 0

        if is_compatible:
            logger.info(
                f"✅ All {len(video_files)} videos compatible for concatenation",
                extra={
                    "video_count": len(video_files),
                    "codec": reference['codec'],
                    "fps": reference['fps'],
                    "resolution": reference['resolution']
                }
            )
        else:
            logger.warning(
                f"⚠️ Incompatible videos detected: {len(incompatibilities)} videos have issues",
                extra={
                    "incompatibility_count": len(incompatibilities),
                    "total_videos": len(video_files),
                    "details": incompatibilities
                }
            )

        VideoCompatibilityValidator._raise_if_strict(strict, is_compatible, incompatibilities, reference)

        return {
            "is_compatible": is_compatible,
            "total_videos": len(video_files),
            "validated_videos": len(videos_metadata),
            "reference_video": reference,
            "incompatibilities": incompatibilities,
            "incompatibility_count": len(incompatibilities)
        }
