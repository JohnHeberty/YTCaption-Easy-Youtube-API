"""API routes for video job management."""
from __future__ import annotations

import os
import shutil
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Depends, Query, status

from app.core.config import settings
from app.core.constants import (
    JOB_ID_PREFIX,
    TRANSITIONS,
    ASPECT_RATIOS,
    ZOOM_STYLES,
    IMAGE_ASPECT_RATIOS,
    CAMERA_MOVEMENT_MAP,
    DEFAULT_VOICE_ID,
)
from app.core.models import (
    CreateVideoRequest,
    VideoJob,
)
from app.api.schemas import (
    CreateVideoResponse,
    DeleteJobResponse,
    JobStatusResponse,
    JobListItem,
    ListJobsResponse,
    ServiceInfoResponse,
    ConfigResponse,
    TransitionsResponse,
    VoicesResponse,
    ErrorResponse,
    VideoJobStatus,
)
from app.infrastructure.http_client import SE7Client
from app.infrastructure.redis_store import get_video_job_store
from app.worker import get_worker

router = APIRouter(tags=["Jobs"])
store = get_video_job_store()


# ─── Service Info ────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=ServiceInfoResponse,
    summary="Service info",
    tags=["Health"],
    description=(
        "Returns service metadata: name, version, and a catalog of all available endpoints.\n\n"
        "**Use this endpoint** to discover the API structure programmatically."
    ),
)
async def root() -> ServiceInfoResponse:
    return ServiceInfoResponse(
        service="make-video-img",
        version=settings.app_version,
        endpoints={
            "POST /jobs": "Create video generation job",
            "GET /jobs": "List all jobs (paginated)",
            "GET /jobs/{job_id}": "Get job status and progress",
            "DELETE /jobs/{job_id}": "Delete job and output files",
            "GET /download/{job_id}": "Download completed video (MP4)",
            "GET /config": "Service configuration",
            "GET /transitions": "Available FFmpeg xfade transitions",
            "GET /camera-movements": "Available Ken Burns camera movements",
            "GET /voices": "Available TTS voices",
            "GET /health": "Health check (SE7 + SE8 + disk + FFmpeg)",
            "GET /ping": "Simple ping",
            "GET /admin/stats": "System statistics",
            "POST /admin/cleanup": "Cleanup failed jobs",
        },
    )


# ─── Config / Metadata ──────────────────────────────────────────────────────

@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Service configuration",
    description=(
        "Returns current service configuration including default video settings, "
        "supported aspect ratios, zoom styles, and upstream service URLs.\n\n"
        "**Note:** Does not expose secrets (API keys)."
    ),
    responses={
        200: {"description": "Service configuration"},
    },
)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        service="make-video-img",
        version=settings.app_version,
        defaults={
            "voice_id": settings.default_voice_id,
            "aspect_ratio": settings.default_aspect_ratio,
            "zoom_style": "random",
            "fps": settings.default_fps,
            "width": settings.default_width,
            "height": settings.default_height,
            "crossfade_duration": settings.default_crossfade_duration,
            "image_steps": settings.default_image_steps,
            "image_performance": settings.default_image_performance,
            "title_card_duration": settings.title_card_duration,
            "tts_exaggeration": settings.tts_exaggeration,
            "tts_cfg_weight": settings.tts_cfg_weight,
            "tts_temperature": settings.tts_temperature,
        },
        supported_aspect_ratios=list(ASPECT_RATIOS.keys()),
        supported_zoom_styles=ZOOM_STYLES,
        upstream={
            "se7": settings.se7_url,
            "se8": settings.se8_url,
        },
    )


@router.get(
    "/transitions",
    response_model=TransitionsResponse,
    summary="Available transitions",
    description=(
        "Returns all FFmpeg xfade transitions available for video assembly.\n\n"
        "Use `scene_suggestions[].transition` to specify a transition per scene. "
        "If not specified, a random transition is chosen from this list."
    ),
    responses={
        200: {"description": "Available transitions"},
    },
)
async def list_transitions() -> TransitionsResponse:
    return TransitionsResponse(
        transitions=TRANSITIONS,
        total=len(TRANSITIONS),
        default="random",
    )


@router.get(
    "/camera-movements",
    summary="Available camera movements",
    description=(
        "Returns all camera movements available for Ken Burns effect.\n\n"
        "Use `scene_suggestions[].camera_movement` to specify movement per scene.\n"
        "- `static` — no zoom (zoom_in with speed=0)\n"
        "- `slow_push_in` — zoom in from 1.0x to 1.2x\n"
        "- `slow_pull_out` — zoom out from 1.2x to 1.0x\n"
        "- `random` — alternates zoom_in/zoom_out per scene"
    ),
    responses={
        200: {"description": "Available camera movements"},
    },
)
async def list_camera_movements() -> dict:
    return {
        "movements": list(CAMERA_MOVEMENT_MAP.keys()),
        "mapping": CAMERA_MOVEMENT_MAP,
        "description": {
            "static": "No zoom — camera stays fixed",
            "slow_push_in": "Zoom in 1.0x → 1.2x — creates tension, focus",
            "slow_pull_out": "Zoom out 1.2x → 1.0x — reveals context, resolution",
            "random": "Alternates zoom_in/zoom_out per scene",
        },
        "default": "random",
    }


@router.get(
    "/voices",
    response_model=VoicesResponse,
    summary="Available TTS voices",
    description=(
        "Returns all available TTS voices from SE7 (Chatterbox).\n\n"
        "Use `voice_id` in `POST /jobs` to specify which voice to use.\n"
        "Built-in voices: `builtin_feminino` (default), `builtin_masculino`.\n"
        "Custom voices can be created via SE7's `POST /voices` endpoint."
    ),
    responses={
        200: {"description": "Available voices"},
    },
)
async def list_voices() -> VoicesResponse:
    se7 = SE7Client()
    try:
        voices = await se7.list_voices()
    finally:
        await se7.close()

    return VoicesResponse(
        voices=[{"voice_id": v["id"], "name": v["name"]} for v in voices],
        default=DEFAULT_VOICE_ID,
    )


# ─── Jobs CRUD ───────────────────────────────────────────────────────────────

@router.post(
    "/jobs",
    response_model=CreateVideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create video generation job",
    description=(
        "Create a new video generation job.\n\n"
        "The pipeline will:\n"
        "1. Generate audio narration via SE7 TTS (Chatterbox)\n"
        "2. Generate scene images via SE8 Fooocus SDXL\n"
        "3. Assemble video with Ken Burns, crossfade transitions, and captions\n\n"
        "**Minimum required fields:** `post_id`, `hook`, `narration`, `scene_suggestions`.\n\n"
        "Each scene supports:\n"
        "- `negative_prompt` — what to avoid in the image\n"
        "- `camera_movement` — Ken Burns direction (static/slow_push_in/slow_pull_out)\n"
        "- `transition` — FFmpeg xfade transition after this scene"
    ),
    responses={
        201: {"description": "Job created successfully"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_job(request: CreateVideoRequest) -> CreateVideoResponse:
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    job = VideoJob(
        job_id=job_id,
        post_id=request.post_id,
        request=request,
    )

    store.save_job(job_id, job.model_dump(mode="json"))

    worker = get_worker()
    worker.start()

    return CreateVideoResponse(
        job_id=job_id,
        status=VideoJobStatus.QUEUED,
        post_id=request.post_id,
        estimated_seconds=request.estimated_seconds,
        scenes_count=len(request.scene_suggestions),
        message="Video generation started",
    )


@router.get(
    "/jobs",
    response_model=ListJobsResponse,
    summary="List all jobs",
    description=(
        "Returns a paginated list of all video generation jobs.\n\n"
        "Jobs are returned in reverse chronological order (most recent first)."
    ),
    responses={
        200: {"description": "Paginated job list"},
    },
)
async def list_jobs(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of jobs to return",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of jobs to skip (for pagination)",
    ),
) -> ListJobsResponse:
    jobs = store.list_jobs()
    sliced = jobs[offset : offset + limit]
    return ListJobsResponse(
        jobs=[
            JobListItem(
                job_id=j["job_id"],
                status=j["status"],
                progress=j.get("progress", 0),
                post_id=j.get("post_id"),
                created_at=j.get("created_at"),
            )
            for j in sliced
        ],
        total=len(jobs),
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status",
    description=(
        "Get the current status and progress of a video generation job.\n\n"
        "**Polling:** Call this endpoint every 5–10 seconds while `status` is\n"
        "`queued`, `generating_audio`, `generating_images`, or `assembling_video`.\n"
        "The job is finished when `status` is `completed` or `failed`.\n\n"
        "**Progress:** Weighted across stages — audio=0-40%, images=40-70%, assembly=70-100%.\n\n"
        "**Output:** When completed, use `GET /download/{job_id}` to download the MP4."
    ),
    responses={
        200: {"description": "Job status"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return JobStatusResponse(
        job_id=job_data["job_id"],
        status=job_data["status"],
        progress=job_data.get("progress", 0),
        stages=job_data.get("stages", {}),
        created_at=job_data.get("created_at", ""),
        error=job_data.get("error"),
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=DeleteJobResponse,
    summary="Delete job",
    description=(
        "Delete a video generation job and all its output files.\n\n"
        "**Warning:** This action is irreversible. All output images,\n"
        "video segments, and final MP4 will be permanently removed."
    ),
    responses={
        200: {"description": "Job deleted"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def delete_job(job_id: str) -> DeleteJobResponse:
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    output_dir = os.path.join(settings.output_dir, job_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    store.delete_job(job_id)
    return DeleteJobResponse(detail=f"Job {job_id} deleted")
