"""Video segment concatenation with transitions."""
from __future__ import annotations

import asyncio
import os
import random

from common.log_utils import get_logger

from app.core.config import settings
from app.core.constants import H264_ENCODING_ARGS, TRANSITIONS
from app.infrastructure.ffmpeg_runner import run_ffmpeg

logger = get_logger(__name__)


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
            *H264_ENCODING_ARGS,
            output_path,
        ]
        await run_ffmpeg(args)
        return

    inputs: list[str] = []
    for path in segment_paths:
        inputs.extend(["-i", path])

    n = len(segment_paths)

    # Pre-probe all segment durations
    seg_durs: list[float] = []
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
    offsets: list[float] = []
    xfade_durations: list[float] = []
    chain_output = seg_durs[0]
    for i in range(n - 1):
        effective_xfade = min(crossfade_duration, seg_durs[i] * 0.15)
        effective_xfade = max(effective_xfade, 0.05)
        xfade_durations.append(effective_xfade)

        offset = chain_output - effective_xfade
        offsets.append(offset)

        chain_output = chain_output + seg_durs[i + 1] - effective_xfade

    filter_complex: list[str] = []
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
        *H264_ENCODING_ARGS,
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
    """Concatenate segments in batches of `batch_size` with xfade, then concat batches."""
    n = len(segment_paths)

    if n <= batch_size:
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
    batches: list[list[str]] = []
    for i in range(0, n, batch_size):
        batches.append(segment_paths[i:i + batch_size])

    logger.info(
        "Batched concat: %d segments → %d batches (%s)",
        n, len(batches), [len(b) for b in batches],
    )

    # Process each batch with xfade
    batch_paths: list[str] = []
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

    # Concat batches with simple concat
    if len(batch_paths) == 1:
        import shutil
        shutil.move(batch_paths[0], output_path)
    else:
        await concat_simple(segment_paths=batch_paths, output_path=output_path)

    # Cleanup batch files
    for bp in batch_paths:
        if os.path.exists(bp) and bp != output_path:
            os.remove(bp)
