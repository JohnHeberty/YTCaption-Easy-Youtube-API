"""FFmpeg utilities for video assembly."""
import asyncio
from common.log_utils import get_logger
import os
import random
from typing import Optional

from app.core.config import settings
from app.core.constants import TRANSITIONS

logger = get_logger(__name__)


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


async def create_title_card(
    image_path: str,
    output_path: str,
    hook_text: str,
    duration: float = 0.5,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> None:
    """Create a brief darkened title card (no text overlay)."""
    frames = int(duration * fps)
    vf = (
        f"scale=-2:{height*2}:force_original_aspect_ratio=increase,"
        f"crop={width*2}:{height*2},"
        f"zoompan=z='1+0.002*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
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


async def concat_segments(
    segment_paths: list[str],
    output_path: str,
    crossfade_duration: float = 0.5,
    first_transition: str = "fade",
    other_transitions: str = "fade",
    transitions: list[str] | None = None,
) -> None:
    """Concatenate video segments with crossfade transitions.

    If transitions list is provided, uses one per segment pair (randomized).
    Otherwise falls back to first_transition/other_transitions.
    """
    if len(segment_paths) == 1:
        args = [
            "ffmpeg", "-y", "-i", segment_paths[0],
            "-c:v", "libx264", "-profile:v", "main", "-level", "4.0",
            "-g", "30", "-bf", "2", "-pix_fmt", "yuv420p",
            output_path,
        ]
        await run_ffmpeg(args)
        return

    inputs = []
    for path in segment_paths:
        inputs.extend(["-i", path])

    n = len(segment_paths)

    # Pre-probe all segment durations
    seg_durs = []
    for path in segment_paths:
        probe = await asyncio.create_subprocess_exec(
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await probe.communicate()
        seg_durs.append(float(stdout.decode().strip()))

    # Calculate correct offsets for chained xfade
    # offset = time in the CURRENT chain output where the transition starts
    # chain_output grows as: seg[0] + seg[1] - xfade + seg[2] - xfade + ...
    offsets = []
    xfade_durations = []
    chain_output = seg_durs[0]
    for i in range(n - 1):
        # Clamp crossfade to 15% of segment duration for quick transitions
        effective_xfade = min(crossfade_duration, seg_durs[i] * 0.15)
        effective_xfade = max(effective_xfade, 0.05)
        xfade_durations.append(effective_xfade)

        # Offset is within the current chain output, leaving room for xfade
        offset = chain_output - effective_xfade
        offsets.append(offset)

        # Chain output grows by the next segment minus crossfade overlap
        chain_output = chain_output + seg_durs[i + 1] - effective_xfade

    filter_complex = []
    prev = "[0:v]"
    for i in range(1, n):
        out = f"[vout{i}]" if i < n - 1 else "[vout]"
        if transitions and i - 1 < len(transitions):
            transition = transitions[i - 1]
        else:
            transition = first_transition if i == 1 else other_transitions
        xfade_dur = xfade_durations[i - 1]
        filter_complex.append(
            f"{prev}[{i}:v]xfade=transition={transition}:duration={xfade_dur:.3f}"
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
        "-profile:v", "main",
        "-level", "4.0",
        "-g", "30",
        "-bf", "2",
        "-pix_fmt", "yuv420p",
        output_path,
    ]
    await run_ffmpeg(args, timeout=settings.ffmpeg_total_timeout)


async def concat_simple(segment_paths: list[str], output_path: str) -> None:
    """Concatenate segments using concat demuxer (no transitions, fast, no OOM).

    Used when >8 segments to avoid xfade filter_complex OOM/SIGKILL.
    Hard cuts between segments — no crossfade transitions.
    """
    if len(segment_paths) == 1:
        import shutil
        shutil.copy2(segment_paths[0], output_path)
        return

    # Create concat list file
    list_path = output_path + ".txt"
    with open(list_path, "w") as f:
        for path in segment_paths:
            f.write(f"file '{os.path.abspath(path)}'\n")

    args = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ]
    try:
        await run_ffmpeg(args, timeout=settings.ffmpeg_total_timeout)
    finally:
        if os.path.exists(list_path):
            os.remove(list_path)


async def concat_batched(
    segment_paths: list[str],
    output_path: str,
    crossfade_duration: float = 0.5,
    transitions: list[str] | None = None,
    batch_size: int = 8,
) -> None:
    """Concatenate segments in batches of `batch_size` with xfade, then concat batches.

    Best of both worlds: transitions within each batch, fast concat between batches.
    For 13 segments with batch_size=8: [batch1: 8 with xfade] + [batch2: 5 with xfade]
    → concat_simple between the 2 batches. Only 1 hard cut instead of 12.
    """
    n = len(segment_paths)

    if n <= batch_size:
        # Fits in one batch — use regular xfade
        if transitions is None:
            transitions = [random.choice(TRANSITIONS) for _ in range(n - 1)]
        await concat_segments(
            segment_paths=segment_paths,
            output_path=output_path,
            crossfade_duration=crossfade_duration,
            transitions=transitions,
        )
        return

    # Split into batches
    batches = []
    for i in range(0, n, batch_size):
        batches.append(segment_paths[i:i + batch_size])

    logger.info(
        "Batched concat: %d segments → %d batches (%s)",
        n, len(batches), [len(b) for b in batches],
    )

    # Process each batch with xfade
    batch_paths = []
    for batch_idx, batch in enumerate(batches):
        batch_output = output_path.replace(".mp4", f"_batch{batch_idx}.mp4")
        batch_transitions = [random.choice(TRANSITIONS) for _ in range(len(batch) - 1)]

        logger.info(
            "Processing batch %d/%d: %d segments with xfade",
            batch_idx + 1, len(batches), len(batch),
        )
        await concat_segments(
            segment_paths=batch,
            output_path=batch_output,
            crossfade_duration=crossfade_duration,
            transitions=batch_transitions,
        )
        batch_paths.append(batch_output)

    # Concat batches with simple concat (hard cuts between batches)
    if len(batch_paths) == 1:
        import shutil
        shutil.move(batch_paths[0], output_path)
    else:
        await concat_simple(segment_paths=batch_paths, output_path=output_path)

    # Cleanup batch files
    for bp in batch_paths:
        if os.path.exists(bp) and bp != output_path:
            os.remove(bp)


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
        "-c:v", "libx264",
        "-profile:v", "main",
        "-level", "4.0",
        "-g", "30",
        "-bf", "2",
        "-c:a", "aac",
        "-profile:a", "aac_low",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]
    await run_ffmpeg(args)
