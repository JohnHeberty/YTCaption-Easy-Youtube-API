"""Celery tasks for SE8 Image Engine.

The GPU worker runs directly inside this process.
"""

from __future__ import annotations
from common.log_utils import get_logger

import time
from typing import Any

from app.infrastructure.celery_config import celery_app

logger = get_logger(__name__)


def _init_worker() -> None:
    """Initialize the GPU worker on first task."""
    import torch
    from app.services.model_manager import get_model_manager
    from app.services.pipeline import get_pipeline
    from app.services.task_queue import TaskQueue
    import app.services.worker as worker_module

    # Set up task queue if not already set
    if worker_module.worker_queue is None:
        worker_module.worker_queue = TaskQueue(
            queue_size=100,
            history_size=64,
        )

    # Load pipeline if GPU available
    mm = get_model_manager()
    if mm.is_gpu_available():
        logger.info("GPU detected: %s (%.0f MB VRAM)", mm.device_name, mm.total_vram_mb)
        try:
            pipeline = get_pipeline()
            logger.info("Pipeline initialized successfully")
        except Exception as e:
            logger.warning("Pipeline init deferred: %s", e)
    else:
        logger.warning("No GPU detected — generation will fail")


@celery_app.task(
    name="app.infrastructure.celery_tasks.generate_image",
    bind=True,
    max_retries=0,
)
def generate_image(self, request_params: dict[str, Any]) -> dict[str, Any]:
    """Process an image generation request.

    Args:
        request_params: Full request parameters (prompt, negative_prompt, loras, etc.)

    Returns:
        Dict with job_id, status, results.
    """
    import uuid
    import app.services.worker as worker_module
    from app.domain.task_models import QueueTask, TaskType

    _init_worker()

    job_id = str(uuid.uuid4())
    task_type = worker_module._detect_task_type(request_params)

    task = QueueTask(
        job_id=job_id,
        task_type=task_type,
        req_param=request_params,
    )

    logger.info("Task %s started (type=%s)", job_id, task_type.value)
    start = time.time()

    try:
        worker_module.process_generate(task)
        elapsed = time.time() - start
        logger.info("Task %s completed in %.1fs", job_id, elapsed)

        results = []
        if task.task_result:
            for r in task.task_result:
                results.append({
                    "url": r.im,
                    "seed": r.seed,
                    "finish_reason": r.finish_reason.value,
                })

        return {
            "job_id": job_id,
            "status": "SUCCESS" if not task.finish_with_error else "ERROR",
            "results": results,
            "elapsed_seconds": round(elapsed, 2),
        }

    except Exception as e:
        elapsed = time.time() - start
        logger.exception("Task %s failed after %.1fs: %s", job_id, elapsed, e)
        return {
            "job_id": job_id,
            "status": "ERROR",
            "error": str(e),
            "elapsed_seconds": round(elapsed, 2),
        }


@celery_app.task(
    name="app.infrastructure.celery_tasks.stop_generation",
    bind=True,
)
def stop_generation(self) -> dict[str, str]:
    """Stop the current generation."""
    from app.services.worker import process_stop
    process_stop()
    return {"status": "stopped"}


@celery_app.task(
    name="app.infrastructure.celery_tasks.cleanup_expired_jobs",
)
def cleanup_expired_jobs() -> dict[str, Any]:
    """Clean up expired jobs from the history."""
    import app.services.worker as worker_module
    if worker_module.worker_queue is None:
        return {"status": "ok", "cleaned": 0}

    queue = worker_module.worker_queue
    now = int(time.time() * 1000)
    max_age = 24 * 60 * 60 * 1000  # 24 hours

    cleaned = 0
    expired = [
        t for t in queue.history
        if t.is_finished and (now - t.finish_mills) > max_age
    ]
    for task in expired:
        queue.history.remove(task)
        queue._cleanup_output_files(task)
        cleaned += 1

    logger.info("Cleaned %d expired jobs", cleaned)
    return {"status": "ok", "cleaned": cleaned}
