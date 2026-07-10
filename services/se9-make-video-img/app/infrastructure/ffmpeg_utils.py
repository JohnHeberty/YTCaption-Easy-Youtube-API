"""FFmpeg utilities for video assembly — re-exports from focused modules.

This module maintains backward compatibility. Import from the sub-modules directly
for new code.
"""
from __future__ import annotations

# Re-export all public symbols for backward compatibility
from app.infrastructure.ffmpeg_runner import run_ffmpeg
from app.infrastructure.ffmpeg_probes import get_audio_duration, get_video_duration
from app.infrastructure.ffmpeg_segments import create_title_card, create_segment
from app.infrastructure.ffmpeg_concat import concat_segments, concat_simple, concat_batched
from app.infrastructure.ffmpeg_assembly import add_audio, trim_to_duration
from app.infrastructure.ffmpeg_captions import render_captions

__all__ = [
    "run_ffmpeg",
    "get_audio_duration",
    "get_video_duration",
    "create_title_card",
    "create_segment",
    "concat_segments",
    "concat_simple",
    "concat_batched",
    "add_audio",
    "trim_to_duration",
    "render_captions",
]
