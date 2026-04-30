# ADR-006: Router Organization

## Status
Accepted

## Date
2026-04-30

## Context
Three services (orchestrator, video-downloader, audio-transcriber) had monolithic `main.py` files (1000+ lines each). All routes, middleware, and business logic were in a single file, violating SRP and making testing impossible.

## Decision
Each service should organize routes into separate APIRouter modules:
- `app/api/health_routes.py` — `/health`, `/metrics`
- `app/api/jobs_routes.py` — CRUD for jobs
- `app/api/admin_routes.py` — `/admin/*` endpoints
- `app/api/model_routes.py` — Service-specific endpoints (e.g., Whisper model)

Main.py responsibilities:
- App configuration and middleware
- Exception handlers
- Lifespan management
- Include routers

## Consequences
- Each router is independently testable with TestClient + DI overrides
- `main.py` is under 300 lines
- Routes can be developed and reviewed independently