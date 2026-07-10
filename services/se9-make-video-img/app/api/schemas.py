"""API schemas for SE9 Make Video IMG — request/response models.

Separated from domain models for clean architecture.
All schemas use FlexibleSchema (extra="allow") for forward compatibility.
Pattern: matches SE11 clothes-removal schemas.py structure.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FlexibleSchema(BaseModel):
    """Base schema with extra='allow' for forward compatibility."""
    model_config = ConfigDict(extra="allow")


# =============================================================================
# Enums (named — produce dropdowns in Swagger UI)
# =============================================================================

class VideoJobStatus(str, Enum):
    """Job lifecycle status."""
    QUEUED = "queued"
    GENERATING_AUDIO = "generating_audio"
    GENERATING_IMAGES = "generating_images"
    ASSEMBLING_VIDEO = "assembling_video"
    COMPLETED = "completed"
    FAILED = "failed"


class StageStatus(str, Enum):
    """Pipeline stage status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ZoomStyle(str, Enum):
    """Ken Burns zoom direction for video segments."""
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    RANDOM = "random"


# =============================================================================
# Request — Narration / Scene / Text segments
# =============================================================================

class NarrationSegment(BaseModel):
    """A single narration segment with timestamp.

    Sent to SE7 TTS for voice generation. Timestamps define scene boundaries.
    """
    t: float = Field(
        ...,
        description="Start time in seconds from video beginning.",
        examples=[0.0, 5.0, 10.0],
    )
    text: str = Field(
        ...,
        max_length=5000,
        description="Narration text for this segment. Concatenated and sent to SE7 TTS.",
        examples=["Meu pai comprou um sítio perto da família materna."],
    )


class SceneSuggestion(BaseModel):
    """Visual prompt for a single scene image.

    Sent to SE8 Fooocus for image generation. Each scene maps to one image.
    Includes cinematic metadata from upstream JSON for richer prompts.
    """
    t: float = Field(
        ...,
        description="Start time in seconds. Determines image order and segment mapping.",
        examples=[0.0, 5.0, 10.0],
    )
    visual: str = Field(
        ...,
        max_length=2000,
        description=(
            "Image generation prompt for SE8 Fooocus.\n\n"
            "A cinematic suffix is appended automatically: "
            "'cinematic composition, depth of field, volumetric lighting, "
            "high detail, professional photography, 8k resolution'."
        ),
        examples=["Estabelecing shot vertical, câmera estática, paisagem rural genérica."],
    )
    negative_prompt: str | None = Field(
        default=None,
        max_length=2000,
        description=(
            "Negative prompt — what to avoid in the image.\n\n"
            "Passed directly to SE8. If null, SE9 uses a generic default."
        ),
        examples=["pessoas, casas, carros, objetos específicos, elementos urbanos."],
    )
    camera_movement: Literal["static", "slow_push_in", "slow_pull_out", "random"] | None = Field(
        default=None,
        description=(
            "Camera movement direction for Ken Burns effect.\n\n"
            "- `static` — no zoom (zoom_in with speed=0)\n"
            "- `slow_push_in` — zoom in from 1.0x to 1.2x\n"
            "- `slow_pull_out` — zoom out from 1.2x to 1.0x\n"
            "- `random` — alternates zoom_in/zoom_out per scene\n\n"
            "If null, falls back to `zoom_style` field or 'random'."
        ),
        examples=["static", "slow_push_in"],
    )
    transition: str | None = Field(
        default=None,
        description=(
            "FFmpeg xfade transition to use AFTER this scene.\n\n"
            "Must be a valid FFmpeg xfade transition name. "
            "If null, a random transition is chosen from the built-in list.\n\n"
            "Common transitions: dissolve, fadeblack, smoothleft, circleopen, wipeleft, radial."
        ),
        examples=["dissolve", "fadeblack", "smoothleft"],
    )
    # Cinematic metadata from upstream JSON
    shot_type: str | None = Field(
        default=None,
        max_length=100,
        description=(
            "Shot type for this scene.\n\n"
            "Examples: establishing_shot, medium_shot, close_up, wide_shot, over_shoulder."
        ),
        examples=["establishing_shot", "medium_shot", "close_up"],
    )
    composition: str | None = Field(
        default=None,
        max_length=1000,
        description="Composition description for the scene.",
        examples=["Composição vertical simples com foco no ambiente rural."],
    )
    lighting: str | None = Field(
        default=None,
        max_length=200,
        description="Lighting description for the scene.",
        examples=["natural discreet", "soft low light", "dramatic side lighting"],
    )
    color_mood: str | None = Field(
        default=None,
        max_length=200,
        description="Color/mood description for the scene.",
        examples=["soft dark", "low contrast", "warm tones"],
    )
    subject: str | None = Field(
        default=None,
        max_length=500,
        description="Main subject of the scene.",
        examples=["paisagem rural genérica", "ambiente interno genérico"],
    )
    environment: str | None = Field(
        default=None,
        max_length=500,
        description="Environment/setting of the scene.",
        examples=["ambiente rural genérico", "ambiente interno genérico"],
    )
    allowed_visual_elements: list[str] | None = Field(
        default=None,
        description="Visual elements allowed in this scene.",
        examples=[["ambiente rural genérico", "vegetação", "céu"]],
    )
    forbidden_visual_elements: list[str] | None = Field(
        default=None,
        description="Visual elements forbidden in this scene.",
        examples=[["pessoas", "veículos", "objetos específicos"]],
    )


class OnScreenText(BaseModel):
    """Caption/subtitle overlay with timing.

    Rendered as text overlay on the final video using FFmpeg drawtext.
    """
    t: float = Field(
        ...,
        description="Start time in seconds when the caption appears.",
        examples=[1.2, 7.0],
    )
    text: str = Field(
        ...,
        max_length=500,
        description="Caption text to display on screen.",
        examples=["Meu pai comprou um sítio perto da família materna."],
    )
    end_seconds: float | None = Field(
        default=None,
        description=(
            "End time in seconds when the caption disappears.\n\n"
            "If null, the caption stays visible until the next caption or scene end."
        ),
        examples=[4.5],
    )


# =============================================================================
# Request — Audio Cues (SFX / Silence)
# =============================================================================

class SFxCue(BaseModel):
    """Sound effect cue for a specific time range.

    Defines an abstract sound texture to be mixed into the final audio.
    Used for atmospheric enhancement — not tied to specific visual elements.
    """
    t: float = Field(
        ...,
        description="Start time in seconds (scene-relative).",
        examples=[1.5],
    )
    end_seconds: float = Field(
        ...,
        description="End time in seconds (scene-relative).",
        examples=[2.0],
    )
    cue: str = Field(
        ...,
        max_length=500,
        description="Description of the sound texture.",
        examples=["textura sonora baixa e abstrata sugerindo ruído"],
    )
    intensity: str = Field(
        default="low",
        max_length=50,
        description="Intensity level: low, medium, high.",
        examples=["low", "medium"],
    )
    purpose: str = Field(
        default="",
        max_length=500,
        description="Narrative purpose of this sound cue.",
        examples=["sutil indicação dos ruídos mencionados na narração"],
    )
    global_start_seconds: float | None = Field(
        default=None,
        description="Global start time in seconds (from video beginning).",
        examples=[6.5],
    )
    global_end_seconds: float | None = Field(
        default=None,
        description="Global end time in seconds (from video beginning).",
        examples=[7.0],
    )


class SilenceCue(BaseModel):
    """Silence/pause cue for a specific time range.

    Defines a deliberate pause in audio for dramatic effect or clarity.
    """
    t: float = Field(
        ...,
        description="Start time in seconds (scene-relative).",
        examples=[0.5],
    )
    end_seconds: float = Field(
        ...,
        description="End time in seconds (scene-relative).",
        examples=[1.0],
    )
    purpose: str = Field(
        default="",
        max_length=500,
        description="Purpose of this silence.",
        examples=["respiro antes da frase principal para clareza"],
    )
    global_start_seconds: float | None = Field(
        default=None,
        description="Global start time in seconds (from video beginning).",
        examples=[0.5],
    )
    global_end_seconds: float | None = Field(
        default=None,
        description="Global end time in seconds (from video beginning).",
        examples=[1.0],
    )


# =============================================================================
# Request — Main
# =============================================================================

class CreateVideoRequest(BaseModel):
    """Request to create a video generation job.

    The pipeline will:
    1. Generate audio narration via SE7 TTS (Chatterbox)
    2. Generate scene images via SE8 Fooocus SDXL
    3. Assemble video with Ken Burns, crossfade transitions, and captions

    **Minimum required fields:** post_id, hook, narration, scene_suggestions.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "post_id": "1ra5656",
                    "hook": "Fiz meu pai vender o sítio assombrado dele",
                    "estimated_seconds": 30,
                    "language": "pt-BR",
                    "narration": [
                        {"t": 0, "text": "Meu pai comprou um sítio perto da família materna."},
                        {"t": 5, "text": "Uma semana depois, ouvi ruídos à noite."},
                    ],
                    "scene_suggestions": [
                        {
                            "t": 0,
                            "visual": "Estabelecing shot vertical, paisagem rural genérica.",
                            "negative_prompt": "pessoas, casas, carros.",
                            "camera_movement": "static",
                            "transition": "dissolve",
                        },
                        {
                            "t": 5,
                            "visual": "Medium shot interior at night, soft low light.",
                            "camera_movement": "slow_push_in",
                        },
                    ],
                    "on_screen_text": [
                        {"t": 1.2, "text": "Meu pai comprou um sítio.", "end_seconds": 4.5},
                    ],
                    "voice_id": "builtin_feminino",
                    "aspect_ratio": "9:16",
                }
            ]
        },
    )

    post_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique post identifier from the upstream system.",
        examples=["1ra5656"],
    )
    hook: str = Field(
        ...,
        max_length=500,
        description=(
            "Title/hook text for the video.\n\n"
            "Used as title card text (if title card is enabled). "
            "Also sent in webhook payload."
        ),
        examples=["Fiz meu pai vender o sítio assombrado dele (foi difícil)"],
    )
    estimated_seconds: int = Field(
        ...,
        ge=5,
        le=600,
        description="Target video duration in seconds. Used for scene count estimation.",
        examples=[30],
    )
    language: str = Field(
        default="pt-BR",
        max_length=10,
        description="Language code for TTS and caption rendering.",
        examples=["pt-BR", "en-US"],
    )
    content_rating: str = Field(
        default="Geral",
        max_length=20,
        description="Content rating hint (metadata only, not enforced).",
        examples=["Geral", "16+"],
    )
    narration: list[NarrationSegment] = Field(
        ...,
        min_length=1,
        description=(
            "Narration segments with timestamps.\n\n"
            "Sorted by `t`, concatenated, and sent to SE7 TTS as a single text. "
            "Timestamps define scene boundaries for duration calculation."
        ),
    )
    scene_suggestions: list[SceneSuggestion] = Field(
        ...,
        min_length=1,
        max_length=20,
        description=(
            "Visual prompts for scene images.\n\n"
            "Each entry generates one image via SE8 Fooocus. "
            "Images are looped cyclically if fewer than needed scenes. "
            "Supports negative_prompt, camera_movement, and transition per scene."
        ),
    )
    on_screen_text: list[OnScreenText] = Field(
        default_factory=list,
        description=(
            "Caption overlays with timing.\n\n"
            "Rendered as text overlays on the final video. "
            "If empty, no captions are added."
        ),
    )
    title_options: list[str] = Field(
        default_factory=list,
        description="Alternative title options (metadata, used in webhook payload).",
    )
    hashtags: list[str] = Field(
        default_factory=list,
        description="Hashtags for the video (metadata, used in webhook payload).",
    )
    safety_notes: list[str] = Field(
        default_factory=list,
        description="Safety/content notes (metadata only).",
    )
    voice_id: str = Field(
        default="builtin_feminino",
        max_length=100,
        description=(
            "TTS voice identifier.\n\n"
            "Built-in voices: `builtin_feminino`, `builtin_masculino`. "
            "Custom voices: path to WAV file in SE7 data/voices/."
        ),
        examples=["builtin_feminino"],
    )
    aspect_ratio: Literal["9:16", "16:9", "1:1"] = Field(
        default="9:16",
        description=(
            "Video aspect ratio.\n\n"
            "- `9:16` — vertical (TikTok/Reels/Shorts) — 1080×1920\n"
            "- `16:9` — horizontal (YouTube) — 1920×1080\n"
            "- `1:1` — square (Instagram) — 1080×1080"
        ),
        examples=["9:16"],
    )
    zoom_style: ZoomStyle = Field(
        default=ZoomStyle.RANDOM,
        description=(
            "Default Ken Burns zoom direction.\n\n"
            "Overridden per-scene if `scene_suggestions[].camera_movement` is set."
        ),
        examples=["random"],
    )
    webhook_url: str | None = Field(
        default=None,
        description=(
            "Webhook URL for job completion notification.\n\n"
            "POST request sent with full job status when job completes or fails. "
            "Retries up to 3 times with exponential backoff (2s, 4s, 8s)."
        ),
        examples=["https://example.com/webhook/video-ready"],
    )
    normalize_text: bool = Field(
        default=True,
        description=(
            "Normalize text before TTS.\n\n"
            "Enables SE7 text normalization (expand abbreviations, fix punctuation)."
        ),
    )
    global_style: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Global style constraints from upstream JSON.\n\n"
            "Metadata fields like visual_style, tone, pacing, safety rules. "
            "Stored but not directly used by SE9 pipeline. "
            "Preserved for future prompt enrichment."
        ),
        examples=[
            {
                "visual_style": "neutral, cinematic, fact-locked",
                "tone": "medo, tensão, estranhamento",
                "no_people_or_faces": True,
            }
        ],
    )
    platform: str | None = Field(
        default=None,
        description=(
            "Target platform for video presets.\n\n"
            "Affects aspect ratio and caption font size:\n"
            "- `tiktok_reels_shorts` — 9:16, font 48px\n"
            "- `youtube` — 16:9, font 42px\n"
            "- `instagram_feed` — 1:1, font 40px\n"
            "- `instagram_stories` — 9:16, font 52px, centered\n\n"
            "If null, uses aspect_ratio and default font size."
        ),
        examples=["tiktok_reels_shorts", "youtube"],
    )
    # Audio cues from upstream JSON
    sfx_cues: list[SFxCue] = Field(
        default_factory=list,
        description=(
            "Sound effect cues for the video.\n\n"
            "Defines abstract sound textures to mix into the final audio. "
            "Used for atmospheric enhancement. If empty, no SFX are added."
        ),
    )
    silence_cues: list[SilenceCue] = Field(
        default_factory=list,
        description=(
            "Silence/pause cues for the video.\n\n"
            "Defines deliberate pauses for dramatic effect or clarity. "
            "If empty, no silence pauses are added."
        ),
    )
    ambient_bed: str | None = Field(
        default=None,
        max_length=500,
        description=(
            "Ambient background audio description.\n\n"
            "Describes the continuous background ambience for the video. "
            "Stored as metadata for future audio mixing."
        ),
        examples=["ambiente rural de baixa presença", "ambiente interno discreto"],
    )


# =============================================================================
# Response — Jobs
# =============================================================================

class CreateVideoResponse(FlexibleSchema):
    """Response when a video generation job is created (HTTP 201)."""
    job_id: str = Field(
        ...,
        description="Unique job identifier (prefix: `rbg_`)",
        examples=["rbg_a1b2c3d4e5f6"],
    )
    status: VideoJobStatus = Field(
        default=VideoJobStatus.QUEUED,
        description="Initial job status",
        examples=["queued"],
    )
    post_id: str = Field(
        ...,
        description="Post identifier from the request",
        examples=["1ra5656"],
    )
    estimated_seconds: int = Field(
        ...,
        description="Target video duration in seconds",
        examples=[30],
    )
    scenes_count: int = Field(
        ...,
        description="Number of scene suggestions in the request",
        examples=[6],
    )
    message: str = Field(
        default="Video generation started",
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
        examples=[45.0],
    )
    error: str | None = Field(
        default=None,
        description="Error message if stage failed",
    )
    started_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp when stage started",
        examples=["2026-07-08T14:30:00.000-03:00"],
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
        examples=["rbg_a1b2c3d4e5f6"],
    )
    status: VideoJobStatus = Field(
        ...,
        description=(
            "Job status lifecycle:\n"
            "- `queued` — waiting for worker\n"
            "- `generating_audio` — SE7 TTS processing\n"
            "- `generating_images` — SE8 Fooocus processing\n"
            "- `assembling_video` — FFmpeg assembly\n"
            "- `completed` — video ready for download\n"
            "- `failed` — error occurred"
        ),
        examples=["generating_images"],
    )
    progress: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Overall progress percentage (0–100). Weighted: audio=0-40%, images=40-70%, assembly=70-100%.",
        examples=[55.0],
    )
    stages: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Stage details with individual progress.\n\n"
            "Keys: `generating_audio`, `generating_images`, `assembling_video`. "
            "Each contains: status, progress, error, started_at, completed_at."
        ),
    )
    created_at: str = Field(
        ...,
        description="Job creation timestamp (ISO 8601)",
        examples=["2026-07-08T14:30:00.000-03:00"],
    )
    error: str | None = Field(
        default=None,
        description="Error message if job failed",
    )


class JobListItem(FlexibleSchema):
    """Lightweight job info for list views."""
    job_id: str = Field(
        ...,
        description="Unique job identifier",
        examples=["rbg_a1b2c3d4e5f6"],
    )
    status: VideoJobStatus = Field(
        ...,
        description="Current job status",
        examples=["completed"],
    )
    progress: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Overall progress percentage",
        examples=[100.0],
    )
    post_id: str | None = Field(
        default=None,
        description="Post identifier",
        examples=["1ra5656"],
    )
    created_at: str | None = Field(
        default=None,
        description="Job creation timestamp (ISO 8601)",
        examples=["2026-07-08T14:30:00.000-03:00"],
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
    detail: str = Field(
        ...,
        description="Confirmation message",
        examples=["Job rbg_a1b2c3d4e5f6 deleted"],
    )


# =============================================================================
# Response — Config / Metadata
# =============================================================================

class ServiceInfoResponse(FlexibleSchema):
    """Service info endpoint response."""
    service: str = Field(default="make-video-img", description="Service name")
    version: str = Field(..., description="Service version")
    endpoints: dict[str, str] = Field(
        default_factory=dict,
        description="Available endpoints with descriptions",
    )


class ConfigResponse(FlexibleSchema):
    """Current service configuration (no secrets)."""
    service: str = Field(default="make-video-img", description="Service name")
    version: str = Field(..., description="Service version")
    defaults: dict[str, Any] = Field(
        default_factory=dict,
        description="Default video generation settings",
        examples=[{
            "voice_id": "builtin_feminino",
            "aspect_ratio": "9:16",
            "zoom_style": "random",
            "fps": 30,
            "width": 1080,
            "height": 1920,
            "crossfade_duration": 0.3,
            "image_steps": 30,
            "image_performance": "Quality",
        }],
    )
    supported_aspect_ratios: list[str] = Field(
        default_factory=list,
        description="Supported aspect ratios",
        examples=[["9:16", "16:9", "1:1"]],
    )
    supported_zoom_styles: list[str] = Field(
        default_factory=list,
        description="Supported Ken Burns zoom styles",
        examples=[["zoom_in", "zoom_out", "random"]],
    )
    upstream: dict[str, str] = Field(
        default_factory=dict,
        description="Upstream service URLs (SE7, SE8)",
        examples=[{"se7": "http://localhost:8007", "se8": "http://localhost:8008"}],
    )


class TransitionInfo(FlexibleSchema):
    """FFmpeg xfade transition with metadata."""
    name: str = Field(
        ...,
        description="Transition identifier (FFmpeg xfade name)",
        examples=["dissolve"],
    )
    category: str = Field(
        ...,
        description="Transition category",
        examples=["fade", "wipe", "slide", "smooth"],
    )


class TransitionsResponse(FlexibleSchema):
    """Available FFmpeg xfade transitions."""
    transitions: list[str] = Field(
        default_factory=list,
        description="All available transition names",
    )
    total: int = Field(
        default=0,
        description="Total number of available transitions",
        examples=[32],
    )
    default: str = Field(
        default="random",
        description="Default transition selection mode",
    )


class VoicesResponse(FlexibleSchema):
    """Available TTS voices."""
    voices: list[dict[str, str]] = Field(
        default_factory=list,
        description="Available voices with id and name",
        examples=[[{"voice_id": "builtin_feminino", "name": "Feminino"}]],
    )
    default: str = Field(
        default="builtin_feminino",
        description="Default voice ID",
    )


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
        default="make-video-img",
        description="Service name",
    )
    version: str = Field(
        ...,
        description="Service version",
    )


class PingResponse(FlexibleSchema):
    """Simple connectivity test."""
    pong: bool = Field(default=True, description="Pong response")


# =============================================================================
# Response — Admin
# =============================================================================

class AdminStatsResponse(FlexibleSchema):
    """System statistics — job counts and disk usage."""
    service: str = Field(default="make-video-img", description="Service name")
    version: str = Field(..., description="Service version")
    jobs: dict[str, Any] = Field(
        default_factory=dict,
        description="Job counts by status",
        examples=[{"total": 38, "by_status": {"completed": 30, "failed": 5, "queued": 3}}],
    )
    disk: dict[str, Any] = Field(
        default_factory=dict,
        description="Disk usage by directory",
    )


class AdminCleanupResponse(FlexibleSchema):
    """Cleanup result — removed failed jobs and their files."""
    detail: str = Field(
        ...,
        description="Cleanup result message",
        examples=["Cleaned up 5 failed jobs (dirs + Redis keys)"],
    )


# =============================================================================
# Response — Errors
# =============================================================================

class ErrorResponse(FlexibleSchema):
    """Standard error response returned by all endpoints on failure."""
    detail: str = Field(
        ...,
        description="Human-readable error message",
        examples=["Job not found"],
    )
