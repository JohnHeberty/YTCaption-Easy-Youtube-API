"""FFmpeg utilities for video assembly."""
import asyncio
import logging
import os
import random
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


async def run_ffmpeg(args: list[str], timeout: int = None) -> bytes:
    """Run an FFmpeg command asynchronously."""
    timeout = timeout or settings.ffmpeg_total_timeout
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    if proc.returncode != 0:
        error_msg = stderr.decode(errors="replace") if stderr else "Unknown error"
        raise RuntimeError(f"FFmpeg failed (code {proc.returncode}): {error_msg}")
    return stdout


async def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    proc = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    if proc.returncode != 0:
        raise RuntimeError("ffprobe failed to get audio duration")
    return float(stdout.decode().strip())


async def create_segment(
    image_path: str,
    output_path: str,
    duration: float,
    width: int,
    height: int,
    fps: int = 30,
    zoom_style: str = "random",
) -> None:
    """Create a video segment with Ken Burns effect."""
    frames = int(duration * fps)
    if frames < 1:
        frames = 1

    if zoom_style == "random":
        zoom_style = random.choice(["zoom_in", "zoom_out", "pan_left", "pan_right"])

    zoom_speed = settings.default_zoom_speed

    if zoom_style == "zoom_in":
        zoom_expr = f"1+{zoom_speed}*on"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif zoom_style == "zoom_out":
        zoom_expr = f"1.05-{zoom_speed}*on"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
    elif zoom_style == "pan_left":
        zoom_expr = "1.05"
        x_expr = f"iw*0.1-on*{zoom_speed}*5"
        y_expr = "ih/2-(ih/zoom/2)"
    elif zoom_style == "pan_right":
        zoom_expr = "1.05"
        x_expr = f"on*{zoom_speed}*5"
        y_expr = "ih/2-(ih/zoom/2)"
    else:
        zoom_expr = "1"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"

    vf = (
        f"scale={width*2}:{height*2},"
        f"zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}'"
        f":d={frames}:s={width}x{height}:fps={fps},"
        f"format=yuv420p"
    )

    args = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    await run_ffmpeg(args, timeout=settings.ffmpeg_segment_timeout)


async def concat_segments(
    segment_paths: list[str],
    output_path: str,
    crossfade_duration: float = 0.5,
) -> None:
    """Concatenate video segments with crossfade transitions."""
    if len(segment_paths) == 1:
        args = ["ffmpeg", "-y", "-i", segment_paths[0], "-c", "copy", output_path]
        await run_ffmpeg(args)
        return

    inputs = []
    for path in segment_paths:
        inputs.extend(["-i", path])

    filter_parts = []
    n = len(segment_paths)
    offsets = []

    current_duration = 0
    for i in range(n - 1):
        probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            segment_paths[i],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await probe.communicate()
        seg_dur = float(stdout.decode().strip())

        offset = current_duration + seg_dur - crossfade_duration
        offsets.append(offset)
        current_duration = offset + crossfade_duration

    filter_complex = []
    prev = "[0:v]"
    for i in range(1, n):
        out = f"[vout{i}]" if i < n - 1 else "[vout]"
        filter_complex.append(
            f"{prev}[{i}:v]xfade=transition=fade:duration={crossfade_duration}"
            f":offset={offsets[i-1]:.3f}{out}"
        )
        prev = out

    args = [
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", ";".join(filter_complex),
        "-map", "[vout]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        output_path,
    ]
    await run_ffmpeg(args, timeout=settings.ffmpeg_total_timeout)


async def add_audio(video_path: str, audio_path: str, output_path: str) -> None:
    """Add audio track to video."""
    args = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        output_path,
    ]
    await run_ffmpeg(args)


async def burn_subtitles(
    video_path: str,
    srt_path: str,
    output_path: str,
    font_size: int = 22,
) -> None:
    """Burn SRT subtitles into video."""
    vf = (
        f"subtitles={srt_path}"
        f":force_style='FontSize={font_size},"
        f"Alignment=2,MarginV=60'"
    )
    args = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-vf", vf,
        "-c:a", "copy",
        output_path,
    ]
    await run_ffmpeg(args)


async def trim_to_duration(video_path: str, duration: float, output_path: str) -> None:
    """Trim video to exact duration."""
    args = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264",
        "-c:a", "aac",
        output_path,
    ]
    await run_ffmpeg(args)
