"""Job routes for SE11 Clothes Removal."""
from __future__ import annotations

import base64
import os
import shutil
import uuid
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.core.constants import JOB_ID_PREFIX
from app.core.models import ClothesRemovalJob
from app.api.schemas import (
    ClothesRemovalJobStatus,
    ConfigResponse,
    CreateClothesRemovalResponse,
    DeleteJobResponse,
    DetectorType,
    DetectorInfo,
    DetectorsResponse,
    ErrorResponse,
    JobListItem,
    JobStatusResponse,
    ListJobsResponse,
    ModeInfo,
    ModesResponse,
    RemovalMode,
)
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.worker import get_worker

router = APIRouter(tags=["Jobs"])
store = ClothesRemovalJobStore()


# ─── Service Info ────────────────────────────────────────────────────────────

class ServiceInfoResponse(BaseModel):
    service: str = "clothes-removal"
    version: str = "1.0.0"
    description: str = "AI-powered clothes removal with SE10 detection + SE8 inpainting"
    endpoints: dict[str, str]


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
        endpoints={
            "POST /jobs": "Create a clothes removal job",
            "GET /jobs": "List all jobs (paginated)",
            "GET /jobs/{job_id}": "Get job status and progress",
            "DELETE /jobs/{job_id}": "Delete job and output files",
            "GET /jobs/{job_id}/download": "Download result image (PNG)",
            "GET /modes": "List available processing modes",
            "GET /detectors": "List available detection engines",
            "GET /config": "Current service configuration",
            "GET /health": "Liveness check",
            "GET /health/deep": "Deep check (SE10 + SE8 connectivity)",
            "GET /admin/stats": "System statistics",
            "POST /admin/cleanup": "Cleanup completed/failed jobs",
        },
    )


# ─── Utility Endpoints ───────────────────────────────────────────────────────

@router.get(
    "/modes",
    response_model=ModesResponse,
    summary="List processing modes",
    description=(
        "Returns all available processing modes with descriptions.\n\n"
        "Use this to populate UI dropdowns or validate `mode` parameter values."
    ),
    responses={
        200: {"description": "Available modes"},
    },
)
async def list_modes() -> ModesResponse:
    return ModesResponse(
        modes=[
            ModeInfo(
                name="clothes",
                description="Detects and removes detected clothing items. Best for general use.",
                recommended=True,
            ),
            ModeInfo(
                name="person",
                description="Removes entire torso region. Head is preserved via adaptive detection (haarcascade + silhouette).",
            ),
            ModeInfo(
                name="nsfw",
                description=(
                    "Production NSFW pipeline with 3-attempt retry loop, "
                    "pose validation (MediaPipe), and best result selection. "
                    "Highest quality but slower."
                ),
                recommended=True,
            ),
            ModeInfo(
                name="nsfw_test",
                description="Alias for `nsfw`. Kept for backward compatibility.",
            ),
        ],
        default="clothes",
    )


@router.get(
    "/detectors",
    response_model=DetectorsResponse,
    summary="List detection engines",
    description=(
        "Returns all available object detection engines.\n\n"
        "Use this to populate UI dropdowns or validate `detector` parameter values."
    ),
    responses={
        200: {"description": "Available detectors"},
    },
)
async def list_detectors() -> DetectorsResponse:
    return DetectorsResponse(
        detectors=[
            DetectorInfo(
                name="groundingdino",
                description="Default engine. Best overall accuracy for clothing detection.",
                recommended=True,
            ),
            DetectorInfo(
                name="florence2",
                description="Alternative engine. Good for fine-grained clothing class matching.",
            ),
        ],
        default="groundingdino",
    )


@router.get(
    "/config",
    response_model=ConfigResponse,
    summary="Service configuration",
    description=(
        "Returns current service configuration including supported modes, "
        "detectors, and upstream service URLs.\n\n"
        "**Note:** Does not expose secrets (API keys)."
    ),
    responses={
        200: {"description": "Service configuration"},
    },
)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        output_dir=settings.output_dir,
        supported_modes=["clothes", "person", "nsfw", "nsfw_test"],
        supported_detectors=["groundingdino", "florence2"],
        upstream={
            "se10": settings.se10_url,
            "se8": settings.se8_url,
        },
    )


# ─── Jobs CRUD ───────────────────────────────────────────────────────────────

@router.post(
    "/jobs",
    response_model=CreateClothesRemovalResponse,
    status_code=201,
    summary="Create clothes removal job",
    description=(
        "Upload an AI-generated image and start a clothes removal pipeline job.\n\n"
        "## Workflow\n"
        "1. **SE10** detects the person and clothing items\n"
        "2. **Head protection** via adaptive detection (haarcascade + silhouette scan)\n"
        "3. **SE8** inpaints the masked region (up to 3 attempts in `nsfw` mode)\n"
        "4. **Pose validation** ensures the result matches the input pose\n"
        "5. Returns the best result across all attempts\n\n"
        "## Polling\n"
        "Use `GET /jobs/{job_id}` to track progress. The job status transitions:\n"
        "`queued` → `detecting` → `inpainting` → `completed` | `failed`\n\n"
        "## Webhook\n"
        "Optionally provide `webhook_url` to receive a POST notification on completion.\n\n"
        "## Modes\n"
        "| Mode | Description |\n|------|-------------|\n"
        "| `clothes` | Default — removes detected clothing |\n"
        "| `person` | Removes entire torso (head preserved) |\n"
        "| `nsfw` | Production NSFW pipeline (retry + pose validation) |\n"
        "| `nsfw_test` | Alias for nsfw |\n\n"
        "## Tips\n"
        "- Use `GET /modes` to list available modes with descriptions\n"
        "- Use `GET /detectors` to list available detection engines"
    ),
    responses={
        201: {"description": "Job created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid file type or size"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_job(
    file: UploadFile = File(
        ...,
        description=(
            "**AI-generated image file** (PNG, JPEG, WebP).\n\n"
            "⚠️ **Policy:** Only AI-generated images are allowed. "
            "Real people photos are strictly prohibited. See POLITICA-USO.md."
        ),
    ),
    mode: RemovalMode = Form(
        default=RemovalMode.NSFW,
        description=(
            "**Processing mode:**\n"
            "- `nsfw` ⭐ — **Recommended.** Production pipeline with 3-attempt retry, pose validation.\n"
            "- `clothes` — Removes detected clothing items.\n"
            "- `person` — Removes entire torso (head preserved).\n"
            "- `nsfw_test` — Alias for nsfw."
        ),
    ),
    classes: str | None = Form(
        default="spaghetti strap, camisole, top, blouse",
        description=(
            "**Clothing classes to detect** (comma-separated).\n"
            "Only used in `clothes` mode. Ignored in `nsfw` mode.\n\n"
            "Leave as default for general fashion, or specify custom classes."
        ),
    ),
    prompt: str = Form(
        default="NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, detailed breast anatomy, realistic nipples, areola details, natural skin pores, skin texture, skin imperfections, realistic body proportions, maintaining exact same body posture, keeping original body position, not moving, not rotating, same stance, identical pose, skin tone matching the person's arms and face, consistent skin color throughout, seamless skin transition, matching skin tone with surrounding body, photorealistic, professional studio photography, soft lighting, sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd",
        description=(
            "**Inpainting prompt** — what the AI generates in the masked area.\n"
            "Leave as default for best results. Customize only if you know what you're doing."
        ),
    ),
    negative_prompt: str = Form(
        default="(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limbs, missing limbs, floating limbs, severed limbs, mutated hands and fingers, extra fingers, missing fingers, long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, clothes, fabric, bra, straps, underwear, pattern, floral, textile, cartoon, anime, sketch, (changed pose, moved body, different position, rotated torso:1.5), (shifted weight, leaning, tilting, bending, twisting:1.4), (new angle, different posture:1.3)",
        description=(
            "**Negative prompt** — what the AI should avoid.\n"
            "Leave as default for best results."
        ),
    ),
    box_threshold: float = Form(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="**SE10 detection threshold.** Higher = fewer but more confident detections. Default 0.10 works well.",
    ),
    text_threshold: float = Form(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="**SE10 text matching threshold.** Higher = stricter class matching. Default 0.10 works well.",
    ),
    inpaint_strength: float = Form(
        default=0.65,
        ge=0.0,
        le=1.0,
        description=(
            "**Inpainting strength.** In `nsfw` mode, the pipeline overrides this with a retry loop "
            "(0.65 → 0.70 → 0.75). In `clothes`/`person` modes, the pipeline uses 0.70."
        ),
    ),
    per_garment: bool = Form(
        default=False,
        description="**Inpaint each garment separately.** Slower but higher quality. Only used in `clothes` mode.",
    ),
    webhook_url: str | None = Form(
        default=None,
        description="**Webhook URL** for completion notification (POST with job status).",
    ),
    detector: DetectorType = Form(
        default=DetectorType.GROUNDINGDINO,
        description=(
            "**Detection engine:**\n"
            "- `groundingdino` ⭐ — Default. Best overall accuracy.\n"
            "- `florence2` — Alternative. Good for fine-grained classes."
        ),
    ),
) -> CreateClothesRemovalResponse:
    # ── Validate file type ──
    allowed_types = {"image/png", "image/jpeg", "image/webp", "image/jpg"}
    if file.content_type and file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Allowed: PNG, JPEG, WebP",
        )

    # ── Read file → base64 ──
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum: 20MB.")

    image_b64 = base64.b64encode(content).decode("utf-8")
    mime = file.content_type or "image/png"
    image_data_uri = f"data:{mime};base64,{image_b64}"

    # ── Create job ──
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    request_data = {
        "image": image_data_uri,
        "mode": mode.value,
        "classes": classes,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "box_threshold": box_threshold,
        "text_threshold": text_threshold,
        "inpaint_strength": inpaint_strength,
        "per_garment": per_garment,
        "webhook_url": webhook_url,
        "detector": detector.value,
    }

    job = ClothesRemovalJob(
        job_id=job_id,
        request=request_data,
    )

    store.save_job(job_id, job.model_dump(mode="json"))

    worker = get_worker()
    worker.start()

    return CreateClothesRemovalResponse(
        job_id=job_id,
        status="queued",
        message="Clothes removal job started",
    )


@router.get(
    "/jobs",
    response_model=ListJobsResponse,
    summary="List all jobs",
    description=(
        "Returns a paginated list of all clothes removal jobs.\n\n"
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
                objects_detected=j.get("objects_detected"),
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
        "Get the current status and progress of a clothes removal job.\n\n"
        "**Polling:** Call this endpoint every 5–10 seconds while `status` is\n"
        "`queued`, `detecting`, or `inpainting`. The job is finished when\n"
        "`status` is `completed` or `failed`.\n\n"
        "**Output:** When completed, use `GET /jobs/{job_id}/download`\n"
        "to download the result PNG image."
    ),
    responses={
        200: {"description": "Job status"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_job_status(job_id: str) -> JobStatusResponse:
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=job_data["job_id"],
        status=job_data["status"],
        progress=job_data.get("progress", 0),
        stages=job_data.get("stages", {}),
        objects_detected=job_data.get("objects_detected"),
        created_at=job_data.get("created_at", ""),
        error=job_data.get("error"),
        result_path=job_data.get("result_path"),
    )


@router.delete(
    "/jobs/{job_id}",
    response_model=DeleteJobResponse,
    summary="Delete job",
    description=(
        "Delete a clothes removal job and all its output files.\n\n"
        "**Warning:** This action is irreversible. All output images,\n"
        "debug grids, and attempt data will be permanently removed."
    ),
    responses={
        200: {"description": "Job deleted"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def delete_job(job_id: str) -> DeleteJobResponse:
    job_data = store.get_job(job_id)
    if not job_data:
        raise HTTPException(status_code=404, detail="Job not found")

    output_dir = os.path.join(settings.output_dir, job_id)
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)

    result_path = job_data.get("result_path")
    if result_path and os.path.exists(result_path):
        os.remove(result_path)

    store.delete_job(job_id)
    return DeleteJobResponse(
        message=f"Job {job_id} deleted",
        job_id=job_id,
    )
