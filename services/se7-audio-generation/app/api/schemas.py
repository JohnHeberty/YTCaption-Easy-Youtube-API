from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FlexibleSchema(BaseModel):
    model_config = {"extra": "allow"}


class VoiceProfileResponse(FlexibleSchema):
    id: str
    name: str
    description: str = ""
    created_at: str
    duration_seconds: float
    sample_rate: int
    status: str


class VoiceProfileCreateResponse(FlexibleSchema):
    id: str
    name: str
    description: str = ""
    created_at: str
    duration_seconds: float
    sample_rate: int
    status: str
    message: str = ""


class DeleteVoiceResponse(FlexibleSchema):
    message: str
    voice_id: str


class JobResponse(FlexibleSchema):
    success: bool
    job_id: str
    status: str
    message: str = ""


class JobDetailResponse(FlexibleSchema):
    id: str
    status: str
    progress: float = 0.0
    progress_message: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    voice_id: str | None = None
    has_voice_cloning: bool = False
    exaggeration: float = 0.5
    cfg_weight: float = 0.5
    temperature: float = 0.8
    output_duration_seconds: float | None = None
    error_message: str | None = None
    stages: dict[str, Any] = Field(default_factory=dict)


class JobListResponse(FlexibleSchema):
    jobs: list[JobDetailResponse]
    total: int


class DeleteJobResponse(FlexibleSchema):
    message: str
    job_id: str
    files_deleted: int = 0


class HealthResponse(FlexibleSchema):
    status: str
    service: str = "audio-generation"
    version: str = "1.0.0"
    timestamp: str = ""
    checks: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(FlexibleSchema):
    error: str
    message: str
    details: dict[str, Any] | None = None
