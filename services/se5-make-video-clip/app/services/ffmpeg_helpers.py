"""
FFmpeg/FFprobe Helpers

Shared subprocess wrappers and utility functions for FFmpeg operations.
"""
from __future__ import annotations

import json
from pathlib import Path

from common.log_utils import get_logger
from ..shared.exceptions_v2 import (
    SubprocessTimeoutException,
    FFmpegTimeoutException,
    FFprobeFailedException,
    AudioNotFoundException,
    AudioCorruptedException,
    SubtitleGenerationException,
)
from ..infrastructure.subprocess_utils import run_subprocess_with_timeout

logger = get_logger(__name__)


async def run_ffmpeg_cmd(
    cmd: list[str],
    timeout: int,
    operation: str,
    details: dict | None = None,
) -> tuple[int, bytes, bytes]:
    """Run FFmpeg command with standard timeout handling.

    Returns (returncode, stdout, stderr). Caller must check returncode.
    """
    try:
        returncode, stdout, stderr = await run_subprocess_with_timeout(
            cmd=cmd, timeout=timeout, check=False, capture_output=True
        )
        return returncode, stdout, stderr
    except SubprocessTimeoutException as e:
        raise FFmpegTimeoutException(
            operation=operation,
            timeout=timeout,
            details=details or {},
            cause=e,
        )


async def run_ffprobe_cmd(
    cmd: list[str],
    timeout: int = 30,
    operation: str = "ffprobe",
    video_path: str = "unknown",
) -> tuple[int, bytes, bytes]:
    """Run FFprobe command with standard timeout handling."""
    try:
        returncode, stdout, stderr = await run_subprocess_with_timeout(
            cmd=cmd, timeout=timeout, check=False, capture_output=True
        )
        return returncode, stdout, stderr
    except SubprocessTimeoutException as e:
        raise FFprobeFailedException(
            video_path=video_path,
            stderr=f"FFprobe timeout after {timeout}s",
            returncode=-1,
            cause=e,
        )


async def get_audio_duration_ffprobe(
    audio_path: str,
    ffprobe_path: str = "ffprobe",
) -> float:
    """Get audio duration via ffprobe. Shared helper for VideoBuilder methods."""
    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        str(audio_path),
    ]

    returncode, stdout, stderr = await run_ffprobe_cmd(
        cmd=cmd, timeout=30, operation="audio duration extraction",
        video_path=str(audio_path),
    )

    if returncode != 0:
        error_msg = stderr.decode() if stderr else "Unknown error"
        if "Invalid data found" in error_msg or "moov atom not found" in error_msg:
            raise AudioCorruptedException(
                audio_path=str(audio_path),
                reason="Audio file is corrupted or not a valid audio file",
                details={"ffprobe_error": error_msg[:500], "hint": "Upload a valid MP3, WAV, M4A, or OGG file"},
            )
        elif "No such file" in error_msg:
            raise AudioNotFoundException(
                audio_path=str(audio_path),
                expected_location=str(audio_path),
            )
        else:
            raise AudioCorruptedException(
                audio_path=str(audio_path),
                reason=f"FFprobe failed: {error_msg.split(':')[-1].strip()[:200] if error_msg else 'Unknown error'}",
                details={"ffprobe_error": error_msg[:500]},
            )

    info = json.loads(stdout.decode())
    return float(info["format"]["duration"])


def validate_srt(subtitle_path: str) -> None:
    """Validate SRT file exists and is not empty."""
    subtitle_path_obj = Path(subtitle_path).resolve()

    if not subtitle_path_obj.exists():
        raise SubtitleGenerationException(
            reason=f"Subtitle file not found: {subtitle_path_obj}",
            subtitle_path=str(subtitle_path_obj),
            details={"expected_path": str(subtitle_path_obj)},
        )

    subtitle_size = subtitle_path_obj.stat().st_size
    if subtitle_size == 0:
        raise SubtitleGenerationException(
            reason="Subtitle file is empty - subtitles are mandatory for this job",
            subtitle_path=str(subtitle_path_obj),
            details={
                "subtitle_size": 0,
                "expected_size": "> 0 bytes",
                "problem": "Cannot generate video without subtitles - empty SRT file",
                "recommendation": "Check audio transcription and VAD processing steps",
            },
        )


SUBTITLE_STYLES: dict[str, str] = {
    "static": "FontSize=20,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=10,MarginV=280",
    "dynamic": "FontSize=22,PrimaryColour=&H00FFFF&,OutlineColour=&H000000&,Outline=2,Bold=1,Alignment=10,MarginV=280",
    "minimal": "FontSize=18,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,Outline=1,Alignment=10,MarginV=280",
}


def get_subtitle_style(style_name: str) -> str:
    """Get ASS style string for subtitle burning."""
    return SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["dynamic"])
