# ADR-003: Health Check Standard

## Status
Accepted

## Date
2026-04-30

## Context
Each service implemented `/health` differently — different JSON shapes, different status values, different check logic. No consistent response format across services.

## Decision
Adopt `common.health_utils.ServiceHealthChecker` as the standard:
- Each service registers its own checks via `add_check()`
- Built-in checkers: `check_redis()`, `check_disk()`, `check_ffmpeg()`, `check_celery()`
- Standard response: `{status, service, version, timestamp, checks: {...}}`
- Status values: "healthy", "degraded", "unhealthy"
- HTTP 200 for healthy/degraded, 503 for unhealthy

## Consequences
- Consistent `/health` API across all services
- Orchestrator can reliably parse health from any service
- Easy to add service-specific checks (e.g., Whisper model for audio-transcriber)