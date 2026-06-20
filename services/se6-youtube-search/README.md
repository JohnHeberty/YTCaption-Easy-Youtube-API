# SE6 -- YouTube Search

> Busca e consulta de dados do YouTube com ytbpy (scraping, sem API key)

- **Port:** 8006 (default, configurable via `PORT` env var)
- **Cache:** 24-hour TTL in Redis, periodic cleanup every 30 minutes
- **Async processing:** All search requests create a Job that is processed by a Celery worker; clients can poll, long-poll (`/wait`), or download results

---

## Quick Start

### Prerequisites
- Python 3.11+
- Redis (shared instance, externally managed)
- Docker & Docker Compose (optional, for containerized deployment)

### Local development
```bash
cp .env.example .env         # edit REDIS_URL and other variables as needed
make venv                     # create virtual environment
make install                  # install Python dependencies
make dev                      # run the FastAPI server (hot-reload enabled)
```

### Docker (3 containers)
```bash
make build      # docker compose build
make up         # docker compose up -d
# Starts: API server, Celery worker, Celery beat
```

### Verify
```bash
make health     # curl /health
make info       # show service info and docs URL
```

---

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Service info and endpoint catalog |
| GET | `/health` | Deep health check (Redis, disk, Celery workers, ytbpy library) |
| POST | `/search/video-info` | Get video details (by ID or full URL) |
| POST | `/search/channel-info` | Get channel info, optionally with video listing |
| POST | `/search/playlist-info` | Get playlist info |
| POST | `/search/videos` | Text-based video search |
| POST | `/search/shorts` | Search YouTube Shorts (videos <= 60s) |
| POST | `/search/related-videos` | Get related videos for a given video ID |
| GET | `/jobs/{job_id}` | Get job status and results |
| GET | `/jobs` | List recent jobs |
| DELETE | `/jobs/{job_id}` | Delete a job |
| GET | `/jobs/{job_id}/download` | Download completed results as JSON |
| GET | `/jobs/{job_id}/wait` | Long-poll until job completes (timeout configurable) |
| GET | `/admin/stats` | System statistics (jobs by status, Celery info) |
| GET | `/admin/queue` | Celery queue inspection |
| POST | `/admin/cleanup` | Manual cleanup (basic or deep, optional Celery purge) |
| GET | `/admin/metrics` | Prometheus metrics |

Interactive docs at `/docs` (OpenAPI / Swagger).

---

## Architecture Notes

- **3 Docker containers:** FastAPI server (`youtube-search-api`), Celery worker (`youtube-search-celery-worker`), Celery beat (`youtube-search-celery-beat`). Redis runs externally.
- **Job-based async pattern:** Every search request returns a `Job` immediately with status `queued`. A Celery worker picks it up, runs the search, and stores results in Redis. Clients poll `/jobs/{id}` or use the `/wait` long-poll endpoint.
- **Search library:** `ytbpy` (bundled `app/services/ytbpy/`) scrapes YouTube Innertube API directly -- no official API key needed.
- **Resilience:** ytbpy calls wrapped with exponential-retry (3 attempts, 1-10s backoff) via tenacity. Celery tasks have soft (300s) and hard (330s) time limits with automatic retry (up to 3) on timeout.
- **Storage:** Redis with circuit breaker (`ResilientRedisStore`), key prefix `youtube_search:job:*`, sorted set for job listing. Default 24h TTL.
- **Periodic tasks:** Celery beat triggers `cleanup_expired_jobs` every 30 minutes.
- **Rate limiting:** Enabled by default (100 requests per minute, configurable).
- **Logging:** Structured JSON logs, configurable level and output directory.
- **Monitoring:** Prometheus metrics endpoint `/admin/metrics`, deep health check at `/health`.
