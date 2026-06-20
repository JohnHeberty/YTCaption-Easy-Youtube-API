"""Webhook notification sender with exponential backoff retry."""
import asyncio
from common.log_utils import get_logger

import httpx

from app.core.config import settings
from app.core.models import VideoJob

logger = get_logger(__name__)

WEBHOOK_MAX_RETRIES = 3
WEBHOOK_BACKOFF_BASE = 2


async def send_webhook(job: VideoJob) -> None:
    """Send webhook notification when video is ready.

    Retries up to 3 times with exponential backoff (2s, 4s, 8s).
    """
    if not job.request.webhook_url:
        return

    external_url = settings.external_url or f"http://localhost:{settings.port}"

    payload = {
        "event": "video_ready",
        "job_id": job.job_id,
        "post_id": job.request.post_id,
        "status": "completed",
        "download_url": f"{external_url}/download/{job.job_id}",
        "hashtags": job.request.hashtags,
        "duration_seconds": job.request.estimated_seconds,
    }
    if job.request.title_options:
        payload["title"] = job.request.title_options[0]

    last_error = None
    for attempt in range(WEBHOOK_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(job.request.webhook_url, json=payload)
                resp.raise_for_status()
                logger.info("Webhook sent to %s (attempt %d)", job.request.webhook_url, attempt + 1)
                return
        except Exception as e:
            last_error = e
            if attempt < WEBHOOK_MAX_RETRIES - 1:
                wait = WEBHOOK_BACKOFF_BASE ** (attempt + 1)
                logger.warning("Webhook attempt %d/%d failed: %s — retrying in %ds",
                               attempt + 1, WEBHOOK_MAX_RETRIES, e, wait)
                await asyncio.sleep(wait)

    logger.error("Webhook failed after %d attempts to %s: %s",
                 WEBHOOK_MAX_RETRIES, job.request.webhook_url, last_error)
