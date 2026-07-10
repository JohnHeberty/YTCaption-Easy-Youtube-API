"""Core FFmpeg subprocess runner."""
from __future__ import annotations

import asyncio

from common.log_utils import get_logger

from app.core.config import settings

logger = get_logger(__name__)


async def run_ffmpeg(args: list[str], timeout: int | None = None) -> bytes:
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
