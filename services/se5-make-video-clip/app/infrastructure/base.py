"""Shared job status update utility."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from common.datetime_utils import now_brazil
from common.log_utils import get_logger
from ..core.models import JobStatus
from ..core.constants import (
    STATUS_UPDATE_MAX_RETRIES,
    STATUS_UPDATE_RETRY_DELAY,
    COMPLETED_JOB_EXPIRY_HOURS,
)

logger = get_logger(__name__)


async def update_job_status(
    job_id: str,
    status: JobStatus,
    progress: float | None = None,
    stage_updates: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None
) -> None:
    """Atualiza status do job no Redis com retry automático"""
    from .instances import get_instances
    store, _, _, _, _ = get_instances()

    max_retries = STATUS_UPDATE_MAX_RETRIES
    retry_delay = STATUS_UPDATE_RETRY_DELAY

    for attempt in range(1, max_retries + 1):
        try:
            job = store.get_job(job_id)
            if not job:
                logger.error(f"Job {job_id} not found for status update")
                return

            job.status = status

            if progress is not None:
                job.progress = progress

            if stage_updates:
                for stage_name, stage_info in stage_updates.items():
                    if stage_name not in job.stages:
                        from app.core.models import StageInfo
                        job.stages[stage_name] = StageInfo(**stage_info)
                    else:
                        existing_stage = job.stages[stage_name]
                        for key, value in stage_info.items():
                            if key == 'metadata' and hasattr(existing_stage, 'metadata'):
                                existing_stage.metadata.update(value)
                            else:
                                setattr(existing_stage, key, value)

            if error:
                job.error = error

            if status == JobStatus.COMPLETED:
                job.completed_at = now_brazil()
                job.expires_at = job.completed_at + timedelta(hours=COMPLETED_JOB_EXPIRY_HOURS)

            store.save_job(job)

            if attempt > 1:
                logger.info(f"✅ Status update succeeded on attempt {attempt}")
            return

        except Exception as e:
            if attempt < max_retries:
                logger.warning(
                    f"⚠️ Failed to update job status (attempt {attempt}/{max_retries}): {e}",
                    extra={"job_id": job_id, "status": status.value, "progress": progress}
                )
                await asyncio.sleep(retry_delay * attempt)
            else:
                logger.error(
                    f"❌ CRITICAL: Failed to update job status after {max_retries} attempts: {e}",
                    exc_info=True,
                    extra={
                        "job_id": job_id,
                        "status": status.value,
                        "progress": progress,
                        "error": str(e)
                    }
                )
