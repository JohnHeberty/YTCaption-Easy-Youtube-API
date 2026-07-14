"""Audio/video assembly utilities."""
from __future__ import annotations

from app.core.constants import H264_ENCODING_ARGS
from app.infrastructure.ffmpeg_runner import run_ffmpeg


async def add_audio(video_path: str, audio_path: str, output_path: str) -> None:
    """Add audio track to video, resampling to 44100Hz stereo for compatibility.

    Does NOT use -shortest so audio plays fully. If video is shorter, the last
    frame is held (freeze frame) until audio ends. The trim step handles final length.
    """
    args = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    await run_ffmpeg(args)


async def trim_to_duration(video_path: str, duration: float, output_path: str) -> None:
    """Trim video to exact duration."""
    args = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-t", f"{duration:.3f}",
        *H264_ENCODING_ARGS,
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", "192k",
        "-movflags", "+faststart",
        output_path,
    ]
    await run_ffmpeg(args)
