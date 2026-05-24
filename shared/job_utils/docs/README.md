# common/job_utils — Standardized Job Lifecycle

## Overview

The `job_utils` module provides a unified job creation, tracking, and management pattern
across all YTCaption microservices. It replaces the fragmented, service-specific
implementations with a single, well-tested foundation.

## Key Components

### Models (`models.py`)
- **JobStatus** — Unified enum: `PENDING, QUEUED, PROCESSING, COMPLETED, FAILED, CANCELLED`
- **StageStatus** — Per-stage tracking: `PENDING, PROCESSING, COMPLETED, FAILED, SKIPPED`
- **StageInfo** — Rich stage model with progress, timing, error, and metadata
- **StandardJob** — Base job model with lifecycle methods:
  - `mark_as_queued()`, `mark_as_processing()`, `mark_as_completed()`, `mark_as_failed()`, `mark_as_cancelled()`
  - `update_progress()`, `increment_retry()`
  - `add_stage()`, `start_stage()`, `complete_stage()`, `fail_stage()`
  - `is_expired`, `is_terminal`, `duration_seconds`
- **generate_job_id()** / **generate_random_job_id()** — Consistent ID generation

### Exceptions (`exceptions.py`)
All inherit from `common.exception_handlers.BaseServiceException`:
- `JobNotFoundError` (404)
- `JobExpiredError` (410)
- `JobAlreadyExistsError` (409)
- `JobCreationError` (500)
- `JobSubmissionError` (503)
- `JobProcessingError` (500)
- `JobValidationError` (400)
- `WorkerUnavailableError` (503)

### Store (`store.py`)
- **JobRedisStore** — Uses `ResilientRedisStore` with unified key pattern `{service_name}:job:{id}`
  - Sorted set `{service_name}:jobs:list` for efficient listing
  - TTL-based expiration
  - Consistent `save_job`, `get_job`, `update_job`, `delete_job`, `list_jobs`, `get_stats`, `cleanup_expired`, `find_orphaned`

### Manager (`manager.py`)
- **JobManager** — Business logic layer wrapping `JobRedisStore`:
  - `create_job()` with deterministic or random ID generation
  - `get_job()`, `complete_job()`, `fail_job()`, `cancel_job()`
  - `start_stage()`, `complete_stage()`, `fail_stage()`
  - `list_jobs()`, `delete_job()`, `get_stats()`

### Celery Utils (`celery_utils.py`)
- **CallbackTask** — Base Celery task with automatic `on_success`/`on_failure`/`on_retry`
- **submit_task()** — Submit to Celery with automatic fallback to async processing
- **reconstitute_job()** / **serialize_job()** — Serialization helpers

### Routes (`routes.py`)
- **create_job_router()** — Factory that returns an `APIRouter` with standard endpoints:
  - `GET /{job_id}` — Get job status (with 404/410 error handling)
  - `GET /` — List jobs with filtering
  - `DELETE /{job_id}` — Delete job
  - `GET /stats` — Job statistics

## Migration Pattern

Each service extends `StandardJob` with service-specific fields:

```python
# services/video-downloader/app/core/models_v2.py
from common.job_utils.models import StandardJob, JobStatus

class VideoDownloadJob(StandardJob):
    url: str = ""
    quality: str = "best"
    filename: Optional[str] = None
    file_path: Optional[str] = None
    # ...
```

Each service creates a store adapter that wraps `JobRedisStore`:

```python
# services/video-downloader/app/infrastructure/redis_store_v2.py
from common.job_utils.store import JobRedisStore

class VideoDownloadJobStore:
    def __init__(self, redis_url: str):
        self._resilient = ResilientRedisStore(redis_url=redis_url)
        self._store = JobRedisStore(
            redis_store=self._resilient,
            service_name="video_downloader",
        )
    # Delegate to internals while adding service-specific methods
```

## Redis Key Convention

| Service | Key Pattern | List Key |
|---------|-------------|----------|
| video-downloader | `video_downloader:job:{id}` | `video_downloader:jobs:list` |
| audio-normalization | `audio_normalization:job:{id}` | `audio_normalization:jobs:list` |
| audio-transcriber | `audio_transcriber:job:{id}` | `audio_transcriber:jobs:list` |
| make-video | `make_video:job:{id}` | `make_video:jobs:list` |
| youtube-search | `youtube_search:job:{id}` | `youtube_search:jobs:list` |
| orchestrator | `orchestrator:job:{id}` | `orchestrator:jobs:list` |

## Status Mapping

Service-specific statuses map to `JobStatus`:

| Service Status | Standard Status |
|----------------|-----------------|
| `DOWNLOADING` | `PROCESSING` |
| `NORMALIZING` | `PROCESSING` |
| `TRANSCRIBING` | `PROCESSING` |
| `ANALYZING_AUDIO` | `PROCESSING` |
| etc. | `PROCESSING` |

Use the `stages` dict in `StandardJob` for granular status tracking
instead of creating new enum values.