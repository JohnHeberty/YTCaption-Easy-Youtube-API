"""Webhook notification sender."""
import logging

import httpx

from app.core.config import settings
from app.core.models import VideoJob

logger = logging.getLogger(__name__)


async def send_webhook(job: VideoJob) -> None:
    """Send webhook notification when video is ready."""
    if not job.request.webhook_url:
        return

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
