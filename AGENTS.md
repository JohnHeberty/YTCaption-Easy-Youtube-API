# AGENTS.md - YTCaption-Easy-Youtube-API

Compact guide for AI agents working in this repository.

## Quick Commands

```bash
# Validate without starting services
make validate

# Development workflow
make dev-setup      # Install deps + validate
make build          # Build all Docker images
make up             # Start all services
make status         # Check container status
make logs-youtube-search   # View specific service logs

# Service-specific operations (pattern: make <command>-<service>)
make build-audio-transcriber
make up-make-video
make down-video-downloader
make restart-audio-normalization

# Cleanup
make clean          # Remove containers/volumes
make clean-all      # Full cleanup including venv
```

## Architecture

**Microservices (FastAPI + Celery + Redis):**
- `orchestrator/` (port 8000/8080) - Pipeline coordinator
- `services/video-downloader` (8002) - YouTube download
- `services/audio-normalization` (8003) - Audio processing
- `services/audio-transcriber` (8004) - Whisper transcription
- `services/make-video` (8005) - Video composition
- `services/youtube-search` (8001) - YouTube search API

**Communication:** HTTP REST (sync) + Celery tasks (async) via Redis at `192.168.1.110:6379`

**Common Library:** Shared code in `common/` - installed via `-e ./common` in requirements.txt

## Project Structure Rules

Each service follows this structure:
```
services/{name}/
├── README.md              # ONLY .md file allowed at root
├── run.py                 # Entry point
├── app/                   # Application code
├── tests/                 # All tests (pytest)
├── docs/                  # All documentation (.md files)
├── scripts/               # All scripts (.sh, .py runners)
├── common/ -> ../../common  # Symlink to shared library
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── Makefile
```

**Critical:** Never put `.md` files (except README), `.sh` scripts, or `test_*.py` files at service root. Use `docs/`, `scripts/`, `tests/` respectively.

## Code Quality (Pre-commit)

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

**Configured tools:**
- **Black** (100 chars), **isort** (black profile), **Flake8** (max complexity 15, ignores E203,E266,E501,W503)
- **Bandit** (security), **MyPy** (types), **detect-secrets**
- **Custom:** Blocks `datetime.now()` - must use `now_brazil()` from `common.datetime_utils`

## Testing

```bash
# Run tests for a service
cd services/make-video && pytest

# With markers
pytest -m "not slow"        # Skip slow tests
pytest -m integration       # Integration tests only
pytest --cov=app tests/     # With coverage
```

**pytest.ini config:** 600s timeout, HTML report output, strict markers

## Environment Setup

```bash
# Each service needs:
cd services/{service}
cp .env.example .env      # Edit as needed
pip install -r requirements.txt   # Installs common library too
```

**Key env vars:** `REDIS_URL`, `PORT`, service-specific URLs (`VIDEO_DOWNLOADER_URL`, etc.)

## Important Constraints

1. **Datetime:** Always use `now_brazil()` from `common.datetime_utils` - never `datetime.now()`. Pre-commit enforces this.
2. **Imports from common:** `from common.datetime_utils import now_brazil`, `from common.redis_utils import ResilientRedisStore`
3. **Health endpoints:** All services expose `/health` for health checks
4. **Logging:** Use structured JSON logging via `common.log_utils`

## Ports Reference

| Service | Port | Redis DB |
|---------|------|----------|
| orchestrator | 8000 | varies |
| youtube-search | 8001 | varies |
| video-downloader | 8002 | varies |
| audio-normalization | 8003 | varies |
| audio-transcriber | 8004 | varies |
| make-video | 8005 | varies |

Redis server: `192.168.1.110:6379` (external instance)

## Documentation References

- `docs/ARCHITECTURE.md` - System architecture
- `docs/PROJECT_STRUCTURE.md` - File organization rules
- `docs/DEVELOPMENT.md` - Development guide
- `MAKEFILE-README.md` - Makefile command reference
- `docs/PRE_COMMIT_HOOKS.md` - Pre-commit details
- Service-specific docs in `services/{name}/docs/`
