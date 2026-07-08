"""Simplified circuit breaker for external services (Sprint-04)."""
from __future__ import annotations

from common.datetime_utils import now_brazil
from common.log_utils import get_logger

logger = get_logger(__name__)


class SimpleCircuitBreaker:
    """Simplified circuit breaker for external services."""

    def __init__(self, failure_threshold: int = 5) -> None:
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.last_failure_time = None
        self.is_open = False

    def record_success(self) -> None:
        self.failure_count = 0
        self.is_open = False

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = now_brazil()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.error(f"🔌 [CIRCUIT] Opened after {self.failure_count} failures")

    def should_allow_request(self) -> bool:
        if not self.is_open:
            return True

        if self.last_failure_time:
            elapsed = (now_brazil() - self.last_failure_time).total_seconds()
            if elapsed > 60:
                self.is_open = False
                self.failure_count = 0
                logger.info("🔌 [CIRCUIT] Attempting reset")
                return True

        return False


# Global circuit breakers
circuit_breakers = {
    "download": SimpleCircuitBreaker(failure_threshold=10),
    "transcription": SimpleCircuitBreaker(failure_threshold=3),
}
