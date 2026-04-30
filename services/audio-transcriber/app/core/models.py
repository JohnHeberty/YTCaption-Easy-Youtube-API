"""
Re-export de modelos do domínio para padronização.
O audio-transcriber mantém seus modelos em domain/models.py.
"""
from ..domain.models import (
    Job,
    JobStatus,
    JobRequest,
    TranscriptionResponse,
    WhisperEngine,
    BaseJob,
    BaseHealthResponse,
    HealthStatus,
)

__all__ = [
    "Job",
    "JobStatus",
    "JobRequest",
    "TranscriptionResponse",
    "WhisperEngine",
    "BaseJob",
    "BaseHealthResponse",
    "HealthStatus",
]
