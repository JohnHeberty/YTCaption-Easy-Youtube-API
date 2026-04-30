# ADR-004: Structured Logging Format

## Status
Accepted

## Date
2026-04-30

## Context
Services used different logging approaches: `logging.basicConfig()`, custom `setup_logging()`, `logging.getLogger()`. This led to inconsistent log formats, no JSON logging option, and difficulty correlating logs across services.

## Decision
All services use `common.log_utils.setup_structured_logging()` and `get_logger()`:
- JSON logging by default for production
- Structured fields: timestamp, service, level, message, correlation_id
- `logging.basicConfig()` is banned (enforced by pre-commit)
- `logging.getLogger()` replaced by `get_logger()` from common

## Consequences
- Consistent log format across all services
- JSON logs can be parsed by ELK/CloudWatch/Grafana Loki
- Correlation IDs enable distributed tracing