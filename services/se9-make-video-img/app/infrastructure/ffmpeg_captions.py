"""Caption rendering using FFmpeg drawtext filter."""
from __future__ import annotations

import shutil
from typing import Any

from common.log_utils import get_logger

from app.core.config import settings
from app.core.constants import H264_ENCODING_ARGS
from app.infrastructure.ffmpeg_runner import run_ffmpeg
from app.infrastructure.ffmpeg_probes import get_video_duration

logger = get_logger(__name__)


def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter.

    Handles: backslash, single quote, colon, percent, newline,
    semicolon, square brackets.
    """
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("'", "\\'")
    escaped = escaped.replace(":", "\\:")
    escaped = escaped.replace("%", "%%")
    escaped = escaped.replace("\n", " ")
    escaped = escaped.replace("\r", "")
    escaped = escaped.replace(";", "\\;")
    escaped = escaped.replace("[", "\\[")
    escaped = escaped.replace("]", "\\]")
    return escaped


async def render_captions(
    video_path: str,
    output_path: str,
    captions: list[dict[str, Any]],
    font_size: int = 48,
    font_color: str = "white",
    border_width: int = 3,
    position_y: str = "h-th-80",
    font: str = "Sans",
    ffmpeg_bin: str = "/usr/bin/ffmpeg",
) -> None:
    """Render on-screen captions using FFmpeg drawtext filter.

    Each caption entry must have:
    - text: str — caption text
    - t: float — start time in seconds
    - end_seconds: float | None — end time (default: t + 3.0)

    Captions are centered horizontally at the bottom of the video.
    Text has a black border for readability over any background.

    Captions with timing outside video duration are silently skipped.
    """
    if not captions:
        shutil.copy2(video_path, output_path)
        return

    # Get actual video duration for timing validation
    video_duration = await get_video_duration(video_path)

    # Build drawtext filter chain
    drawtext_filters: list[str] = []
    skipped = 0
    for cap in captions:
        text = cap.get("text", "").strip()
        if not text:
            skipped += 1
            continue

        start = cap.get("t", 0.0)
        end = cap.get("end_seconds") or (start + 3.0)

        # Skip captions that start after video ends
        if start >= video_duration:
            skipped += 1
            continue

        # Clamp end to video duration
        if end > video_duration:
            end = video_duration

        # Skip if no visible duration left after clamping
        if end <= start:
            skipped += 1
            continue

        escaped = _escape_drawtext(text)
        enable = f"between(t\\,{start:.3f}\\,{end:.3f})"
        dt = (
            f"drawtext=text='{escaped}'"
            f":font={font}"
            f":fontsize={font_size}"
            f":fontcolor={font_color}"
            f":borderw={border_width}"
            f":bordercolor=black"
            f":x=(w-tw)/2"
            f":y={position_y}"
            f":enable='{enable}'"
        )
        drawtext_filters.append(dt)

    if skipped:
        logger.warning("Skipped %d captions (outside video duration or empty text)", skipped)

    if not drawtext_filters:
        shutil.copy2(video_path, output_path)
        return

    vf = ",".join(drawtext_filters)

    args = [
        ffmpeg_bin, "-y",
        "-i", video_path,
        "-vf", vf,
        *H264_ENCODING_ARGS,
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]
    await run_ffmpeg(args, timeout=settings.ffmpeg_total_timeout)
