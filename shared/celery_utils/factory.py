"""
Standardized Celery application factory.

Eliminates duplicated celery_config.py across microservices by providing
a single factory with sensible defaults and service-specific overrides.
"""
from __future__ import annotations

import os
from typing import Any

from celery import Celery


def create_celery_app(
    service_name: str,
    *,
    redis_url: str | None = None,
    broker_url: str | None = None,
    backend_url: str | None = None,
    task_default_queue: str | None = None,
    task_routes: dict[str, str] | None = None,
    task_time_limit: int | None = None,
    task_soft_time_limit: int | None = None,
    cache_ttl_hours: int | None = None,
    timezone: str = "UTC",
    enable_utc: bool = True,
    worker_prefetch_multiplier: int = 1,
    worker_max_tasks_per_child: int = 50,
    task_acks_late: bool = True,
    task_reject_on_worker_lost: bool = True,
    include: list[str] | None = None,
    beat_schedule: dict[str, Any] | None = None,
    **extra_conf: Any,
) -> Celery:
    _redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _broker_url = broker_url or os.getenv("CELERY_BROKER_URL", _redis_url)
    _backend_url = backend_url or os.getenv("CELERY_RESULT_BACKEND", _redis_url)

    _time_limit = task_time_limit
    if _time_limit is None:
        _time_limit = int(os.getenv("CELERY_TASK_TIME_LIMIT", "1800"))

    _soft_time_limit = task_soft_time_limit
    if _soft_time_limit is None:
        _soft_time_limit = int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", "1500"))

    _cache_ttl = cache_ttl_hours
    if _cache_ttl is None:
        _cache_ttl = int(os.getenv("CACHE_TTL_HOURS", "24"))
    _result_expires = _cache_ttl * 3600

    _queue = task_default_queue or f"{service_name}_queue"

    app = Celery(
        f"{service_name}_tasks",
        broker=_broker_url,
        backend=_backend_url,
    )

    conf: dict[str, Any] = dict(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone=timezone,
        enable_utc=enable_utc,
        result_expires=_result_expires,
        task_time_limit=_time_limit,
        task_soft_time_limit=_soft_time_limit,
        worker_prefetch_multiplier=worker_prefetch_multiplier,
        worker_max_tasks_per_child=worker_max_tasks_per_child,
        task_acks_late=task_acks_late,
        task_reject_on_worker_lost=task_reject_on_worker_lost,
        broker_connection_retry_on_startup=True,
        task_default_queue=_queue,
    )

    if task_routes:
        conf["task_routes"] = task_routes

    if include:
        conf["include"] = include

    if beat_schedule:
        conf["beat_schedule"] = beat_schedule

    conf.update(extra_conf)

    app.conf.update(conf)
    return app
