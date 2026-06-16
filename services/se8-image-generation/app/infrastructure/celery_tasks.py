import time

from celery import shared_task

from app.infrastructure.celery_config import celery_app
from app.services.image_service import fooocus_client
from common.log_utils import get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.infrastructure.celery_tasks.generate_image", bind=True, max_retries=2)
def generate_image(self, prompt: str, negative_prompt: str = "", performance: str = None,
                   width: int = 1024, height: int = 1024, image_number: int = 1,
                   seed: int = -1):
    import asyncio

    logger.info("generate_image task started | prompt=%s", prompt[:50])
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            fooocus_client.text_to_image(
                prompt=prompt,
                negative_prompt=negative_prompt,
                performance=performance,
                aspect_ratios_selection=f"{width}×{height}",
                image_number=image_number,
                seed=seed,
                async_process=False,
            )
        )
        loop.close()
        logger.info("generate_image task completed")
        return result
    except Exception as exc:
        logger.error("generate_image task failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="app.infrastructure.celery_tasks.cleanup_expired_jobs")
def cleanup_expired_jobs():
    logger.info("cleanup_expired_jobs running")
    return {"status": "ok", "cleaned": 0}
