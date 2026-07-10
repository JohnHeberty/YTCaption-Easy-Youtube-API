"""API response schemas for SE8 Image Engine.

Typed response models for all endpoints. Re-exports domain models
that are used as response shapes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models import (
    AllModelNamesResponse,
    AsyncJobResponse,
    DescribeImageResponse,
    GeneratedImageResult,
    JobHistoryInfo,
    JobHistoryResponse,
    JobQueueInfo,
)


# =============================================================================
# Error
# =============================================================================

class ErrorResponse(BaseModel):
    """Unified error response for all SE8 endpoints."""

    detail: str = Field(..., description="Human-readable error message")
    error_code: str | None = Field(
        None, description="Machine-readable error code (e.g. 'QUEUE_FULL', 'INVALID_INPUT')"
    )


# =============================================================================
# Admin
# =============================================================================

class AdminOutputStats(BaseModel):
    """Output directory statistics."""

    count: int = Field(0, description="Number of output files")
    size_mb: float = Field(0.0, description="Total output size in MB")


class AdminStatsResponse(BaseModel):
    """System statistics response."""

    service: str = Field(..., description="Service name")
    queue: dict[str, Any] = Field(default_factory=dict, description="Current queue info")
    outputs: AdminOutputStats = Field(default_factory=AdminOutputStats)


class AdminCleanupResponse(BaseModel):
    """Cleanup result response."""

    jobs_removed: int = Field(0, description="Number of history entries removed")
    files_deleted: int = Field(0, description="Number of old output files deleted")
    message: str = Field("", description="Human-readable summary")


# =============================================================================
# Query
# =============================================================================

class OutputFileInfo(BaseModel):
    """Single output file info."""

    name: str = Field(..., description="Filename")
    url: str = Field(..., description="Relative URL to download the file")
    size: int = Field(..., description="File size in bytes")


class OutputDateGroup(BaseModel):
    """Output files grouped by date."""

    date: str = Field(..., description="Date directory (YYYY-MM-DD)")
    files: list[OutputFileInfo] = Field(default_factory=list, description="Files for this date")


class ListOutputsResponse(BaseModel):
    """Response listing all output images by date."""

    days: list[OutputDateGroup] = Field(default_factory=list, description="Output groups by date")


# =============================================================================
# Styles
# =============================================================================

class StyleDetail(BaseModel):
    """Style preset with prompt templates."""

    name: str = Field(..., description="Style preset name")
    prompt: str = Field("", description="Positive prompt template")
    negative_prompt: str = Field("", description="Negative prompt template")


# =============================================================================
# VRAM / Cleanup
# =============================================================================

class VRAMCleanupResponse(BaseModel):
    """Response from VRAM cleanup endpoint."""

    message: str = Field(..., description="Cleanup status message")
    detail: str | None = Field(None, description="Additional error detail if failed")


class ProcessRestartResponse(BaseModel):
    """Response from process restart endpoint."""

    message: str = Field(..., description="Restart status message")
    rss_before_gb: float = Field(..., description="Memory usage before cleanup (GB)")
    rss_after_cleanup_gb: float = Field(..., description="Memory usage after cleanup (GB)")


# =============================================================================
# Tools
# =============================================================================

class UpscaleResult(BaseModel):
    """ESRGAN upscale result."""

    success: bool = Field(..., description="Whether upscale succeeded")
    base64: str | None = Field(None, description="Base64-encoded output image (data URI)")
    width: int | None = Field(None, description="Output width in pixels")
    height: int | None = Field(None, description="Output height in pixels")
    error: str | None = Field(None, description="Error message if failed")


# =============================================================================
# Re-exports (explicit for OpenAPI generation)
# =============================================================================

__all__ = [
    "ErrorResponse",
    "AdminStatsResponse",
    "AdminOutputStats",
    "AdminCleanupResponse",
    "OutputFileInfo",
    "OutputDateGroup",
    "ListOutputsResponse",
    "StyleDetail",
    "VRAMCleanupResponse",
    "ProcessRestartResponse",
    "UpscaleResult",
    "AllModelNamesResponse",
    "AsyncJobResponse",
    "DescribeImageResponse",
    "GeneratedImageResult",
    "JobHistoryInfo",
    "JobHistoryResponse",
    "JobQueueInfo",
]
