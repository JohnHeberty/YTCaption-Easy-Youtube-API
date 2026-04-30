# ADR-001: Dependency Injection Pattern

## Status
Accepted

## Date
2026-04-30

## Context
Each microservice had a different pattern for accessing shared dependencies (Redis stores, processors, API clients):
- Direct module-level globals
- `from app.main import` inside route handlers
- Manual `set_job_store()` setter injection
- `Optional[X] = None` with `global` in lifespan

None of these patterns support testability or proper separation of concerns.

## Decision
Adopt a standardized dependency injection pattern using:
1. `app/infrastructure/dependencies.py` module per service with `@lru_cache` factory functions
2. FastAPI `Depends()` for injecting dependencies into route handlers
3. Override pattern for test fixtures (`set_job_store_override()`, `reset_overrides()`)

## Consequences
- All route handlers declare their dependencies explicitly via `Depends()`
- No more `from app.main import` in route modules
- Tests can override any dependency without modifying global state
- Each service follows the same pattern (consistent across codebase)