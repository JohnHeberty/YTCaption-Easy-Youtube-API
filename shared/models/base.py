"""
Base models shared across all microservices.

HealthStatus and BaseHealthResponse are defined here.
JobStatus and BaseJob are canonical in common.job_utils.models.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from enum import Enum
from datetime import datetime
from typing import Optional

from common.datetime_utils import now_brazil


class HealthStatus(str, Enum):
    """Status de health check"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class BaseHealthResponse(BaseModel):
    """Resposta padrão de health check"""
    status: HealthStatus
    service: str
    version: str
    timestamp: datetime = Field(default_factory=now_brazil)
    uptime_seconds: Optional[float] = None

    # Dependências
    redis_connected: bool = False
    celery_available: bool = False

    # Métricas
    active_jobs: int = 0
    total_processed: int = 0

    model_config = ConfigDict()
