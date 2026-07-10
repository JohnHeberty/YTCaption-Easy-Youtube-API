from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FlexibleSchema(BaseModel):
    model_config = {"extra": "allow"}


# =============================================================================
# Voice Profiles
# =============================================================================

class VoiceProfileResponse(FlexibleSchema):
    """Single voice profile."""
    id: str = Field(..., description="Unique voice profile identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: str = Field(default="", description="Optional voice description")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    duration_seconds: float = Field(..., description="Audio sample duration in seconds")
    sample_rate: int = Field(..., description="Audio sample rate in Hz")
    status: str = Field(..., description="Voice status: ready, processing, error")


class VoiceProfileCreateResponse(FlexibleSchema):
    """Response after creating a voice profile."""
    id: str = Field(..., description="Unique voice profile identifier")
    name: str = Field(..., description="Human-readable voice name")
    description: str = Field(default="", description="Optional voice description")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    duration_seconds: float = Field(..., description="Audio sample duration in seconds")
    sample_rate: int = Field(..., description="Audio sample rate in Hz")
    status: str = Field(..., description="Voice status")
    message: str = Field(default="", description="Success message")


class VoiceProfileListResponse(FlexibleSchema):
    """List of voice profiles."""
    profiles: list[VoiceProfileResponse] = Field(default_factory=list, description="Available voice profiles")
    total: int = Field(..., description="Total number of profiles")


class DeleteVoiceResponse(FlexibleSchema):
    """Response after deleting a voice profile."""
    message: str = Field(..., description="Deletion confirmation message")
    voice_id: str = Field(..., description="ID of deleted voice profile")


# =============================================================================
# Jobs
# =============================================================================

class JobResponse(FlexibleSchema):
    """Job creation response."""
    success: bool = Field(..., description="Whether job was created successfully")
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Initial job status")
    message: str = Field(default="", description="Human-readable status message")


class JobDetailResponse(FlexibleSchema):
    """Full job details."""
    id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Current job status")
    progress: float = Field(default=0.0, description="Progress percentage (0-100)")
    progress_message: str | None = Field(None, description="Current stage description")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    started_at: str | None = Field(None, description="Processing start timestamp")
    completed_at: str | None = Field(None, description="Completion timestamp")
    voice_id: str | None = Field(None, description="Voice profile ID used for cloning")
    has_voice_cloning: bool = Field(default=False, description="Whether voice cloning is enabled")
    exaggeration: float = Field(default=0.5, description="TTS exaggeration parameter")
    cfg_weight: float = Field(default=0.5, description="TTS CFG weight parameter")
    temperature: float = Field(default=0.8, description="TTS temperature parameter")
    output_duration_seconds: float | None = Field(None, description="Output audio duration")
    error_message: str | None = Field(None, description="Error message if failed")
    stages: dict[str, Any] = Field(default_factory=dict, description="Pipeline stage details")


class JobListResponse(FlexibleSchema):
    """Paginated job list."""
    jobs: list[JobDetailResponse] = Field(default_factory=list, description="Job details list")
    total: int = Field(..., description="Total number of jobs")


class DeleteJobResponse(FlexibleSchema):
    """Response after deleting a job."""
    message: str = Field(..., description="Deletion confirmation message")
    job_id: str = Field(..., description="ID of deleted job")
    files_deleted: int = Field(default=0, description="Number of output files deleted")


# =============================================================================
# Health
# =============================================================================

class HealthResponse(FlexibleSchema):
    """Health check response."""
    status: str = Field(..., description="Overall health status")
    service: str = Field(default="audio-generation", description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    timestamp: str = Field(default="", description="Check timestamp (ISO 8601)")
    checks: dict[str, Any] = Field(default_factory=dict, description="Individual health checks")


# =============================================================================
# Admin
# =============================================================================

class AdminStatsResponse(FlexibleSchema):
    """System statistics response."""
    service: str = Field(..., description="Service name")
    jobs: AdminJobStats = Field(default_factory=lambda: AdminJobStats(), description="Job statistics")


class AdminJobStats(FlexibleSchema):
    """Job statistics."""
    total: int = Field(default=0, description="Total number of jobs")
    by_status: dict[str, int] = Field(default_factory=dict, description="Job count by status")


class AdminCleanupResponse(FlexibleSchema):
    """Cleanup result response."""
    jobs_removed: int = Field(default=0, description="Number of jobs removed")
    message: str = Field(default="", description="Human-readable cleanup summary")


# =============================================================================
# Error
# =============================================================================

class ErrorResponse(FlexibleSchema):
    """Standard error response."""
    error: str = Field(..., description="Error type or code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] | None = Field(default=None, description="Additional error details")
