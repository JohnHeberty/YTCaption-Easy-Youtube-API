"""Ken Burns segment creation for image-to-video."""
from __future__ import annotations

import random

from common.log_utils import get_logger

from app.core.config import settings
from app.infrastructure.ffmpeg_runner import run_ffmpeg

logger = get_logger(__name__)


async def create_title_card(
    image_path: str,
    output_path: str,
    duration: float,
    width: int,
    height: int,
    fps: int = 30,
    zoom_speed: float = 0.004,
) -> None:
    """Create a brief darkened title card (no text overlay)."""
    frames = int(duration * fps)
    vf = (
        f"scale=-2:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
        f"zoompan=z='1+{zoom_speed}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={frames}:s={width}x{height}:fps={fps},"
        f"format=yuv420p,"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.5:t=fill"
    )
    args = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-t", str(duration),
        "-vf", vf,
        "-c:v", "libx264",
        "-profile:v", "main",
        "-level", "4.0",
        "-g", "30",
        "-bf", "2",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    await run_ffmpeg(args, timeout=settings.ffmpeg_segment_timeout)


async def create_segment(
    image_path: str,
    output_path: str,
    duration: float,
    width: int,
    height: int,
    fps: int = 30,
    zoom_style: str = "random",
) -> None:
    """Create a video segment with Ken Burns zoom effect.

    Speed is auto-calculated from duration: zoom traverses 1.0→1.20 (or reverse)
    over the ENTIRE scene. Longer scenes = slower, cinematic zoom.
    Styles: zoom_in, zoom_out, random
    """
    frames = int(duration * fps)
    if frames < 1:
        frames = 1

    styles = ["zoom_in", "zoom_out"]
    if zoom_style == "random":
        zoom_style = random.choice(styles)

    n_frames = frames
    progress = f"on/{n_frames}"

    ZOOM_MAX = 1.20
    ZOOM_MIN = 1.0
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"

    if zoom_style == "zoom_in":
        zoom_expr = f"{ZOOM_MIN}+{ZOOM_MAX - ZOOM_MIN}*{progress}"
    elif zoom_style == "zoom_out":
        zoom_expr = f"{ZOOM_MAX}-{ZOOM_MAX - ZOOM_MIN}*{progress}"
    else:
        zoom_expr = f"{ZOOM_MIN}+{ZOOM_MAX - ZOOM_MIN}*{progress}"

    vf = (
        f"scale=-2:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
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
        "-profile:v", "main",
        "-level", "4.0",
        "-g", "30",
        "-bf", "2",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    await run_ffmpeg(args, timeout=settings.ffmpeg_segment_timeout)
