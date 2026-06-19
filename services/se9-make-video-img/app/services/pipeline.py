"""Pipeline orchestrator for video generation."""
import asyncio
import logging
import os
import shutil
from typing import Optional

from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import (
    CreateVideoRequest,
    StageInfo,
    StageStatus,
    VideoJob,
    VideoJobStatus,
)
from app.infrastructure.redis_store import VideoJobStore
from app.services.audio_generator import AudioGenerator
from app.services.image_generator import ImageGenerator
from app.services.video_assembler import VideoAssembler

logger = logging.getLogger(__name__)

MAX_AUDIO_RETRIES = 2
RETRY_BACKOFF_BASE = 10


class VideoPipeline:
    """Orchestrate the full video generation pipeline."""

    def __init__(self):
        self.store = VideoJobStore()

    async def run(self, job: VideoJob) -> None:
        """Run the complete pipeline for a video job."""
        temp_dir = os.path.join(settings.temp_dir, f"rbg_{job.job_id}")
        os.makedirs(temp_dir, exist_ok=True)

        try:
            await self._update_stage(job, "generating_audio", "start")
            audio_path, audio_duration = None, 0.0
            for attempt in range(MAX_AUDIO_RETRIES + 1):
                audio_gen = AudioGenerator()
                try:
                    audio_path, audio_duration = await audio_gen.generate(
                        narration=job.request.narration,
                        voice_id=job.request.voice_id,
                        output_dir=temp_dir,
                    )
                    break
                finally:
                    await audio_gen.close()
                if attempt < MAX_AUDIO_RETRIES:
                    wait = RETRY_BACKOFF_BASE * (attempt + 1)
                    logger.warning("Audio generation failed, retry %d/%d in %ds",
                                   attempt + 1, MAX_AUDIO_RETRIES, wait)
                    await asyncio.sleep(wait)
            job.audio_path = audio_path
            await self._update_stage(job, "generating_audio", "complete")

            await self._update_stage(job, "generating_images", "start")
            img_gen = ImageGenerator()

            async def on_image_progress(progress: float):
                job.stages["generating_images"].progress = progress
                job.update_progress()
                self.store.save_job(job.job_id, job.model_dump(mode="json"))

            image_paths = await img_gen.generate_all(
                scenes=job.request.scene_suggestions,
                aspect_ratio=job.request.aspect_ratio,
                steps=settings.default_image_steps,
                performance=settings.default_image_performance,
                output_dir=temp_dir,
                progress_callback=on_image_progress,
            )
            await img_gen.close()
            job.images = image_paths
            await self._update_stage(job, "generating_images", "complete")

            await self._update_stage(job, "assembling_video", "start")
            assembler = VideoAssembler()
            video_path = await assembler.assemble(
                audio_path=audio_path,
                image_paths=image_paths,
                narration=job.request.narration,
                on_screen_text=job.request.on_screen_text,
                output_dir=temp_dir,
                width=settings.default_width,
                height=settings.default_height,
                fps=settings.default_fps,
                zoom_style=job.request.zoom_style,
                crossfade_duration=settings.default_crossfade_duration,
            )
            job.video_path = video_path
            await self._update_stage(job, "assembling_video", "complete")

            job.status = VideoJobStatus.COMPLETED
            job.progress = 100.0
            job.updated_at = now_brazil()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            logger.info("Job %s completed successfully", job.job_id)

            if job.request.webhook_url:
                from app.api.webhook import send_webhook
                await send_webhook(job)

        except Exception as e:
            logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
            job.status = VideoJobStatus.FAILED
            job.error = str(e)
            job.updated_at = now_brazil()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            raise

        finally:
            self._cleanup_temp(temp_dir)

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

    def _cleanup_temp(self, temp_dir: str) -> None:
        """Remove temporary directory."""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.debug("Cleaned up temp dir: %s", temp_dir)
        except Exception as e:
            logger.warning("Failed to cleanup temp dir %s: %s", temp_dir, e)


async def run_video_pipeline(job: VideoJob) -> None:
    """Entry point for running the video pipeline."""
    pipeline = VideoPipeline()
    await pipeline.run(job)
