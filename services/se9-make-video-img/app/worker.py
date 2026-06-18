"""Background worker for processing video jobs."""
import asyncio
import logging
import threading
from typing import Optional

from app.core.models import VideoJob, VideoJobStatus
from app.infrastructure.redis_store import VideoJobStore

logger = logging.getLogger(__name__)

_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


class VideoWorker:
    """Worker that processes video jobs from the queue."""

    def __init__(self):
        self.store = VideoJobStore()
        self.running = False

    def start(self):
        """Start the worker in a background thread."""
        if self.running:
            return
        self.running = True
        _stop_event.clear()
        global _worker_thread
        _worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        _worker_thread.start()
        logger.info("Video worker started")

    def stop(self):
        """Stop the worker."""
        self.running = False
        _stop_event.set()
        logger.info("Video worker stopped")

    def _run_loop(self):
        """Main worker loop."""
        while self.running and not _stop_event.is_set():
            try:
                job = self._get_next_job()
                if job:
                    self._process_job(job)
                else:
                    _stop_event.wait(timeout=2)
            except Exception as e:
                logger.error(f"Worker error: {e}", exc_info=True)
                _stop_event.wait(timeout=5)

    def _get_next_job(self) -> Optional[VideoJob]:
        """Get the next queued job from the store."""
        jobs = self.store.list_jobs()
        for job_data in jobs:
            if job_data.get("status") == VideoJobStatus.QUEUED.value:
                return VideoJob(**job_data)
        return None

    def _process_job(self, job: VideoJob):
        """Process a single video job."""
        logger.info(f"Processing job {job.job_id}")
        try:
            asyncio.run(self._run_pipeline(job))
        except Exception as e:
            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)
            job.status = VideoJobStatus.FAILED
            job.error = str(e)
            self.store.save_job(job.job_id, job.model_dump(mode="json"))

    async def _run_pipeline(self, job: VideoJob):
        """Run the video generation pipeline."""
        from app.services.pipeline import run_video_pipeline
        await run_video_pipeline(job)


_worker: Optional[VideoWorker] = None


def get_worker() -> VideoWorker:
    """Get or create the singleton worker."""
    global _worker
    if _worker is None:
        _worker = VideoWorker()
    return _worker
