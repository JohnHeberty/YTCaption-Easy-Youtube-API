"""Pipeline orchestrator for video generation."""
from __future__ import annotations

import asyncio
import os
from typing import Any

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import (
    CreateVideoRequest,
    StageInfo,
    StageStatus,
    VideoJob,
    VideoJobStatus,
)
from app.infrastructure.redis_store import VideoJobStore, get_video_job_store
from app.services.audio_generator import AudioGenerator
from app.services.image_generator import ImageGenerator
from app.services.video_assembler import VideoAssembler

logger = get_logger(__name__)

MAX_AUDIO_RETRIES = 3
RETRY_BACKOFF_BASE = 2


class VideoPipeline:
    """Orchestrate the full video generation pipeline."""

    def __init__(
        self,
        store: VideoJobStore | None = None,
        audio_generator_cls: type[AudioGenerator] | None = None,
        image_generator_cls: type[ImageGenerator] | None = None,
        assembler_cls: type[VideoAssembler] | None = None,
    ) -> None:
        self.store = store or get_video_job_store()
        self._audio_generator_cls = audio_generator_cls or AudioGenerator
        self._image_generator_cls = image_generator_cls or ImageGenerator
        self._assembler_cls = assembler_cls or VideoAssembler

    async def run(self, job: VideoJob) -> None:
        """Run the complete pipeline for a video job.

        All artifacts (audio, images, intermediates, final video) are stored
        in output/{job_id}/.
        """
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        try:
            audio_path, _audio_duration = await self._generate_audio(job, output_dir)

            image_paths = await self._generate_images(job, output_dir)

            final_video = await self._assemble_video(job, audio_path, image_paths, output_dir)
            job.video_path = final_video

            job.status = VideoJobStatus.COMPLETED
            job.progress = 100.0
            job.updated_at = now_brazil()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            logger.info("Job %s completed: %s", job.job_id, final_video)

            await self._notify_webhook(job)

        except Exception as e:
            logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
            job.status = VideoJobStatus.FAILED
            job.error = str(e)
            job.updated_at = now_brazil()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            raise

    async def _generate_audio(self, job: VideoJob, output_dir: str) -> tuple[str, float]:
        """Generate audio with retry logic. Returns (audio_path, audio_duration)."""
        await self._update_stage(job, "generating_audio", "start")
        audio_path: str | None = None
        audio_duration = 0.0
        last_audio_error: Exception | None = None
        for attempt in range(MAX_AUDIO_RETRIES + 1):
            audio_gen = self._audio_generator_cls()
            try:
                audio_path, audio_duration = await audio_gen.generate(
                    narration=job.request.narration,
                    voice_id=job.request.voice_id,
                    output_dir=output_dir,
                    normalize_text=getattr(job.request, 'normalize_text', settings.default_normalize_text),
                )
                last_audio_error = None
                break
            except Exception as e:
                last_audio_error = e
                logger.warning("Audio attempt %d/%d failed: %s",
                               attempt + 1, MAX_AUDIO_RETRIES + 1, e)
            finally:
                await audio_gen.close()
            if attempt < MAX_AUDIO_RETRIES:
                wait = RETRY_BACKOFF_BASE ** (attempt + 1)
                logger.info("Retrying audio in %ds...", wait)
                await asyncio.sleep(wait)
        if last_audio_error is not None:
            raise last_audio_error
        job.audio_path = audio_path
        await self._update_stage(job, "generating_audio", "complete")
        return audio_path, audio_duration

    async def _generate_images(self, job: VideoJob, output_dir: str) -> list[str]:
        """Generate images for all scenes. Returns list of image paths."""
        await self._update_stage(job, "generating_images", "start")
        img_gen = self._image_generator_cls()

        async def on_image_progress(progress: float) -> None:
            job.stages["generating_images"].progress = progress
            job.update_progress()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))

        image_paths = await img_gen.generate_all(
            scenes=job.request.scene_suggestions,
            aspect_ratio=job.request.aspect_ratio,
            steps=settings.default_image_steps,
            performance=settings.default_image_performance,
            output_dir=output_dir,
            progress_callback=on_image_progress,
        )
        await img_gen.close()
        job.images = image_paths
        await self._update_stage(job, "generating_images", "complete")
        return image_paths

    async def _assemble_video(
        self, job: VideoJob, audio_path: str, image_paths: list[str], output_dir: str
    ) -> str:
        """Assemble final video from audio and images."""
        await self._update_stage(job, "assembling_video", "start")
        assembler = self._assembler_cls()
        final_video = await assembler.assemble(
            audio_path=audio_path,
            image_paths=image_paths,
            narration=job.request.narration,
            output_dir=output_dir,
            job_id=job.job_id,
            width=settings.default_width,
            height=settings.default_height,
            fps=settings.default_fps,
            zoom_style=job.request.zoom_style,
            crossfade_duration=settings.default_crossfade_duration,
            hook_text=job.request.hook,
            on_screen_text=[t.model_dump() for t in job.request.on_screen_text] or None,
            scene_suggestions=job.request.scene_suggestions,
        )
        await self._update_stage(job, "assembling_video", "complete")
        return final_video

    async def _notify_webhook(self, job: VideoJob) -> None:
        """Send webhook notification if configured."""
        if job.request.webhook_url:
            from app.api.webhook import send_webhook
            await send_webhook(job)

    async def _update_stage(self, job: VideoJob, stage: str, action: str) -> None:
        """Update stage status."""
        if stage not in job.stages:
            job.stages[stage] = StageInfo()

        stage_info = job.stages[stage]
        if isinstance(stage_info, dict):
            stage_info = StageInfo(**stage_info)
            job.stages[stage] = stage_info

        if action == "start":
            stage_info.start()
            job.status = VideoJobStatus(stage)
        elif action == "complete":
            stage_info.complete()

        job.update_progress()
        self.store.save_job(job.job_id, job.model_dump(mode="json"))

async def run_video_pipeline(job: VideoJob, pipeline: VideoPipeline | None = None) -> None:
    """Entry point for running the video pipeline."""
    pipeline = pipeline or VideoPipeline()
    await pipeline.run(job)
