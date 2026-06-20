# SE9 Decisions Log

Date: 2026-06-19
Service: se9-make-video-img

---

## Decision 1: Keep `rbg_` JOB_ID_PREFIX

- **Status:** Accepted (no change)
- **Context:** SE9 uses `rbg_` prefix for job IDs and Redis keys. Investigation suggested migrating to `se9_`.
- **Decision:** Keep `rbg_` prefix.
- **Rationale:**
  - No functional benefit — prefix is cosmetic only
  - Existing Redis keys (`rbg_job:*`) would become orphaned on migration
  - Sorted set `rbg_jobs:list` references old IDs — `zrem` calls on new keys won't clean up
  - Tests hardcode `rbg_` assertions
  - Risk of data loss for in-flight jobs during migration
- **Trade-off:** Inconsistent naming across services, but zero operational risk.

---

## Decision 2: No Prometheus Metrics

- **Status:** Accepted (removed from scope)
- **Context:** Investigation suggested adding `/admin/metrics` with Prometheus counters.
- **Decision:** Do not add Prometheus metrics to SE9.
- **Rationale:**
  - None of the other 9 services (SE1-SE10) use Prometheus
  - Adding it only to SE9 would be inconsistent
  - SE9 already has `GET /admin/stats` with job counts by status + disk usage
  - Adding Prometheus requires new dependency (`prometheus-client`) and endpoint design
- **Trade-off:** No centralized metrics, but consistent architecture across monorepo.

---

## Decision 3: E2E Test Fix Not Needed

- **Status:** Not applicable
- **Context:** INVESTIGACAO.md claimed E2E test passes invalid `on_screen_text` kwarg to `assemble()`.
- **Decision:** No fix needed.
- **Rationale:**
  - Research confirmed the E2E test (`test_full_pipeline.py:245-257`) does NOT pass `on_screen_text`
  - The test already uses correct kwargs: `audio_path`, `image_paths`, `narration`, `output_dir`, etc.
  - `on_screen_text` exists on `CreateVideoRequest` model but is never consumed by `VideoAssembler` — dead field in the model, not a test issue
- **Trade-off:** None — INVESTIGACAO.md contained incorrect information.

---

## Decision 4: Webhook Retry Strategy

- **Status:** Implemented
- **Context:** Webhook had zero retry — single POST, failure silently dropped.
- **Decision:** Add manual retry with exponential backoff (no new dependencies).
- **Rationale:**
  - 3 attempts with delays 2s, 4s, 8s (total max wait ~14s)
  - Manual implementation avoids adding `tenacity` as new dependency
  - `httpx.AsyncClient` created per attempt (connection pool not shared) — acceptable for webhook volume
- **Trade-off:** Slight increase in pipeline completion time on webhook failure, but reliable delivery.

---

## Decision 5: Webhook URL via Pydantic Settings

- **Status:** Implemented
- **Context:** `EXTERNAL_URL` was read via raw `os.getenv()`, bypassing validation.
- **Decision:** Add `external_url` field to `MakeVideoImgSettings` with empty default.
- **Rationale:**
  - Consistent with other settings using Pydantic validation
  - Empty default means fallback to `http://localhost:{port}` when not set
  - Environment variable `EXTERNAL_URL` still works via Pydantic's env reading
- **Trade-off:** None — purely additive, backward compatible.

---

## Decision 6: Title Card Configurable via Settings

- **Status:** Implemented
- **Context:** Title card duration (3.0s) and text wrap width (20 chars) were hardcoded.
- **Decision:** Add `title_card_duration` and `title_card_wrap_width` to settings.
- **Rationale:**
  - Different use cases may need shorter/longer title cards
  - Text wrap width=20 was too narrow for some hook texts; increased to 30 (safe max for 1080px canvas with fontsize=52)
  - Both exposed as env vars for Docker deployment flexibility
- **Trade-off:** None — defaults preserve existing behavior.

---

## Decision 7: Redis Pipeline Batching

- **Status:** Implemented
- **Context:** `save_job`/`delete_job` used separate Redis calls; `list_jobs` had N+1 query problem.
- **Decision:** Use Redis pipelines for atomic operations and MGET for batch reads.
- **Rationale:**
  - `save_job`: pipeline `SETEX` + `ZADD` → atomic, 1 round trip
  - `delete_job`: pipeline `DELETE` + `ZREM` → atomic, 1 round trip
  - `list_jobs`: `ZREVRANGE` + `MGET` → O(2) round trips regardless of N jobs
  - `_FakeRedis` updated with `mget()` and `pipeline()` for test compatibility
- **Trade-off:** Slightly more complex code, but significant performance improvement for job listing.
