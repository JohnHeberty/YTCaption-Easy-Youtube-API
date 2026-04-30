# ADR-005: Error Hierarchy Standard

## Status
Accepted

## Date
2026-04-30

## Context
Each service defined its own exception classes independently, leading to:
- Duplicate exception definitions (e.g., `JobNotFoundError` in 4 services)
- Inconsistent HTTP status codes for the same errors
- No `to_dict()` for API responses

## Decision
Create `common/exceptions.py` with a standard hierarchy:
- `ServiceError` base class with `message`, `error_code`, `status_code`, `to_dict()`
- Job lifecycle: `JobError`, `JobNotFoundError`, `JobExpiredError`, `JobCreationError`, `JobProcessingError`
- Validation: `ValidationError`, `FileValidationError`
- Infrastructure: `RedisConnectionError`, `ResourceNotFoundError`, `ResourceError`, `ProcessingTimeoutError`
- Microservice: `MicroserviceError`, `CircuitBreakerOpenError`

Services extend these for service-specific exceptions (e.g., `AudioNormalizationError(ValidationError)`).

## Consequences
- No duplicate exception definitions
- Consistent HTTP status codes across services
- All exceptions can be serialized to dict for API responses