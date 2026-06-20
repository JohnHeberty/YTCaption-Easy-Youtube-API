"""Formal state pattern for audio transcription job lifecycle transitions."""
from __future__ import annotations
from common.log_utils import get_logger

from enum import Enum, StrEnum
from typing import Optional

logger = get_logger(__name__)


class InvalidStateTransitionError(Exception):
    """Raised when a job attempts an invalid status transition."""

    def __init__(self, current: str, requested: str) -> None:
        self.current = current
        self.requested = requested
        super().__init__(f"Invalid state transition from '{current}' to '{requested}'")


class JobStatus(StrEnum):
    """Canonical job status values for the audio transcriber service."""

    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Valid transitions: current -> set of allowed next statuses.
_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    JobStatus.PENDING: frozenset({JobStatus.QUEUED, JobStatus.PROCESSING}),
    JobStatus.QUEUED: frozenset({JobStatus.PROCESSING, JobStatus.CANCELLED}),
    JobStatus.PROCESSING: frozenset(
        {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
    ),
    # Terminal states — no outgoing transitions.
    JobStatus.COMPLETED: frozenset(),
    JobStatus.FAILED: frozenset({JobStatus.PENDING}),
    JobStatus.CANCELLED: frozenset(),
}


class JobStateMachine:
    """Validates and applies job status transitions."""

    def __init__(self, status: str | JobStatus) -> None:
        self._status = _coerce_status(status)

    @property
    def current(self) -> JobStatus:
        return self._status

    # -- public API ------------------------------------------------------------

    def can_transition_to(self, new_status: str | JobStatus) -> bool:
        """Return ``True`` when *new_status* is a valid next state."""
        target = _coerce_status(new_status)
        allowed = _VALID_TRANSITIONS.get(self._status, frozenset())
        return target in allowed

    def transition_to(self, new_status: str | JobStatus) -> None:
        """Transition to *new_status*, raising on invalid moves."""
        if not self.can_transition_to(new_status):
            raise InvalidStateTransitionError(
                current=self._status.value, requested=_coerce_status(new_status).value
            )
        logger.debug("Job state transition: %s -> %s", self._status.value, _coerce_status(new_status).value)
        self._status = _coerce_status(new_status)


# -- internals -----------------------------------------------------------------

def _coerce_status(value: str | JobStatus) -> JobStatus:
    """Accept a raw string or an enum member and return the canonical ``JobStatus``."""
    if isinstance(value, JobStatus):
        return value
    try:
        return JobStatus(value)
    except ValueError as exc:
        raise InvalidStateTransitionError(
            current="unknown", requested=str(value)
        ) from exc
