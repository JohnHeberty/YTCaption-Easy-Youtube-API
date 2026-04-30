# ADR-002: Redis Serialization Versioning

## Status
Accepted

## Date
2026-04-30

## Context
Job data stored in Redis had no version information. When the job model format changed (e.g., adding `last_heartbeat` field, changing date format from space-separated to ISO 8601), there was no migration path. Old jobs would either fail to deserialize or lose data.

## Decision
Implement versioned serialization via `common.redis_utils.serializers.ModelSerializer`:
- All data saved to Redis includes a `_version` field (current: "2.0")
- On deserialization, the version is checked and automatic migration applied
- v1.0 → v2.0: datetime format normalization, add missing fields

## Consequences
- Safe deployment of model changes without Redis data loss
- Backward compatibility with existing jobs in Redis
- Centralized migration logic in `common/redis_utils/serializers.py`