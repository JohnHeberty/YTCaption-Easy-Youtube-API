"""
Focused job interfaces — ISP split of IJobStore.

IJobRepository: core CRUD for individual jobs (create, read, update, delete).
IJobQuery:     read-only queries with filtering, aggregation and queue info.
IJobStore:     composite interface that inherits both + .redis escape hatch.

The composite is kept so existing code importing IJobStore continues to work
without changes.  New code may type-hint against the narrower sub-interface
when it only needs a subset of operations (adapter pattern / dependency inversion).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# Note: we avoid importing Job here to prevent circular imports at domain level.
# Callers that need concrete types should use the models directly; these interfaces
# remain generic so they can be composed freely.


class IJobRepository(ABC):
    """Core CRUD operations for individual jobs."""

    @abstractmethod
    def save_job(self, job: Any) -> None:  # noqa: ANN401
        """Save (create or update) a single job to the store."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Any | None:  # noqa: ANN401
        """Load a single job by ID. Returns None when not found."""
        pass

    @abstractmethod
    def update_job(self, job: Any) -> None:  # noqa: ANN401
        """Update an existing job in the store."""
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Remove a job from the store. Returns True if it existed and was removed."""
        pass


class IJobQuery(ABC):
    """Read-only queries with filtering and aggregation."""

    @abstractmethod
    def list_jobs(
        self, limit: int = 100, status: Any | None = None, offset: int = 0  # noqa: ANN003
    ) -> list[Any]:  # noqa: ANN401
        """Return a filtered, paginated list of jobs."""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Aggregate job counts (total_jobs, by_status)."""
        pass

    @abstractmethod
    async def find_orphaned_jobs(
        self, max_age_minutes: int = 30
    ) -> list[Any]:  # noqa: ANN401
        """Find jobs stuck in PROCESSING/QUEUED beyond the age threshold."""
        pass

    @abstractmethod
    async def get_queue_info(self) -> dict[str, Any]:
        """Return current queue depth and metadata."""
        pass


class IJobStore(IJobRepository, IJobQuery):  # type: ignore[misc]
    """Composite interface — combines CRUD + Query for backward compatibility.

    Existing code that depends on the monolithic IJobStore continues to work
    unchanged.  The .redis property is kept here because it lives outside the
    pure repository/query split (infrastructure escape hatch).
    """

    @property
    @abstractmethod
    def redis(self) -> Any:  # noqa: ANN401
        """Expose the underlying Redis client for health checks, metrics and cleanup."""
        pass
