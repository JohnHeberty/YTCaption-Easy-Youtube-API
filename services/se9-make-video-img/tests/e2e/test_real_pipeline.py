"""REAL E2E test: CSV fixtures → SE7 audio → SE8 images → FFmpeg video.

This test requires SE7 (port 8007) and SE8 (port 8008) running.
Run with: python -m pytest tests/e2e/test_real_pipeline.py -v -s
"""
import asyncio
import logging
import os
import time

import httpx
import pytest

from app.core.config import settings
from app.core.models import VideoJob, VideoJobStatus
from app.services.audio_generator import AudioGenerator
from app.services.image_generator import ImageGenerator
from app.services.video_assembler import VideoAssembler

logger = logging.getLogger(__name__)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "fixtures")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "outputs")


def _check(url: str) -> bool:
    try:
        r = httpx.get(f"{url}/ping", timeout=3)
        if r.status_code == 200:
            return True
        r = httpx.get(f"{url}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


SE7_ONLINE = _check(settings.se7_url)
SE8_ONLINE = _check(settings.se8_url)

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def real_output_dir():
    d = os.path.join(OUTPUT_DIR, "real_e2e")
    os.makedirs(d, exist_ok=True)
    return d


@pytest.mark.skipif(not SE7_ONLINE, reason="SE7 offline")
@pytest.mark.skipif(not SE8_ONLINE, reason="SE8 offline")
class TestRealPipeline:
    """Full pipeline with real SE7 + SE8 + CSV fixtures."""

    def test_smallest_script(self, real_output_dir):
        """Test with script_id=1068 (5 segments, 1194 chars, 5 scenes)."""
        self._run_script("1068", real_output_dir)

    def test_medium_script(self, real_output_dir):
        """Test with script_id=981 (11 segments, 1315 chars, 11 scenes)."""
        self._run_script("981", real_output_dir)

    def _run_script(self, script_id: str, output_dir: str):
        """Run full pipeline for a given CSV script_id."""
        from tests.fixtures_loader import load_all_scripts, build_request

        scripts = load_all_scripts(FIXTURES_DIR)
        assert script_id in scripts, f"script_id={script_id} not found in fixtures"

        data = scripts[script_id]
        request = build_request(data)

        test_dir = os.path.join(output_dir, script_id)
        os.makedirs(test_dir, exist_ok=True)

        job = VideoJob(
            job_id=f"real_e2e_{script_id}",
            post_id=request.post_id,
            request=request,
        )

        logger.info(f"=== REAL E2E: script_id={script_id} ===")
        logger.info(f"Narration: {len(request.narration)} segments, "
                    f"{sum(len(s.text) for s in request.narration)} chars")
        logger.info(f"Scenes: {len(request.scene_suggestions)}")
        logger.info(f"Hook: {request.hook[:80]}...")

        # Phase 1: Audio (SE7)
        logger.info("\n--- Phase 1: SE7 Audio Generation ---")
        t0 = time.time()
        audio_gen = AudioGenerator()
        try:
            audio_path, audio_duration = asyncio.get_event_loop().run_until_complete(
                audio_gen.generate(
                    narration=request.narration,
                    voice_id=request.voice_id,
                    output_dir=test_dir,
                )
            )
        finally:
            asyncio.get_event_loop().run_until_complete(audio_gen.close())
        audio_time = time.time() - t0
        logger.info(f"Audio: {audio_path} ({audio_duration:.1f}s) in {audio_time:.1f}s")
        assert os.path.exists(audio_path)
        assert audio_duration > 0

        # Phase 2: Images (SE8)
        logger.info("\n--- Phase 2: SE8 Image Generation ---")
        t0 = time.time()
        img_gen = ImageGenerator()
        try:
            image_paths = asyncio.get_event_loop().run_until_complete(
                img_gen.generate_all(
                    scenes=request.scene_suggestions,
                    aspect_ratio=request.aspect_ratio,
                    output_dir=test_dir,
                )
            )
        finally:
            asyncio.get_event_loop().run_until_complete(img_gen.close())
        img_time = time.time() - t0
        logger.info(f"Images: {len(image_paths)} files in {img_time:.1f}s")
        assert len(image_paths) == len(request.scene_suggestions)
        for p in image_paths:
            assert os.path.exists(p)

        # Phase 3: FFmpeg Assembly
        logger.info("\n--- Phase 3: FFmpeg Assembly ---")
        t0 = time.time()
        assembler = VideoAssembler()
        video_path = asyncio.get_event_loop().run_until_complete(
            assembler.assemble(
                audio_path=audio_path,
                image_paths=image_paths,
                narration=request.narration,
                output_dir=test_dir,
                job_id=script_id,
                width=settings.default_width,
                height=settings.default_height,
                fps=settings.default_fps,
                zoom_style=request.zoom_style,
                crossfade_duration=settings.default_crossfade_duration,
                hook_text=request.hook,
            )
        )
        ffmpeg_time = time.time() - t0
        logger.info(f"Video: {video_path} in {ffmpeg_time:.1f}s")

        # Phase 4: Validation
        logger.info("\n--- Phase 4: Validation ---")
        assert os.path.exists(video_path)
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        logger.info(f"File size: {file_size_mb:.2f} MB")

        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True,
        )
        import json
        info = json.loads(result.stdout)
        streams = info["streams"]
        video_stream = next(s for s in streams if s["codec_type"] == "video")
        audio_stream = next(s for s in streams if s["codec_type"] == "audio")

        duration = float(info["format"]["duration"])
        logger.info(f"Duration: {duration:.1f}s")
        logger.info(f"Video: {video_stream['codec_name']} {video_stream['width']}x{video_stream['height']} "
                    f"{video_stream['r_frame_rate']}fps")
        logger.info(f"Audio: {audio_stream['codec_name']} {audio_stream.get('sample_rate', '?')}Hz "
                    f"{audio_stream.get('channels', '?')}ch")

        assert duration > 1, f"Video too short: {duration}s"
        assert video_stream["codec_name"] == "h264"
        assert int(video_stream["width"]) == settings.default_width
        assert int(video_stream["height"]) == settings.default_height
        assert file_size_mb > 0.01

        # Summary
        total_time = audio_time + img_time + ffmpeg_time
        logger.info(f"\n=== SUMMARY ===")
        logger.info(f"Audio: {audio_time:.1f}s | Images: {img_time:.1f}s | FFmpeg: {ffmpeg_time:.1f}s")
        logger.info(f"Total: {total_time:.1f}s")
        logger.info(f"Output: {video_path}")
