# AGENTS.md

## Quick Reference

This is a Python monorepo with 11 FastAPI microservices (SE1-SE11) + shared library. Each service has its own Dockerfile, requirements.txt, and tests under `services/se{N}-{name}/`.

## Commands

**Per-service** (run from `services/se{N}-{name}/`):
```bash
pip install -r requirements.txt          # install deps
python -m pytest tests/ -v               # run tests
python -m py_compile app/main.py         # syntax check
python -m ruff check .                   # lint
make dev                                 # local dev server
make test                                # via Makefile
make build && make up                    # Docker build+run
```

**Shared library** (from `shared/`):
```bash
pip install -e .
python -m pytest tests/ -v
```

**Deploy** (all services via docker compose):
```bash
bash scripts/deploy.sh
```

**CI lint order** (from `.github/workflows/ci.yml`): black → isort → flake8 → mypy → bandit. Run with `--check` flags for verification.

**Pre-commit hooks**: `pre-commit run --all-files` — runs black, isort, flake8, mypy, bandit, hadolint, detect-secrets, custom datetime hooks.

## Architecture

| Service | Port | Worker | Notes |
|---|---|---|---|
| SE1 orchestrator | 8001 | Celery | Pipeline coordinator |
| SE2 video-downloader | 8002 | Celery | yt-dlp |
| SE3 audio-normalization | 8003 | Celery | ffmpeg |
| SE4 audio-transcriber | 8004 | Celery | Whisper |
| SE5 make-video-clip | 8005 | Celery | ffmpeg |
| SE6 youtube-search | 8006 | Celery | YouTube API |
| SE7 audio-generation | 8007 | Celery | Chatterbox TTS (GPU) |
| SE8 image-generation | 8008 | Thread worker | Fooocus SDXL (GPU) |
| SE9 make-video-img | 8009 | Thread worker | Ken Burns video |
| SE10 clothes-segmentation | 8010 | ThreadPoolExecutor | GroundingDINO+SAM2 (CPU) |
| SE11 clothes-removal | 8011 | Celery | SE10→SE8 inpaint |

**Shared library** (`shared/`): installed as `common` package. Provides models, config, middleware, redis/log/celery utils, DI container.

**Key invariants:**
- Each service is independent — never import between services directly. Use `shared/` for common code.
- Redis: each service uses a different DB number (SE1=DB1, SE2=DB2, ... SE11=DB11).
- Auth: `X-API-Key` header on all service endpoints.
- Config: `.env` files per service (`.env.example` committed).
- `FOOOCUS/` directory is an immutable reference — never modify.

## Conventions

- Python 3.11+, always `from __future__ import annotations`
- Pydantic v2 (`SettingsConfigDict`, `@field_validator`) — not v1
- `pathlib.Path` for file paths, never raw strings
- Type hints on all public functions
- Specific exceptions, never bare `except Exception`
- Entry points: `app/main.py` per service, `run.py` for local dev

## Testing

- Framework: pytest with `conftest.py` per service
- **Always use real fixtures** from `tests/fixtures/` or `tests/fixtures_loader.py` — never synthetic payloads when fixtures exist
- Test markers: `unit`, `integration`, `e2e`, `slow`
- CI runs `pytest -x -m "not slow and not integration and not e2e"` for unit tests
- Services with fixtures: SE9 has `tests/fixtures_loader.py` for real CSV data

## Memory & Session State

- `MEMORY.md` — session state between conversations. **Read before starting any work.**
- `LIÇÕES.md` — consolidated lessons learned. Never scatter lessons in other .md files.
- Always update MEMORY.md after significant changes.

## Response Format

- **Always use absolute paths** when referencing files, videos, or outputs
- Include: files changed, what changed, how validated, risks/observations

## Constraints

- **SE7 TTS**: Chatterbox only. Never suggest Piper, Coqui, OpenAI TTS, etc. Voices are profiles in `data/voices/_builtin/` + `voice_seeder.py`.
- **`show/` folder**: copy visual artifacts (images, videos, grids) here for user presentation
- **Never** commit to `main`/`master` directly (pre-commit enforces)
- **Never** modify `FOOOCUS/` directory

## Documentation Index

- Architecture: `agent/architecture.md`
- Commands: `agent/commands.md`
- Full policy: `agent/agent-policy.md`
