"""Pipeline orchestrator for video generation."""
import logging
import os
import shutil
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.core.models import (
    CreateVideoRequest,
    VideoJob,
    VideoJobStatus,
)
from app.infrastructure.redis_store import VideoJobStore
from app.services.audio_generator import AudioGenerator
from app.services.image_generator import ImageGenerator
from app.services.video_assembler import VideoAssembler

logger = logging.getLogger(__name__)


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
            audio_gen = AudioGenerator()
            audio_path, audio_duration = await audio_gen.generate(
                narration=job.request.narration,
                voice_id=job.request.voice_id,
                output_dir=temp_dir,
            )
            await audio_gen.close()
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
                width=1080,
                height=1920,
                fps=settings.default_fps,
                zoom_style=job.request.zoom_style,
                crossfade_duration=settings.default_crossfade_duration,
            )
            job.video_path = video_path
            await self._update_stage(job, "assembling_video", "complete")

            job.status = VideoJobStatus.COMPLETED
            job.progress = 100.0
            job.updated_at = datetime.now()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            logger.info(f"Job {job.job_id} completed successfully")

            if job.request.webhook_url:
                await self._send_webhook(job)

        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)
            job.status = VideoJobStatus.FAILED
            job.error = str(e)
            job.updated_at = datetime.now()
            self.store.save_job(job.job_id, job.model_dump(mode="json"))
            raise

        finally:
            self._cleanup_temp(temp_dir)

    async def _update_stage(self, job: VideoJob, stage: str, action: str) -> None:
        """Update stage status."""
        if stage not in job.stages:
            job.stages[stage] = {"status": "pending", "progress": 0}

        if action == "start":
            job.stages[stage]["status"] = "processing"
            job.stages[stage]["started_at"] = datetime.now().isoformat()
            job.status = VideoJobStatus(stage)
        elif action == "complete":
            job.stages[stage]["status"] = "completed"
            job.stages[stage]["progress"] = 100.0
            job.stages[stage]["completed_at"] = datetime.now().isoformat()

        job.update_progress()
        self.store.save_job(job.job_id, job.model_dump(mode="json"))

    async def _send_webhook(self, job: VideoJob) -> None:
        """Send webhook notification when video is ready."""
        import httpx

        payload = {
            "event": "video_ready",
            "job_id": job.job_id,
            "post_id": job.request.post_id,
            "status": "completed",
            "download_url": f"http://localhost:{settings.port}/download/{job.job_id}",
            "hashtags": job.request.hashtags,
            "duration_seconds": job.request.estimated_seconds,
        }
        if job.request.title_options:
            payload["title"] = job.request.title_options[0]

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(job.request.webhook_url, json=payload)
                logger.info(f"Webhook sent to {job.request.webhook_url}")
        except Exception as e:
            logger.warning(f"Webhook failed: {e}")

    def _cleanup_temp(self, temp_dir: str) -> None:
        """Remove temporary directory."""
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp dir: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")


async def run_video_pipeline(job: VideoJob) -> None:
    """Entry point for running the video pipeline."""
    pipeline = VideoPipeline()
    await pipeline.run(job)
