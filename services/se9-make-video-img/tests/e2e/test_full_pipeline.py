"""E2E test: full pipeline from CSV script → SE7 → SE8 → FFmpeg → MP4.

Auto-detects service availability:
- SE7 + SE8 online  → real pipeline
- Any service offline → mock pipeline (generates dummy WAV/PNG, real FFmpeg assembly)
"""
import asyncio
import logging
import os
import random
import shutil
import subprocess
import time

import pytest

from app.core.models import (
    CreateVideoRequest,
    NarrationSegment,
    OnScreenText,
    SceneSuggestion,
    VideoJob,
    VideoJobStatus,
)
from app.infrastructure.redis_store import VideoJobStore, _FakeRedis
from tests.fixtures_loader import load_all_scripts, build_request, pick_random_script

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers for mock mode — generate real media files using system tools
# ---------------------------------------------------------------------------

def _create_dummy_wav(path: str, duration: float = 5.0, sample_rate: int = 22050) -> None:
    """Create a valid WAV file using ffmpeg (sine wave tone)."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={duration}:sample_rate={sample_rate}",
            "-c:a", "pcm_s16le",
            path,
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )


def _create_dummy_png(path: str, width: int = 1024, height: int = 1792, color: str = "blue") -> None:
    """Create a valid PNG file using ffmpeg (solid color frame)."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c={color}:s={width}x{height}:d=1:r=1",
            "-frames:v", "1",
            path,
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )


def _get_video_duration(path: str) -> float:
    """Get video duration via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def _get_file_size_mb(path: str) -> float:
    return os.path.getsize(path) / (1024 * 1024)


# ---------------------------------------------------------------------------
# Mock pipeline — replaces SE7/SE8 calls with local dummy file generation
# ---------------------------------------------------------------------------

class MockAudioGenerator:
    """Generates a dummy WAV file instead of calling SE7."""

    def __init__(self):
        pass

    async def close(self):
        pass

    async def generate(
        self,
        narration: list[NarrationSegment],
        voice_id: str = "builtin_feminino",
        output_dir: str = "/tmp",
    ) -> tuple[str, float]:
        """Generate a dummy WAV matching estimated duration."""
        if narration:
            estimated_duration = max(narration[-1].t + 5.0, 5.0)
        else:
            estimated_duration = 10.0

        audio_path = os.path.join(output_dir, "audio.wav")
        _create_dummy_wav(audio_path, duration=estimated_duration)
        from app.infrastructure.ffmpeg_utils import get_audio_duration
        duration = await get_audio_duration(audio_path)
        logger.info(f"[MOCK] Audio generated: {audio_path} ({duration:.1f}s)")
        return audio_path, duration


class MockImageGenerator:
    """Generates dummy PNG files instead of calling SE8."""

    COLORS = ["blue", "red", "green", "yellow", "purple", "orange", "cyan", "magenta"]

    def __init__(self):
        pass

    async def close(self):
        pass

    async def generate_all(
        self,
        scenes: list[SceneSuggestion],
        aspect_ratio: str = "9:16",
        steps: int = 30,
        performance: str = "Quality",
        output_dir: str = "/tmp",
        progress_callback=None,
    ) -> list[str]:
        """Generate dummy solid-color PNGs for each scene."""
        dims = {"9:16": (1024, 1792), "16:9": (1792, 1024), "1:1": (1024, 1024)}
        w, h = dims.get(aspect_ratio, (1024, 1792))

        sorted_scenes = sorted(scenes, key=lambda s: s.t)
        image_paths = []
        for i, scene in enumerate(sorted_scenes):
            color = self.COLORS[i % len(self.COLORS)]
            image_path = os.path.join(output_dir, f"scene_{int(scene.t)}.png")
            _create_dummy_png(image_path, width=w, height=h, color=color)
            image_paths.append(image_path)
            logger.info(f"[MOCK] Image generated: {image_path} ({color})")
            if progress_callback:
                await progress_callback(((i + 1) / len(sorted_scenes)) * 100)

        return image_paths


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.e2e
def test_full_pipeline_from_csv(
    csv_data_dir: str,
    output_dir: str,
    services_online: dict,
):
    """Full pipeline: random CSV script → audio → images → FFmpeg → MP4.

    If SE7+SE8 are online, uses real services.
    Otherwise, generates dummy media files locally and runs real FFmpeg assembly.
    """
    script_id, request = pick_random_script(csv_data_dir, seed=42)
    logger.info(f"Testing script_id={script_id}, narration={len(request.narration)} segments, "
                f"scenes={len(request.scene_suggestions)}")

    job = VideoJob(
        job_id=f"rbg_e2e_{script_id}",
        post_id=request.post_id,
        request=request,
    )

    use_mock = not (services_online["se7"] and services_online["se8"])
    mode = "MOCK" if use_mock else "REAL"
    logger.info(f"Running E2E test in {mode} mode (SE7={'online' if services_online['se7'] else 'offline'}, "
                f"SE8={'online' if services_online['se8'] else 'offline'})")

    test_dir = os.path.join(output_dir, f"e2e_{script_id}")
    os.makedirs(test_dir, exist_ok=True)

    try:
        # --- Phase 1: Audio generation ---
        logger.info("[Phase 1] Generating audio...")
        t0 = time.time()

        if use_mock:
            audio_gen = MockAudioGenerator()
        else:
            from app.services.audio_generator import AudioGenerator
            audio_gen = AudioGenerator()

        audio_path, audio_duration = asyncio.get_event_loop().run_until_complete(
            audio_gen.generate(
                narration=request.narration,
                voice_id=request.voice_id,
                output_dir=test_dir,
            )
        )
        asyncio.get_event_loop().run_until_complete(audio_gen.close())
        audio_time = time.time() - t0
        logger.info(f"[Phase 1] Audio: {audio_path} ({audio_duration:.1f}s) in {audio_time:.1f}s")
        assert os.path.exists(audio_path), "Audio file not created"
        assert audio_duration > 0, "Audio duration must be positive"

        # --- Phase 2: Image generation ---
        logger.info("[Phase 2] Generating images...")
        t0 = time.time()

        if use_mock:
            img_gen = MockImageGenerator()
        else:
            from app.services.image_generator import ImageGenerator
            img_gen = ImageGenerator()

        image_paths = asyncio.get_event_loop().run_until_complete(
            img_gen.generate_all(
                scenes=request.scene_suggestions,
                aspect_ratio=request.aspect_ratio,
                output_dir=test_dir,
            )
        )
        asyncio.get_event_loop().run_until_complete(img_gen.close())
        img_time = time.time() - t0
        logger.info(f"[Phase 2] Images: {len(image_paths)} files in {img_time:.1f}s")
        assert len(image_paths) == len(request.scene_suggestions), \
            f"Expected {len(request.scene_suggestions)} images, got {len(image_paths)}"
        for p in image_paths:
            assert os.path.exists(p), f"Image not found: {p}"

        # --- Phase 3: FFmpeg assembly (always real) ---
        logger.info("[Phase 3] Assembling video with FFmpeg...")
        t0 = time.time()

        from app.services.video_assembler import VideoAssembler
        assembler = VideoAssembler()
        video_path = asyncio.get_event_loop().run_until_complete(
            assembler.assemble(
                audio_path=audio_path,
                image_paths=image_paths,
                narration=request.narration,
                output_dir=test_dir,
                width=1080,
                height=1920,
                fps=30,
                zoom_style=request.zoom_style,
                crossfade_duration=0.5,
                hook_text=request.hook,
            )
        )
        asm_time = time.time() - t0
        logger.info(f"[Phase 3] Video assembled: {video_path} in {asm_time:.1f}s")

        # --- Phase 4: Validation ---
        assert os.path.exists(video_path), "Final video not created"
        video_size_mb = _get_file_size_mb(video_path)
        video_duration = _get_video_duration(video_path)
        logger.info(f"[Phase 4] Video: {video_duration:.1f}s, {video_size_mb:.1f}MB")

        assert video_size_mb > 0.01, f"Video too small: {video_size_mb}MB"
        assert video_duration > 1.0, f"Video too short: {video_duration}s"

        duration_diff = abs(video_duration - audio_duration)
        assert duration_diff < 5.0, \
            f"Video/audio duration mismatch: video={video_duration:.1f}s, audio={audio_duration:.1f}s, diff={duration_diff:.1f}s"

        # Copy final to output root with descriptive name
        final_dest = os.path.join(output_dir, f"{script_id}_final.mp4")
        shutil.copy2(video_path, final_dest)
        logger.info(f"Final video saved to: {final_dest}")

        total_time = audio_time + img_time + asm_time
        logger.info(f"E2E test completed in {total_time:.1f}s "
                    f"(audio={audio_time:.1f}s, images={img_time:.1f}s, assembly={asm_time:.1f}s)")
        logger.info(f"Mode: {mode} | script_id: {script_id}")

    finally:
        # Keep test_dir for inspection — don't cleanup on success
        pass
