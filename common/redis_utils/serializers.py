"""
Versioned serialization for Redis data.

Ensures backward compatibility when job data format changes between versions.
All services should use ModelSerializer for saving/loading job data to Redis.

Version history:
- v1.0: Original format (no _version field, created_at as "YYYY-MM-DD HH:MM:SS")
- v2.0: Current format (has _version field, ISO 8601 dates with "T" separator)
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

SERIALIZATION_VERSION = "2.0"

SUPPORTED_VERSIONS = {"1.0", "2.0"}


class ModelSerializer:
    """
    Handles serialization and deserialization of job data with versioning.

    Usage:
        # Serialize before saving to Redis
        data = ModelSerializer.serialize(job_dict)
        redis.hset(key, mapping=data)

        # Deserialize after loading from Redis
        job_dict = ModelSerializer.deserialize(data)
    """

    @staticmethod
    def serialize(model_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize model dict with version tag.

        Args:
            model_dict: Dictionary representation of a model

        Returns:
            Dict with _version field added
        """
        data = dict(model_dict)
        data["_version"] = SERIALIZATION_VERSION

        for field in ("created_at", "updated_at", "completed_at", "expires_at", "started_at", "last_heartbeat"):
            if field in data and data[field] is not None:
                value = data[field]
                if isinstance(value, datetime):
                    data[field] = value.isoformat()
                elif isinstance(value, str) and "T" not in value and " " in value:
                    data[field] = value.replace(" ", "T", 1)

        return data

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize data from Redis with automatic version migration.

        Args:
            data: Raw data from Redis (may be from an older version)

        Returns:
            Dict with _version field removed and data migrated to current format
        """
        if not data:
            return data

        data = dict(data)
        version = data.pop("_version", "1.0")

        if version == "2.0":
            return data
        elif version == "1.0":
            return ModelSerializer._migrate_v1_to_v2(data)
        else:
            logger.warning(f"Unknown serialization version: {version}, attempting migration")
            return data

    @staticmethod
    def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate v1.0 data to v2.0 format.

        v1.0 -> v2.0 changes:
        - created_at format: "YYYY-MM-DD HH:MM:SS" -> "YYYY-MM-DDTHH:MM:SS"
        - Added last_heartbeat field (default: None)
        - progress field: ensure float type
        """
        for field in ("created_at", "updated_at", "completed_at", "expires_at", "started_at"):
            if field in data and data[field] is not None and isinstance(data[field], str):
                value = data[field]
                if " " in value and "T" not in value:
                    data[field] = value.replace(" ", "T", 1)

        if "last_heartbeat" not in data:
            data["last_heartbeat"] = None

        if "progress" in data and data["progress"] is not None:
            try:
                data["progress"] = float(data["progress"])
            except (ValueError, TypeError):
                data["progress"] = 0.0

        return data

    @staticmethod
    def serialize_to_json(model_dict: Dict[str, Any]) -> str:
        """Serialize model dict to JSON string with version tag.

        Args:
            model_dict: Dictionary representation of a model

        Returns:
            JSON string with _version field
        """
        data = ModelSerializer.serialize(model_dict)
        return json.dumps(data, default=str)

    @staticmethod
    def deserialize_from_json(json_str: str) -> Dict[str, Any]:
        """Deserialize JSON string with automatic version migration.

        Args:
            json_str: JSON string from Redis

        Returns:
            Dict with data migrated to current format
        """
        if not json_str:
            return {}
        data = json.loads(json_str)
        return ModelSerializer.deserialize(data)