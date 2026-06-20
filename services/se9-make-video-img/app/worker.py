"""Background worker for processing video jobs."""
from __future__ import annotations

import asyncio
from typing import Any

from common.log_utils import get_logger
import threading

from app.core.models import VideoJob, VideoJobStatus
from app.infrastructure.redis_store import VideoJobStore

logger = get_logger(__name__)

_worker_thread: threading.Thread | None = None
_stop_event = threading.Event()


class VideoWorker:
    """Worker that processes video jobs from the queue."""

    def __init__(self) -> None:
        self.store = VideoJobStore()
        self.running = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        """Start the worker in a background thread."""
        if self.running:
            return
        self.running = True
        _stop_event.clear()
        global _worker_thread
        _worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        _worker_thread.start()
        logger.info("Video worker started")

    def stop(self) -> None:
        """Stop the worker."""
        self.running = False
        _stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("Video worker stopped")

    def _run_loop(self) -> None:
        """Main worker loop with a persistent event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while self.running and not _stop_event.is_set():
            try:
                job = self._get_next_job()
                if job:
                    self._loop.run_until_complete(self._process_job(job))
                else:
                    _stop_event.wait(timeout=2)
            except Exception as e:
                logger.error("Worker error: %s", e, exc_info=True)
                _stop_event.wait(timeout=5)

        self._loop.close()

    def _get_next_job(self) -> VideoJob | None:
        """Get the next queued job from the store (efficient: stops at first match)."""
        job_data = self.store.get_next_queued_job()
        if job_data:
            return VideoJob(**job_data)
        return None

    async def _process_job(self, job: VideoJob) -> None:
        """Process a single video job."""
        logger.info("Processing job %s", job.job_id)
        try:
            from app.services.pipeline import run_video_pipeline
            await run_video_pipeline(job)
        except Exception as e:
            logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
            job.status = VideoJobStatus.FAILED
            job.error = str(e)
            self.store.save_job(job.job_id, job.model_dump(mode="json"))


_worker: VideoWorker | None = None


def get_worker() -> VideoWorker:
    """Get or create the singleton worker."""
    global _worker
    if _worker is None:
        _worker = VideoWorker()
    return _worker
