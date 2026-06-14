"""Progress tracking — unified with JobStateUpdater.

This module is deprecated: import ``JobStateUpdater`` directly from
``app.shared.job_state_updater``, or use the backward-compatible alias below.
"""

from .job_state_updater import JobStateUpdater


class ProgressTracker(JobStateUpdater):  # type: ignore[misc]
    """Deprecated — use :class:`JobStateUpdater` directly."""
    pass


# Keep RedisProgressTracker as an alias for any code that still references it.
RedisProgressTracker = ProgressTracker
