"""Task queue for SE8 Image Engine.

FIFO queue with history tracking, webhook support, and status management.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.domain.task_models import (
    AsyncTask,
    GenerationFinishReason,
    ImageGenerationResult,
    QueueTask,
    TaskOutputs,
    TaskType,
)

logger = logging.getLogger(__name__)


class TaskQueue:
    """FIFO task queue with history, webhooks, and concurrency control."""

    def __init__(
        self,
        queue_size: int = 100,
        history_size: int = 64,
        webhook_url: Optional[str] = None,
        persistent: bool = False,
    ) -> None:
        self.queue_size = queue_size
        self.history_size = history_size
        self.webhook_url = webhook_url
        self.persistent = persistent

        self.queue: List[QueueTask] = []
        self.history: List[QueueTask] = []
        self.last_job_id: Optional[str] = None

    def add_task(
        self,
        task_type: TaskType,
        req_param: Dict[str, Any],
        webhook_url: Optional[str] = None,
    ) -> Optional[QueueTask]:
        """Add a task to the queue. Returns None if queue is full."""
        if len(self.queue) >= self.queue_size:
            logger.warning("Task queue full (%d/%d)", len(self.queue), self.queue_size)
            return None

        job_id = str(uuid.uuid4())
        task = QueueTask(
            job_id=job_id,
            task_type=task_type,
            req_param=req_param,
            webhook_url=webhook_url,
        )
        self.queue.append(task)
        self.last_job_id = job_id
        logger.info("Task added: %s (type=%s, queue=%d)", job_id, task_type.value, len(self.queue))
        return task

    def get_task(self, job_id: str, include_history: bool = False) -> Optional[QueueTask]:
        """Find a task by ID. Optionally search history."""
        for task in self.queue:
            if task.job_id == job_id:
                return task
        if include_history:
            for task in self.history:
                if task.job_id == job_id:
                    return task
        return None

    def is_task_ready_to_start(self, job_id: str) -> bool:
        """Check if task is at the front of the queue."""
        if not self.queue:
            return False
        return self.queue[0].job_id == job_id

    def is_task_finished(self, job_id: str) -> bool:
        """Check if task has finished processing."""
        task = self.get_task(job_id, include_history=True)
        return task is not None and task.is_finished

    def start_task(self, job_id: str) -> None:
        """Mark task as started."""
        task = self.get_task(job_id)
        if task is not None:
            task.start_mills = int(time.time() * 1000)
            logger.info("Task started: %s", job_id)

    def finish_task(self, job_id: str) -> None:
        """Finish a task: send webhook, move to history, clean up."""
        task = self.get_task(job_id)
        if task is None:
            return

        task.is_finished = True
        task.finish_mills = int(time.time() * 1000)

        # Send webhook
        webhook = task.webhook_url or self.webhook_url
        if webhook and task.task_result:
            self._send_webhook(webhook, task)

        # Move to history
        if task in self.queue:
            self.queue.remove(task)
        self.history.append(task)

        # Trim history
        while len(self.history) > self.history_size:
            old = self.history.pop(0)
            self._cleanup_output_files(old)

        logger.info("Task finished: %s (error=%s)", job_id, task.finish_with_error)

    def get_queue_info(self) -> Dict[str, Any]:
        """Return queue status info."""
        return {
            "running_size": len(self.queue),
            "finished_size": len(self.history),
            "last_job_id": self.last_job_id,
        }

    def get_history(
        self,
        job_id: Optional[str] = None,
        page: int = 0,
        page_size: int = 20,
        delete: bool = False,
    ) -> Dict[str, Any]:
        """Query history. Optionally filter by job_id, paginate, or delete."""
        if delete and job_id:
            task = self.get_task(job_id, include_history=True)
            if task and task in self.history:
                self.history.remove(task)
                self._cleanup_output_files(task)
                return {"deleted": job_id}

        tasks = self.history
        if job_id:
            tasks = [t for t in tasks if t.job_id == job_id]

        start = page * page_size
        end = start + page_size
        page_tasks = tasks[start:end]

        return {
            "queue": [
                {
                    "job_id": t.job_id,
                    "in_queue_mills": t.in_queue_mills,
                    "start_mills": t.start_mills,
                    "finish_mills": t.finish_mills,
                    "is_finished": t.is_finished,
                }
                for t in self.queue
            ],
            "history": [
                {
                    "job_id": t.job_id,
                    "in_queue_mills": t.in_queue_mills,
                    "start_mills": t.start_mills,
                    "finish_mills": t.finish_mills,
                    "is_finished": t.is_finished,
                }
                for t in page_tasks
            ],
        }

    def _send_webhook(self, url: str, task: QueueTask) -> None:
        """POST task result to webhook URL."""
        try:
            results = []
            if task.task_result:
                for r in task.task_result:
                    results.append({
                        "url": r.im or "",
                        "seed": r.seed,
                    })
            payload = {
                "job_id": task.job_id,
                "job_result": results,
            }
            httpx.post(url, json=payload, timeout=15.0)
            logger.info("Webhook sent for task %s to %s", task.job_id, url)
        except Exception as e:
            logger.warning("Webhook failed for task %s: %s", task.job_id, e)

    def _cleanup_output_files(self, task: QueueTask) -> None:
        """Remove output files for a finished task."""
        if not task.task_result:
            return
        for result in task.task_result:
            if result.im:
                try:
                    path = Path(result.im)
                    if path.exists():
                        os.remove(str(path))
                except Exception:
                    pass
