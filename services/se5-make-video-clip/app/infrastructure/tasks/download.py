"""Download pipeline task."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..celery_config import celery_app
from ...core.config import get_settings
from ...core.models import JobStatus
from ...shared.exceptions import MakeVideoException
from ..instances import get_instances
from ..base import update_job_status
from ..checkpoint import save_checkpoint, delete_checkpoint
from ..helpers import transform_crop_and_validate_video
from ..file_logger import FileLogger

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name='app.infrastructure.celery_tasks.process_download_pipeline',
    time_limit=7200,
    soft_time_limit=6600,
    acks_late=True,
    reject_on_worker_lost=True
)
def process_download_pipeline(self, job_id: str) -> None:
    """Task: Pipeline completo de download e validacao de shorts."""
    logger.info(f"🚀 Starting download pipeline: {job_id}")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_process_download_pipeline_async(job_id))
    except Exception as e:
        logger.error(f"❌ Download pipeline {job_id} failed: {e}", exc_info=True)
        try:
            store, _, _, _, _ = get_instances()
            existing_job = store.get_job(job_id)
            if existing_job and existing_job.status == JobStatus.FAILED and existing_job.error:
                return
            loop.run_until_complete(update_job_status(
                job_id, JobStatus.FAILED, progress=0.0,
                error={"message": str(e), "type": type(e).__name__, "stage": "unknown"}
            ))
        except Exception:
            pass


async def _search_shorts(
    api_client: Any,
    query: str,
    max_shorts: int,
    job_id: str,
    job_logger: Any,
) -> list[dict[str, Any]]:
    """Search for shorts via the API. Returns list of search results."""
    job_logger.info(f"🔍 [1/3] Searching shorts for '{query}'...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=10.0)

    results = await api_client.search_shorts(query, max_results=max_shorts)
    if not results:
        raise MakeVideoException(f"No shorts found for query '{query}'")

    job_logger.info(f"✅ Found {len(results)} shorts")
    await save_checkpoint(job_id, "searching_shorts_completed")
    return results


async def _download_shorts(
    api_client: Any,
    results: list[dict[str, Any]],
    job_id: str,
    job_logger: Any,
) -> list[str]:
    """Download shorts from search results. Returns list of downloaded video IDs."""
    job_logger.info(f"⬇️ [2/3] Downloading {len(results)} shorts...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=25.0)

    from app.pipeline.video_pipeline import VideoPipeline
    pipeline = VideoPipeline()
    pipeline.cleanup_stale_validations(job_id, max_age_minutes=30)

    raw_dir = Path("data/raw/shorts")
    raw_dir.mkdir(parents=True, exist_ok=True)

    downloaded_ids: list[str] = []
    total = len(results)

    for i, item in enumerate(results):
        video_id = item.get('video_id', item.get('id', ''))
        if not video_id:
            continue

        output_path = str(raw_dir / f"{video_id}.mp4")
        try:
            await api_client.download_video(video_id, output_path)
            downloaded_ids.append(video_id)

            progress = 25.0 + (i + 1) / total * 25.0
            if (i + 1) % 5 == 0 or (i + 1) == total:
                await update_job_status(job_id, JobStatus.PROCESSING, progress=progress)

        except Exception as e:
            logger.warning(f"⚠️ Failed to download {video_id}: {e}")
            job_logger.warning(f"⚠️ Failed to download {video_id}: {e}")

    job_logger.info(f"✅ Downloaded {len(downloaded_ids)}/{total} shorts")
    await save_checkpoint(job_id, "load_approved_completed")

    if not downloaded_ids:
        raise MakeVideoException("No shorts were downloaded successfully")

    return downloaded_ids


async def _validate_downloaded_shorts(
    downloaded_ids: list[str],
    job_id: str,
    aspect_ratio: str,
    crop_position: str,
    video_builder: Any,
    job_logger: Any,
) -> tuple[list[str], list[str]]:
    """Validate each downloaded video. Returns (approved_ids, rejected_ids)."""
    job_logger.info(f"🔍 [3/3] Validating {len(downloaded_ids)} shorts...")
    await update_job_status(job_id, JobStatus.PROCESSING, progress=55.0)

    from .. import instances
    if instances.video_validator is None or instances.blacklist is None:
        get_instances()

    raw_dir = Path("data/raw/shorts")
    approved_ids: list[str] = []
    rejected_ids: list[str] = []
    total_to_validate = len(downloaded_ids)

    for i, video_id in enumerate(downloaded_ids):
        raw_path = raw_dir / f"{video_id}.mp4"
        if not raw_path.exists():
            continue

        job_logger.info(f"   Validating {video_id} ({i+1}/{total_to_validate})...")

        final_path = await transform_crop_and_validate_video(
            video_id=video_id,
            raw_video_path=str(raw_path),
            job_id=job_id,
            aspect_ratio=aspect_ratio,
            crop_position=crop_position,
            video_builder=video_builder,
            video_validator=instances.video_validator,
            blacklist=instances.blacklist,
            job_logger=job_logger,
        )

        if final_path:
            approved_ids.append(video_id)
        else:
            rejected_ids.append(video_id)

        progress = 55.0 + (i + 1) / total_to_validate * 40.0
        if (i + 1) % 5 == 0 or (i + 1) == total_to_validate:
            await update_job_status(
                job_id, JobStatus.PROCESSING, progress=progress,
                stage_updates={
                    "validating_shorts": {
                        "status": "processing",
                        "metadata": {
                            "approved": len(approved_ids),
                            "rejected": len(rejected_ids),
                            "total_validated": i + 1,
                        }
                    }
                }
            )

    job_logger.info(f"📊 Validation results:")
    job_logger.info(f"   ├─ Approved: {len(approved_ids)}")
    job_logger.info(f"   ├─ Rejected: {len(rejected_ids)}")
    job_logger.info(f"   └─ Total downloaded: {len(downloaded_ids)}")

    return approved_ids, rejected_ids


async def _process_download_pipeline_async(job_id: str) -> None:
    """Async implementation of download pipeline."""
    from .. import instances

    store, api_client, video_builder, shorts_cache, subtitle_gen = get_instances()
    settings = get_settings()
    job_logger = FileLogger.get_job_logger(job_id)

    job = store.get_job(job_id)
    if not job:
        raise MakeVideoException(f"Job {job_id} not found")

    query = job.query or "motivation"
    max_shorts = job.max_shorts or 50

    job_logger.info("="*80)
    job_logger.info(f"🚀 STARTING DOWNLOAD PIPELINE: {job_id}")
    job_logger.info(f"   Query: '{query}', Max shorts: {max_shorts}")
    job_logger.info("="*80)

    await update_job_status(job_id, JobStatus.PROCESSING, progress=5.0)

    # Step 1: Search
    results = await _search_shorts(api_client, query, max_shorts, job_id, job_logger)

    # Step 2: Download
    downloaded_ids = await _download_shorts(api_client, results, job_id, job_logger)

    # Step 3: Validate
    aspect_ratio = job.aspect_ratio or "9:16"
    crop_position = job.crop_position or "center"
    approved_ids, rejected_ids = await _validate_downloaded_shorts(
        downloaded_ids, job_id, aspect_ratio, crop_position, video_builder, job_logger
    )

    # Finalize job
    job.status = JobStatus.COMPLETED
    job.progress = 100.0
    job.completed_at = now_brazil()
    job.expires_at = job.completed_at + timedelta(hours=24)

    job.result = {
        "query": query,
        "total_found": len(results),
        "total_downloaded": len(downloaded_ids),
        "approved_count": len(approved_ids),
        "rejected_count": len(rejected_ids),
        "approved_videos": approved_ids,
        "rejected_videos": rejected_ids,
    }
    store.save_job(job)

    await delete_checkpoint(job_id)

    logger.info(f"🎉 Download pipeline {job_id} completed: {len(approved_ids)} approved")
    job_logger.info(f"🎉 DOWNLOAD PIPELINE COMPLETED: {len(approved_ids)} videos approved")
