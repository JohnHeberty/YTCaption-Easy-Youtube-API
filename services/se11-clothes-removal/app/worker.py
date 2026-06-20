"""Background worker for processing clothes removal jobs."""
import asyncio
import threading
from typing import Optional

from common.log_utils import get_logger

from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.redis_store import ClothesRemovalJobStore

logger = get_logger(__name__)

_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


class ClothesRemovalWorker:
    """Worker that processes clothes removal jobs from the queue."""

    def __init__(self):
        self.store = ClothesRemovalJobStore()
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self):
        """Start the worker in a background thread."""
        if self.running:
            return
        self.running = True
        _stop_event.clear()
        global _worker_thread
        _worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        _worker_thread.start()
        logger.info("Clothes removal worker started")

    def stop(self):
        """Stop the worker."""
        self.running = False
        _stop_event.set()
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        logger.info("Clothes removal worker stopped")

    def _run_loop(self):
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

    def _get_next_job(self) -> Optional[ClothesRemovalJob]:
        """Get the next queued job from the store."""
        jobs = self.store.list_jobs()
        for job_data in jobs:
            if job_data.get("status") == ClothesRemovalJobStatus.QUEUED.value:
                return ClothesRemovalJob(**job_data)
        return None

    async def _process_job(self, job: ClothesRemovalJob):
        """Process a single clothes removal job."""
        logger.info("Processing job %s", job.job_id)
        try:
            from app.services.pipeline import run_clothes_removal
            await run_clothes_removal(job, self.store)
        except Exception as e:
            logger.error("Job %s failed: %s", job.job_id, e, exc_info=True)
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = str(e)
            self.store.save_job(job.job_id, job.model_dump(mode="json"))


_worker: Optional[ClothesRemovalWorker] = None


def get_worker() -> ClothesRemovalWorker:
    """Get or create the singleton worker."""
    global _worker
    if _worker is None:
        _worker = ClothesRemovalWorker()
    return _worker
