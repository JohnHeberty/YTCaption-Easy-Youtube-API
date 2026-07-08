"""Simple in-memory metrics tracking (Sprint-05)."""
from __future__ import annotations


class SimpleMetrics:
    """Simple metrics tracking, ready for Prometheus."""

    def __init__(self) -> None:
        self.jobs_started = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.orphans_detected = 0
        self.orphans_recovered = 0
        self.orphans_failed = 0

    def reset(self) -> None:
        self.__init__()


simple_metrics = SimpleMetrics()
