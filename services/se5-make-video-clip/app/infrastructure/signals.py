"""Celery signal handlers."""
from __future__ import annotations

from celery import signals
from common.log_utils import get_logger

logger = get_logger(__name__)


@signals.task_failure.connect
def task_failure_handler(task_id, exception, args, kwargs, traceback, einfo, **kw) -> None:
    """Log Celery worker failures with full context."""
    logger.error(
        "Celery task_failure | task_id=%s error=%s",
        task_id, exception, exc_info=einfo.exc_info if einfo else None
    )
