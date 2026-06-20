"""Pipeline orchestrator for video generation."""
import asyncio
from common.log_utils import get_logger
import os
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

logger = get_logger(__name__)

MAX_AUDIO_RETRIES = 3
RETRY_BACKOFF_BASE = 2


class VideoPipeline:
    """Orchestrate the full video generation pipeline."""

    def __init__(self):
        self.store = VideoJobStore()

    async def run(self, job: VideoJob) -> None:
        """Run the complete pipeline for a video job.

        All artifacts (audio, images, intermediates, final video) are stored
        in output/{job_id}/.
        """
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        try:
            await self._update_stage(job, "generating_audio", "start")
            audio_path, audio_duration = None, 0.0
            last_audio_error = None
            for attempt in range(MAX_AUDIO_RETRIES + 1):
                audio_gen = AudioGenerator()
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
                output_dir=output_dir,
                progress_callback=on_image_progress,
            )
            await img_gen.close()
            job.images = image_paths
            await self._update_stage(job, "generating_images", "complete")

            await self._update_stage(job, "assembling_video", "start")
            assembler = VideoAssembler()
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
            )
            job.video_path = final_video
            await self._update_stage(job, "assembling_video", "complete")

            job.status = VideoJobStatus.COMPLETED
            job.progress = 100.0
            job.updated_at = now_brazil()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            logger.info("Job %s completed: %s", job.job_id, final_video)

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

async def run_video_pipeline(job: VideoJob) -> None:
    """Entry point for running the video pipeline."""
    pipeline = VideoPipeline()
    await pipeline.run(job)
