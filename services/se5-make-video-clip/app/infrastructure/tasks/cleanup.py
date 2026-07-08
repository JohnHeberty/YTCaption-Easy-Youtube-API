"""Cleanup tasks."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

from ..celery_config import celery_app
from ...core.config import get_settings
from ...core.models import JobStatus
from ..instances import get_instances

logger = get_logger(__name__)


@celery_app.task(name='app.infrastructure.celery_tasks.cleanup_temp_files')
def cleanup_temp_files() -> None:
    """Limpa arquivos temporários antigos"""
    logger.info("🧹 Running temp files cleanup...")

    settings = get_settings()
    temp_dir = Path('/tmp/make-video-temp')
    cutoff_hours = settings['cleanup_temp_after_hours']

    if not temp_dir.exists():
        return

    cutoff_time = now_brazil() - timedelta(hours=cutoff_hours)
    removed_count = 0

    for job_dir in temp_dir.iterdir():
        if job_dir.is_dir():
            try:
                job_id = job_dir.name
                store, _, _, _, _ = get_instances()
                loop = asyncio.get_event_loop()
                job = store.get_job(job_id)

                if job and job.status not in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    logger.info(f"⏭️ Skipping active job: {job_id}")
                    continue
            except Exception as e:
                logger.debug(f"Could not check job status for {job_id}: {e}")

            mtime = datetime.fromtimestamp(job_dir.stat().st_mtime)
            if mtime < cutoff_time:
                try:
                    import shutil
                    shutil.rmtree(job_dir)
                    removed_count += 1
                    logger.info(f"🗑️ Removed temp dir: {job_dir.name}")
                except Exception as e:
                    logger.error(f"Error removing {job_dir}: {e}")

    logger.info(f"✅ Cleanup complete: {removed_count} temp directories removed")


@celery_app.task(name='app.infrastructure.celery_tasks.cleanup_old_shorts')
def cleanup_old_shorts() -> None:
    """Limpa shorts não usados há muito tempo"""
    logger.info("🧹 Running shorts cache cleanup...")

    settings = get_settings()
    _, _, _, shorts_cache, _ = get_instances()

    days = settings['cleanup_shorts_cache_after_days']
    removed_count = shorts_cache.cleanup_old(days=days)

    logger.info(f"✅ Cleanup complete: {removed_count} old shorts removed")
