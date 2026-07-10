"""Task queue for SE8 Image Engine.

FIFO queue with history tracking, webhook support, and status management.

Architecture:
- Queue (active tasks): In-memory list — fast FIFO for GPU worker polling
- History (completed tasks): Redis-backed via ResilientRedisStore — survives restarts
- Metadata only in Redis — req_param (large base64 images) stays in-memory
"""

from __future__ import annotations
from common.log_utils import get_logger

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from app.domain.task_models import (
    AsyncTask,
    GenerationFinishReason,
    ImageGenerationResult,
    QueueTask,
    TaskOutputs,
    TaskType,
)

logger = get_logger(__name__)

HISTORY_KEY_PREFIX = "se8:history"
HISTORY_LIST_KEY = "se8:history:list"
HISTORY_TTL_SECONDS = 86400  # 24 hours


def _task_to_metadata(task: QueueTask) -> dict[str, Any]:
    """Extract lightweight metadata from a QueueTask for Redis storage.

    Excludes req_param (can contain MBs of base64 images) and task_step_preview.
    """
    result_data = None
    if task.task_result:
        result_data = [
            {"im": r.im, "seed": r.seed, "finish_reason": r.finish_reason.value}
            for r in task.task_result
        ]

    return {
        "job_id": task.job_id,
        "task_type": task.task_type.value,
        "webhook_url": task.webhook_url,
        "is_finished": task.is_finished,
        "finish_progress": task.finish_progress,
        "in_queue_mills": task.in_queue_mills,
        "start_mills": task.start_mills,
        "finish_mills": task.finish_mills,
        "finish_with_error": task.finish_with_error,
        "task_status": task.task_status,
        "task_result": result_data,
        "error_message": task.error_message,
        "require_base64": task.req_param.get("require_base64", False) if task.req_param else False,
    }


def _metadata_to_task(meta: dict[str, Any]) -> QueueTask:
    """Reconstruct a QueueTask from Redis metadata."""
    task_result = None
    if meta.get("task_result"):
        task_result = [
            ImageGenerationResult(
                im=r.get("im"),
                seed=r.get("seed", ""),
                finish_reason=GenerationFinishReason(r.get("finish_reason", "SUCCESS")),
            )
            for r in meta["task_result"]
        ]

    return QueueTask(
        job_id=meta["job_id"],
        task_type=TaskType(meta.get("task_type", "Text to Image")),
        req_param={"require_base64": meta.get("require_base64", False)},
        webhook_url=meta.get("webhook_url"),
        is_finished=meta.get("is_finished", False),
        finish_progress=meta.get("finish_progress", 0),
        in_queue_mills=meta.get("in_queue_mills", 0),
        start_mills=meta.get("start_mills", 0),
        finish_mills=meta.get("finish_mills", 0),
        finish_with_error=meta.get("finish_with_error", False),
        task_status=meta.get("task_status"),
        task_result=task_result,
        error_message=meta.get("error_message"),
    )


class TaskQueue:
    """FIFO task queue with Redis-backed history, webhooks, and concurrency control."""

    def __init__(
        self,
        queue_size: int = 100,
        history_size: int = 64,
        webhook_url: str | None = None,
        redis_store=None,
    ) -> None:
        self.queue_size = queue_size
        self.history_size = history_size
        self.webhook_url = webhook_url

        # In-memory queue (hot path for GPU worker)
        self.queue: list[QueueTask] = []
        self.last_job_id: str | None = None

        # Redis-backed history (persistent across restarts)
        self._redis = redis_store
        self._history_fallback: list[QueueTask] = []

    @property
    def history(self) -> list[QueueTask]:
        """Compatibility property — returns in-memory fallback when Redis unavailable."""
        return self._history_fallback

    def _save_history_to_redis(self, task: QueueTask) -> bool:
        """Persist a finished task to Redis history. Returns True on success."""
        if self._redis is None:
            return False
        try:
            meta = _task_to_metadata(task)
            meta_json = json.dumps(meta, default=str)
            key = f"{HISTORY_KEY_PREFIX}:{task.job_id}"
            score = float(task.in_queue_mills)

            pipe = self._redis.redis.pipeline()
            pipe.setex(key, HISTORY_TTL_SECONDS, meta_json)
            pipe.zadd(HISTORY_LIST_KEY, {task.job_id: score})

            # Trim history: keep only last history_size entries
            pipe.zremrangebyrank(HISTORY_LIST_KEY, 0, -(self.history_size + 1))
            pipe.execute()
            return True
        except Exception as e:
            logger.warning("Failed to save task %s to Redis history: %s", task.job_id, e)
            return False

    def _get_history_from_redis(self, job_id: str) -> QueueTask | None:
        """Retrieve a single task from Redis history."""
        if self._redis is None:
            return None
        try:
            key = f"{HISTORY_KEY_PREFIX}:{job_id}"
            data = self._redis.get(key)
            if data:
                return _metadata_to_task(json.loads(data))
        except Exception as e:
            logger.warning("Failed to get task %s from Redis history: %s", job_id, e)
        return None

    def _list_history_from_redis(
        self, page: int = 0, page_size: int = 20
    ) -> list[dict[str, Any]]:
        """List history entries from Redis sorted set."""
        if self._redis is None:
            return []
        try:
            start = page * page_size
            end = start + page_size - 1
            job_ids = self._redis.redis.zrevrange(HISTORY_LIST_KEY, start, end)
            results = []
            for jid in job_ids:
                key = f"{HISTORY_KEY_PREFIX}:{jid}"
                data = self._redis.get(key)
                if data:
                    results.append(json.loads(data))
            return results
        except Exception as e:
            logger.warning("Failed to list Redis history: %s", e)
            return []

    def _delete_from_redis(self, job_id: str) -> bool:
        """Delete a task from Redis history."""
        if self._redis is None:
            return False
        try:
            key = f"{HISTORY_KEY_PREFIX}:{job_id}"
            pipe = self._redis.redis.pipeline()
            pipe.delete(key)
            pipe.zrem(HISTORY_LIST_KEY, job_id)
            pipe.execute()
            return True
        except Exception as e:
            logger.warning("Failed to delete task %s from Redis: %s", job_id, e)
            return False

    def _clear_redis_history(self) -> int:
        """Clear all Redis history. Returns count of entries removed."""
        if self._redis is None:
            return 0
        try:
            job_ids = self._redis.redis.zrange(HISTORY_LIST_KEY, 0, -1)
            count = len(job_ids)
            if count == 0:
                return 0
            pipe = self._redis.redis.pipeline()
            for jid in job_ids:
                pipe.delete(f"{HISTORY_KEY_PREFIX}:{jid}")
            pipe.delete(HISTORY_LIST_KEY)
            pipe.execute()
            return count
        except Exception as e:
            logger.warning("Failed to clear Redis history: %s", e)
            return 0

    def _get_redis_history_count(self) -> int:
        """Get count of entries in Redis history."""
        if self._redis is None:
            return 0
        try:
            return self._redis.redis.zcard(HISTORY_LIST_KEY)
        except Exception:
            return 0

    def add_task(
        self,
        task_type: TaskType,
        req_param: dict[str, Any],
        webhook_url: str | None = None,
    ) -> QueueTask | None:
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

    def get_task(self, job_id: str, include_history: bool = False) -> QueueTask | None:
        """Find a task by ID. Optionally search Redis history."""
        for task in self.queue:
            if task.job_id == job_id:
                return task
        if include_history:
            # Try Redis first
            redis_task = self._get_history_from_redis(job_id)
            if redis_task is not None:
                return redis_task
            # Fall back to in-memory history
            for task in self._history_fallback:
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
        """Finish a task: send webhook, persist to history, clean up."""
        task = self.get_task(job_id)
        if task is None:
            return

        task.is_finished = True
        task.finish_mills = int(time.time() * 1000)

        # Send webhook
        webhook = task.webhook_url or self.webhook_url
        if webhook and task.task_result:
            self._send_webhook(webhook, task)

        # Remove from queue
        if task in self.queue:
            self.queue.remove(task)

        # Persist to Redis history
        saved_to_redis = self._save_history_to_redis(task)

        # Also keep in in-memory fallback (for when Redis is unavailable)
        if not saved_to_redis:
            self._history_fallback.append(task)

        # Trim in-memory fallback
        while len(self._history_fallback) > self.history_size:
            old = self._history_fallback.pop(0)
            self._cleanup_output_files(old)

        logger.info("Task finished: %s (error=%s, redis=%s)", job_id, task.finish_with_error, saved_to_redis)

    def get_queue_info(self) -> dict[str, Any]:
        """Return queue status info."""
        return {
            "running_size": len(self.queue),
            "finished_size": self._get_redis_history_count() or len(self._history_fallback),
            "last_job_id": self.last_job_id,
        }

    def get_history(
        self,
        job_id: str | None = None,
        page: int = 0,
        page_size: int = 20,
        delete: bool = False,
    ) -> dict[str, Any]:
        """Query history. Optionally filter by job_id, paginate, or delete."""
        if delete and job_id:
            # Try Redis first
            deleted = self._delete_from_redis(job_id)
            # Also check in-memory fallback
            task = None
            for t in self._history_fallback:
                if t.job_id == job_id:
                    task = t
                    break
            if task:
                self._history_fallback.remove(task)
                self._cleanup_output_files(task)
                deleted = True
            if deleted:
                return {"deleted": job_id}
            return {"message": "Not found"}

        # Single job lookup
        if job_id:
            redis_task = self._get_history_from_redis(job_id)
            if redis_task:
                return {
                    "queue": self._queue_info_list(),
                    "history": [self._task_info_dict(redis_task)],
                }
            for t in self._history_fallback:
                if t.job_id == job_id:
                    return {
                        "queue": self._queue_info_list(),
                        "history": [self._task_info_dict(t)],
                    }
            return {"queue": self._queue_info_list(), "history": []}

        # Paginated list — try Redis first
        redis_entries = self._list_history_from_redis(page, page_size)
        if redis_entries:
            return {
                "queue": self._queue_info_list(),
                "history": [
                    {
                        "job_id": e.get("job_id"),
                        "in_queue_mills": e.get("in_queue_mills", 0),
                        "start_mills": e.get("start_mills", 0),
                        "finish_mills": e.get("finish_mills", 0),
                        "is_finished": e.get("is_finished", False),
                    }
                    for e in redis_entries
                ],
            }

        # Fallback to in-memory
        tasks = self._history_fallback
        start = page * page_size
        end = start + page_size
        page_tasks = tasks[start:end]

        return {
            "queue": self._queue_info_list(),
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

    def _queue_info_list(self) -> list[dict[str, Any]]:
        """Build queue info list for response."""
        return [
            {
                "job_id": t.job_id,
                "in_queue_mills": t.in_queue_mills,
                "start_mills": t.start_mills,
                "finish_mills": t.finish_mills,
                "is_finished": t.is_finished,
            }
            for t in self.queue
        ]

    @staticmethod
    def _task_info_dict(task: QueueTask) -> dict[str, Any]:
        """Build a task info dict for response."""
        return {
            "job_id": task.job_id,
            "in_queue_mills": task.in_queue_mills,
            "start_mills": task.start_mills,
            "finish_mills": task.finish_mills,
            "is_finished": task.is_finished,
        }

    def clear_all_history(self) -> int:
        """Clear all history from Redis and in-memory. Returns count cleared."""
        redis_count = self._clear_redis_history()
        memory_count = len(self._history_fallback)
        for task in self._history_fallback:
            self._cleanup_output_files(task)
        self._history_fallback.clear()
        return redis_count or memory_count

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
                except Exception as exc:
                    logger.debug("Failed to cleanup output file %s: %s", result.im, exc)
