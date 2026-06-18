# Make-Video Service

Orchestrates video creation from audio + YouTube Shorts + subtitles. Part of the YTCaption microservice ecosystem.

## Quick Start

```bash
# Prerequisites
cp .env.example .env
make validate   # Check directory structure

# Development (Docker)
make dev        # docker compose up --build

# Or run locally
make install    # Create venv + install deps
source .venv/bin/activate
python run.py   # Starts on port 8005

# Verify
make api-health
```

### Makefile targets

| Category | Targets |
|---|---|
| Dev | `install`, `dev`, `logs`, `shell` |
| Test | `test`, `test-unit`, `test-integration`, `test-e2e`, `test-coverage` |
| API | `api-health`, `api-download`, `api-make-video`, `api-jobs`, `api-job`, `api-cache-stats`, `api-admin-stats` |
| Docker | `build`, `up`, `down`, `restart`, `status` |
| OCR Calibration | `calibrate-start`, `calibrate-status`, `calibrate-apply`, `calibrate-watch` |
| Maintenance | `clean`, `validate`, `compatibility`, `purge` |

## Key Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service info and endpoint catalog |
| GET | `/health` | Health check (Redis, disk) |
| GET | `/metrics` | Prometheus metrics |
| POST | `/download` | Start download pipeline (shorts search + OCR validation) |
| POST | `/make-video` | Start video creation (audio file + approved shorts) |
| GET | `/jobs` | List jobs (optional `?status=` and `?limit=`) |
| GET | `/jobs/{job_id}` | Get job status and result |
| DELETE | `/jobs/{job_id}` | Delete job and its output |
| GET | `/download/{job_id}` | Download completed video file |
| GET | `/cache/stats` | Shorts cache statistics |
| GET | `/admin/stats` | Admin dashboard stats |

Both `/download` and `/make-video` return `202 Accepted` with a `job_id` for polling via `GET /jobs/{job_id}`.

## Architecture Notes

### Stack

- **FastAPI** (Python 3.11) — REST API
- **Celery** (Redis broker) — async task queue
- **Redis** — job store, cache, distributed locks
- **FFmpeg** — video/audio processing
- **EasyOCR / PaddleOCR / Tesseract** — subtitle detection in video frames
- **SQLite** — blacklist of rejected (embedded-subtitle) videos

### Pipeline

1. **Download** — Searches YouTube Shorts via microservice, downloads raw videos
2. **Transform** — Converts to H264 via FFmpeg
3. **Crop** — Permanent crop to target aspect ratio (default 9:16)
4. **Validate** — OCR on 100% of frames; rejects videos with embedded subtitles, approves clean ones
5. **Compose** — Concatenates approved shorts, adds audio (user-uploaded), burns word-level speech-gated subtitles, trims to audio duration + padding

### Storage Layout

```
data/
  raw/shorts/         # Downloaded shorts (processed)
  raw/audio/          # User-uploaded audio files
  transform/videos/   # H264-converted videos
  validate/in_progress/  # Videos tagged for OCR validation
  approved/videos/    # OCR-approved (no embedded subs)
  approved/output/    # Final composed videos
```

### Microservice Dependencies

| Service | Env Var | Default Port | Purpose |
|---|---|---|---|
| youtube-search | `YOUTUBE_SEARCH_URL` | 8001 | Shorts search |
| video-downloader | `VIDEO_DOWNLOADER_URL` | 8002 | Video download |
| audio-transcriber | `AUDIO_TRANSCRIBER_URL` | 8004 | Audio transcription (Whisper) |

### Docker Services

| Container | Role |
|---|---|
| `ytcaption-make-video` | FastAPI app (port 8005, host networking) |
| `ytcaption-make-video-celery` | Celery worker (1 solo worker, `make_video_queue`) |
| `ytcaption-make-video-celery-beat` | Celery Beat (periodic cleanup, orphan recovery) |

### Key Configuration (.env)

- `REDIS_URL` — Redis connection string (default: `redis://192.168.1.110:6379/0`)
- `CACHE_TTL_HOURS` — Job/result TTL (default 24h)
- `DEFAULT_ASPECT_RATIO` — 9:16, 16:9, 1:1, 4:5
- `VIDEO_TRIM_PADDING_MS` — Padding after audio ends (default 100ms)
- `TARGET_VIDEO_HEIGHT` / `TARGET_VIDEO_WIDTH` — Normalization resolution (720p default)
- `OCR_CONFIDENCE_THRESHOLD` — OCR detection sensitivity (default 0.50)
- `TRSD_ENABLED` — Temporal Region Subtitle Detector (experimental)
- `VAD_MODEL` — Voice Activity Detection: `webrtc` or `silero`
- `CELERY_WORKER_CONCURRENCY` — Parallel tasks (default 4)

### OCR / Subtitle Detection

The service uses an ensemble of detectors (EasyOCR, PaddleOCR, Tesseract) to detect embedded subtitles in short videos. Videos with detected hardcoded subtitles are blacklisted permanently and excluded from compositions. The `app/video_processing/` module contains:

- `ocr_detector.py` — Main OCR orchestrator
- `detectors/` — Individual detector wrappers (EasyOCR, PaddleOCR, Tesseract, CLIP)
- `subtitle_detector_v2.py` — Frame-level detection pipeline
- `voting/` — Ensemble conflict detection and confidence estimation
- `TRSD` — Temporal Region Subtitle Detector (experimental, frame-tracking based)

### Video Composition

VideoBuilder (`app/services/video_builder.py`) handles all FFmpeg operations: H264 conversion, cropping, concatenation, audio mixing, subtitle burning, and trimming. The composition flow:

1. Concatenate approved shorts (video only, audio removed)
2. Validate concatenation duration against expected sum
3. Transcribe audio via microservice, generate word-level cues
4. Apply VAD speech gating (silero-vad or webrtcvad)
5. Write SRT captions preserving original timestamps
6. Burn subtitles into video with configurable style (static/dynamic/minimal)
7. Trim video to audio duration + padding, validate sync drift
