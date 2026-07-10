"""API schemas for SE11 Clothes Removal — request/response models.

Separated from domain models for clean architecture.
All schemas use FlexibleSchema (extra="allow") for forward compatibility.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services._helpers import DEFAULT_BASE_MODEL


class FlexibleSchema(BaseModel):
    model_config = {"extra": "allow"}


# =============================================================================
# Enums (named — produce dropdowns in Swagger UI)
# =============================================================================

class RemovalMode(str, Enum):
    """Processing mode for clothes removal pipeline."""
    CLOTHES = "clothes"
    PERSON = "person"
    NSFW = "nsfw"
    NSFW_TEST = "nsfw_test"


class DetectorType(str, Enum):
    """Object detection engine used by SE10."""
    GROUNDINGDINO = "groundingdino"
    SEGFORMER = "segformer"
    ENSEMBLE = "ensemble"


class ClothesRemovalJobStatus(str, Enum):
    """Job lifecycle status."""
    QUEUED = "queued"
    DETECTING = "detecting"
    INPAINTING = "inpainting"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    """Pipeline stage status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# =============================================================================
# Request
# =============================================================================

class CreateClothesRemovalRequest(BaseModel):
    """Request to create a clothes removal job (production modes: nsfw, clothes, person).

    Send an AI-generated image and the pipeline will:
    1. Detect the person (SE10)
    2. Detect clothing items (SE10 + SegFormer B2)
    3. Generate inpainting mask with adaptive head protection
    4. Inpaint via SE8 (Fooocus + LustifyNSFW)
    5. Validate pose integrity (MediaPipe)
    6. Return best result from 5 progressive attempts
    """

    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "json_schema_extra": {
            "examples": [
                {
                    "image": "data:image/png;base64,iVBORw0KGgo...",
                    "mode": "nsfw",
                    "classes": "spaghetti strap, camisole, top, blouse",
                    "prompt": "bare skin, realistic skin texture, photorealistic",
                    "negative_prompt": "deformed, blurry, cartoon",
                    "box_threshold": 0.10,
                    "text_threshold": 0.10,
                    "inpaint_strength": 1.0,
                    "per_garment": False,
                    "detector": "groundingdino",
                },
                {
                    "image": "https://example.com/model-photo.jpg",
                    "mode": "clothes",
                    "detector": "segformer",
                },
            ]
        },
    }

    image: str = Field(
        ...,
        description=(
            "**Image to process.** Accepts three formats:\n"
            "- `base64` — raw base64-encoded image\n"
            "- `data URI` — `data:image/png;base64,...`\n"
            "- `HTTP(S) URL` — direct link to image file\n\n"
            "Supported formats: PNG, JPEG, WebP."
        ),
        examples=["data:image/png;base64,iVBORw0KGgo...", "https://example.com/photo.jpg"],
    )
    mode: RemovalMode = Field(
        default=RemovalMode.CLOTHES,
        description=(
            "**Processing mode:**\n"
            "- `clothes` — Default. Detects and removes detected clothing items.\n"
            "- `person` — Removes entire torso region (head is preserved via adaptive detection).\n"
            "- `nsfw` — **Production pipeline.** Body-mask + retry loop (3 attempts) + pose validation + best selection.\n"
            "- `nsfw_test` — Alias for `nsfw`."
        ),
        examples=["clothes"],
    )
    classes: str | None = Field(
        default=None,
        description=(
            "**Clothing classes to detect** (comma-separated).\n"
            "If `null`, all clothing is detected automatically.\n\n"
            "Examples: `\"shirt,pants,dress\"`, `\"spaghetti strap, camisole, top\"`"
        ),
        examples=["spaghetti strap, camisole, top, blouse", "shirt, pants, dress"],
    )
    prompt: str = Field(
        default="",
        max_length=2000,
        description=(
            "**Inpainting prompt** — what the AI should generate in the masked area.\n"
            "Leave empty to use the default prompt optimized for skin texture."
        ),
        examples=["bare skin, realistic skin texture, photorealistic"],
    )
    negative_prompt: str = Field(
        default="",
        max_length=2000,
        description=(
            "**Negative prompt** — what the AI should avoid generating.\n"
            "Leave empty to use defaults."
        ),
        examples=["deformed, blurry, cartoon, low quality"],
    )
    box_threshold: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="**SE10 detection confidence threshold.** Higher = fewer but more confident detections.",
        examples=[0.10],
    )
    text_threshold: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="**SE10 text matching threshold** (used with GroundingDINO). Higher = stricter class matching.",
        examples=[0.10],
    )
    inpaint_strength: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description=(
            "**SE8 inpaint denoise strength.**\n"
            "- `0.0` — preserve original completely\n"
            "- `1.0` — full AI generation (default)"
        ),
        examples=[1.0],
    )
    per_garment: bool = Field(
        default=False,
        description="**Inpaint each garment separately.** Slower but higher quality for complex outfits.",
    )
    webhook_url: str | None = Field(
        default=None,
        description=(
            "**Webhook URL** for job completion notification.\n"
            "POST request sent with full job status when job completes or fails."
        ),
        examples=["https://example.com/webhook"],
    )
    detector: DetectorType = Field(
        default=DetectorType.GROUNDINGDINO,
        description=(
            "**Object detection engine:**\n"
            "- `groundingdino` — Default. Text-prompt detection.\n"
            "- `segformer` — Pixel-level clothing segmentation (18 classes). Recommended for clothes mode.\n"
            "- `ensemble` — Multi-detector consensus (GD+YOLO+BiRefNet+SegFormer). Best accuracy."
        ),
        examples=["groundingdino"],
    )
    face_blend_mode: Literal["alpha", "laplacian"] = Field(
        default="laplacian",
        description=(
            "**Face-body blending mode:**\n"
            "- `laplacian` — Multi-scale Laplacian pyramid blend (smoother transitions).\n"
            "- `alpha` — Simple alpha/feather blend (legacy v23.4)."
        ),
        examples=["laplacian"],
    )
    upscale: bool = Field(
        default=True,
        description=(
            "**Apply 4x-UltraSharp ESRGAN upscale** after inpainting.\n"
            "- `true` — **Default.** Upscales result 2x via pure ESRGAN (no SDXL generation).\n"
            "- `false` — Skip upscale, return result at original resolution."
        ),
        examples=[True],
    )
    face_restore: bool = Field(
        default=False,
        description="Apply face restoration (CodeFormer/GFPGAN) after compositing to unify texture.",
    )
    face_restore_model: Literal["CodeFormer", "GFPGAN"] = Field(
        default="CodeFormer",
        description="Face restoration model. CodeFormer preserves identity better; GFPGAN is more smoothing.",
        examples=["CodeFormer"],
    )
    face_restore_fidelity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="CodeFormer fidelity: 0.0 = more restoration, 1.0 = more identity preservation.",
        examples=[0.5],
    )
    inpaint_mode: Literal["body_mask", "clothes_mask", "invert_mask"] = Field(
        default="invert_mask",
        description=(
            "**Inpainting mask strategy (both nsfw and nsfw_test):**\n"
            "- `body_mask` — inpaint entire body minus head (legacy).\n"
            "- `clothes_mask` — inpaint only detected clothing regions.\n"
            "- `invert_mask` — **default.** Keep face/body/background and regenerate only clothing regions via inverted mask."
        ),
        examples=["invert_mask"],
    )
    use_faceid: bool = Field(
        default=True,
        description="Enable IP-Adapter FaceID to preserve facial identity during inpainting (both nsfw and nsfw_test).",
    )
    faceid_weight: float = Field(
        default=0.8,
        ge=0.0,
        le=1.5,
        description="IP-Adapter FaceID weight. 0.7-1.0 recommended; higher = stronger identity lock (nsfw_test only — production uses hardcoded value).",
        examples=[0.8],
    )
    test_inpaint_strength: float = Field(
        default=0.86,
        ge=0.0,
        le=1.0,
        description="Base denoising strength for nsfw_test (0.86 default). nsfw_test runs 5 attempts from this value. nsfw (production) ignores this — strength is hardcoded (0.86→0.98 progression).",
    )
    base_model: str = Field(
        default=DEFAULT_BASE_MODEL,
        description="Base SDXL checkpoint (nsfw_test only). nsfw (production) hardcodes LustifyNSFW. JuggernautXL also available.",
        examples=["lustifySDXLNSFW_v20-inpainting.safetensors", "juggernautXL_v8Rundiffusion.safetensors"],
    )


class CreateClothesRemovalTestRequest(BaseModel):
    """Request to create an nsfw_test job (experimental pipeline).

    Same as production but with full parameter control for testing:
    - Custom denoising strength progression
    - Base model selection (LustifyNSFW / JuggernautXL)
    - FaceID weight tuning
    - Inpaint mask strategy
    - Face blending mode
    """

    model_config = {
        "str_strip_whitespace": True,
        "validate_assignment": True,
        "json_schema_extra": {
            "examples": [
                {
                    "image": "data:image/png;base64,iVBORw0KGgo...",
                    "mode": "nsfw_test",
                    "test_inpaint_strength": 0.86,
                    "base_model": "lustifySDXLNSFW_v20-inpainting.safetensors",
                    "use_faceid": True,
                    "faceid_weight": 0.8,
                },
            ]
        },
    }

    image: str = Field(
        ...,
        description=(
            "**Image to process.** Accepts three formats:\n"
            "- `base64` — raw base64-encoded image\n"
            "- `data URI` — `data:image/png;base64,...`\n"
            "- `HTTP(S) URL` — direct link to image file\n\n"
            "Supported formats: PNG, JPEG, WebP."
        ),
    )
    mode: RemovalMode = Field(
        default=RemovalMode.NSFW_TEST,
        description="Processing mode. Must be `nsfw_test`.",
    )
    classes: str | None = Field(
        default="spaghetti strap, camisole, top, blouse",
        description="Clothing classes to detect (comma-separated). Ignored in nsfw_test.",
    )
    prompt: str = Field(
        default="",
        max_length=2000,
        description="Inpainting prompt — what the AI generates in the masked area.",
    )
    negative_prompt: str = Field(
        default="",
        max_length=2000,
        description="Negative prompt — what the AI should avoid.",
    )
    box_threshold: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 detection confidence threshold.",
    )
    text_threshold: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 text matching threshold.",
    )
    inpaint_strength: float = Field(
        default=1.0, ge=0.0, le=1.0,
        description="SE8 inpaint denoise strength.",
    )
    per_garment: bool = Field(
        default=False,
        description="Inpaint each garment separately.",
    )
    webhook_url: str | None = Field(
        default=None,
        description="Webhook URL for job completion notification.",
    )
    detector: DetectorType = Field(
        default=DetectorType.GROUNDINGDINO,
        description="Object detection engine.",
    )
    inpaint_mode: Literal["body_mask", "clothes_mask", "invert_mask"] = Field(
        default="invert_mask",
        description=(
            "Inpainting mask strategy:\n"
            "- `body_mask` — inpaint entire body minus head (legacy).\n"
            "- `clothes_mask` — inpaint only detected clothing regions.\n"
            "- `invert_mask` — **default.** Keep face/body/background, regenerate only clothing."
        ),
    )
    use_faceid: bool = Field(
        default=True,
        description="Enable IP-Adapter FaceID to preserve facial identity.",
    )
    faceid_weight: float = Field(
        default=0.8, ge=0.0, le=1.5,
        description="IP-Adapter FaceID weight. 0.7-1.0 recommended.",
        examples=[0.8],
    )
    test_inpaint_strength: float = Field(
        default=0.86, ge=0.0, le=1.0,
        description="Base denoising strength. Pipeline runs 5 attempts from this value (0.86→0.98).",
    )
    base_model: str = Field(
        default=DEFAULT_BASE_MODEL,
        description="Base SDXL checkpoint. LustifyNSFW (recommended) or JuggernautXL.",
        examples=["lustifySDXLNSFW_v20-inpainting.safetensors", "juggernautXL_v8Rundiffusion.safetensors"],
    )
    face_blend_mode: Literal["alpha", "laplacian"] = Field(
        default="laplacian",
        description="Face-body blending mode: `laplacian` (smoother) or `alpha` (legacy).",
    )
    upscale: bool = Field(
        default=True,
        description=(
            "Apply 4x-UltraSharp ESRGAN upscale after inpainting.\n"
            "- `true` — **Default.** Upscales result 2x via pure ESRGAN.\n"
            "- `false` — Skip upscale, return result at original resolution."
        ),
    )
    face_restore: bool = Field(
        default=False,
        description="Apply face restoration (CodeFormer/GFPGAN) after compositing.",
    )
    face_restore_model: Literal["CodeFormer", "GFPGAN"] = Field(
        default="CodeFormer",
        description="Face restoration model. CodeFormer preserves identity better; GFPGAN is more smoothing.",
    )
    face_restore_fidelity: float = Field(
        default=0.5, ge=0.0, le=1.0,
        description="CodeFormer fidelity: 0.0 = more restoration, 1.0 = more identity preservation.",
    )


# =============================================================================
# Response — Jobs
# =============================================================================

class CreateClothesRemovalResponse(FlexibleSchema):
    """Response when a clothes removal job is created (HTTP 201)."""
    job_id: str = Field(
        ...,
        description="Unique job identifier (prefix: `cr_`)",
        examples=["cr_a1b2c3d4e5f6"],
    )
    status: ClothesRemovalJobStatus = Field(
        default=ClothesRemovalJobStatus.QUEUED,
        description="Initial job status",
        examples=["queued"],
    )
    message: str = Field(
        default="Clothes removal job started",
        description="Human-readable status message",
    )


class JobStageInfo(FlexibleSchema):
    """Pipeline stage progress information."""
    status: StageStatus = Field(
        default=StageStatus.PENDING,
        description="Stage status",
        examples=["pending"],
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Stage progress percentage (0–100)",
        examples=[0.0],
    )
    error: str | None = Field(
        default=None,
        description="Error message if stage failed",
    )
    started_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when stage started",
        examples=["2026-06-27T00:12:40.371-03:00"],
    )
    completed_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when stage completed",
    )


class JobStatusResponse(FlexibleSchema):
    """Full job status for polling. Use this to track job progress."""
    job_id: str = Field(
        ...,
        description="Unique job identifier",
        examples=["cr_c6ce6b176755"],
    )
    status: ClothesRemovalJobStatus = Field(
        ...,
        description="Job status: `queued` → `detecting` → `inpainting` → `completed` | `failed`",
        examples=["detecting"],
    )
    progress: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall progress percentage (0–100)",
        examples=[31.0],
    )
    stages: dict[str, Any] = Field(
        default_factory=dict,
        description="Stage details (`detecting`, `inpainting`) with individual progress",
    )
    objects_detected: int | None = Field(
        default=None,
        description="Number of clothing objects detected by SE10",
        examples=[1],
    )
    created_at: str = Field(
        ...,
        description="Job creation timestamp (ISO 8601)",
        examples=["2026-06-27T00:12:40.371028-03:00"],
    )
    error: str | None = Field(
        default=None,
        description="Error message if job failed",
    )
    result_path: str | None = Field(
        default=None,
        description="Internal path to result image (not a public URL)",
    )


class JobListItem(FlexibleSchema):
    """Lightweight job info for list views."""
    job_id: str = Field(
        ...,
        description="Unique job identifier",
        examples=["cr_c6ce6b176755"],
    )
    status: ClothesRemovalJobStatus = Field(
        ...,
        description="Current job status",
        examples=["completed"],
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall progress percentage",
        examples=[70.0],
    )
    objects_detected: int | None = Field(
        default=None,
        description="Number of clothing objects detected",
        examples=[1],
    )
    created_at: str | None = Field(
        default=None,
        description="Job creation timestamp (ISO 8601)",
        examples=["2026-06-27T00:12:40.371028-03:00"],
    )


class ListJobsResponse(FlexibleSchema):
    """Paginated job list."""
    jobs: list[JobListItem] = Field(
        default_factory=list,
        description="List of jobs (most recent first)",
    )
    total: int = Field(
        default=0,
        description="Total number of jobs in the system",
        examples=[38],
    )


# =============================================================================
# Response — Delete
# =============================================================================

class DeleteJobResponse(FlexibleSchema):
    """Response when a job is deleted."""
    message: str = Field(
        ...,
        description="Confirmation message",
        examples=["Job cr_c6ce6b176755 deleted"],
    )
    job_id: str = Field(
        ...,
        description="ID of the deleted job",
        examples=["cr_c6ce6b176755"],
    )


# =============================================================================
# Response — Config / Metadata
# =============================================================================

class ModeInfo(FlexibleSchema):
    """Available processing mode with description."""
    name: str = Field(..., description="Mode identifier", examples=["nsfw"])
    description: str = Field(..., description="What this mode does")
    recommended: bool = Field(default=False, description="Is this the recommended mode?")


class ModesResponse(FlexibleSchema):
    """Available processing modes."""
    modes: list[ModeInfo] = Field(default_factory=list, description="All available modes")
    default: str = Field(default="clothes", description="Default mode if none specified")


class DetectorInfo(FlexibleSchema):
    """Available detection engine with description."""
    name: str = Field(..., description="Engine identifier", examples=["groundingdino"])
    description: str = Field(..., description="What this engine does")
    recommended: bool = Field(default=False, description="Is this the recommended engine?")


class DetectorsResponse(FlexibleSchema):
    """Available detection engines."""
    detectors: list[DetectorInfo] = Field(default_factory=list, description="All available detectors")
    default: str = Field(default="groundingdino", description="Default detector if none specified")


class ConfigResponse(FlexibleSchema):
    """Current service configuration."""
    service: str = Field(default="clothes-removal", description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    supported_modes: list[str] = Field(default_factory=list, description="Available processing modes")
    supported_detectors: list[str] = Field(default_factory=list, description="Available detection engines")
    output_dir: str = Field(default="", description="Output directory path")
    upstream: dict[str, str] = Field(default_factory=dict, description="Upstream service URLs")


# =============================================================================
# Response — Health
# =============================================================================

class HealthResponse(FlexibleSchema):
    """Basic health check response (liveness probe)."""
    status: str = Field(
        default="ok",
        description="Service status",
        examples=["ok"],
    )
    service: str = Field(
        default="clothes-removal",
        description="Service name",
    )
    version: str = Field(
        default="1.0.0",
        description="Service version",
    )


class DeepHealthCheck(FlexibleSchema):
    """Individual upstream service health status."""
    status: str = Field(
        ...,
        description="Service status: `ok` | `unreachable` | `unknown`",
        examples=["ok"],
    )
    latency_ms: float | None = Field(
        default=None,
        description="Response latency in milliseconds",
        examples=[12.5],
    )


class DeepHealthResponse(FlexibleSchema):
    """Deep health check with upstream services (SE10, SE8)."""
    status: str = Field(
        ...,
        description="Overall status: `ok` (all services healthy) or `degraded` (at least one unreachable)",
        examples=["ok"],
    )
    service: str = Field(default="clothes-removal")
    version: str = Field(default="1.0.0")
    checks: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-service health details",
    )


class PingResponse(FlexibleSchema):
    """Simple connectivity test."""
    pong: bool = Field(default=True, description="Pong response")


# =============================================================================
# Response — Admin
# =============================================================================

class AdminStatsResponse(FlexibleSchema):
    """System statistics — job counts and disk usage."""
    jobs: dict[str, Any] = Field(
        default_factory=dict,
        description="Job counts by status",
        examples=[{"total": 38, "by_status": {"completed": 30, "failed": 5, "queued": 3}}],
    )
    storage: dict[str, Any] = Field(
        default_factory=dict,
        description="Disk usage information",
        examples=[{"output_dir": "./data/outputs", "total_files": 150, "total_size_mb": 219.5}],
    )


class AdminCleanupResponse(FlexibleSchema):
    """Cleanup result — removed completed/failed jobs and their files."""
    cleaned: int = Field(
        default=0,
        description="Number of jobs cleaned up",
        examples=[12],
    )


# =============================================================================
# Response — Errors
# =============================================================================

class ErrorResponse(FlexibleSchema):
    """Standard error response returned by all endpoints on failure."""
    error: str = Field(
        ...,
        description="Error type identifier",
        examples=["NOT_FOUND"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Job not found"],
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Additional error details (validation errors, stack traces, etc.)",
    )


# =============================================================================
# Response — Service Info
# =============================================================================

class ServiceInfoResponse(FlexibleSchema):
    """Service information response."""
    service: str = Field(default="clothes-removal", description="Service name")
    version: str = Field(default="1.0.0", description="Service version")
    description: str = Field(default="AI-powered clothes removal with SE10 detection + SE8 inpainting", description="Service description")
    endpoints: dict[str, str] = Field(default_factory=dict, description="Available endpoint descriptions")
