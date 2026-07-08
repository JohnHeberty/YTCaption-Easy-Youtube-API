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
from app.services._helpers import DEFAULT_BASE_MODEL
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
                description="Detects and removes detected clothing items. Use POST /jobs.",
                recommended=True,
            ),
            ModeInfo(
                name="person",
                description="Removes entire torso region. Head preserved. Use POST /jobs.",
            ),
            ModeInfo(
                name="nsfw",
                description="Production NSFW pipeline (5 attempts + scoring + pose validation). Use POST /jobs/nsfw.",
                recommended=True,
            ),
            ModeInfo(
                name="nsfw_test",
                description="Experimental NSFW pipeline with full parameter control. Use POST /jobs/nsfw-test.",
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
                name="segformer",
                description="Pixel-level clothing segmentation (18 classes). Recommended for clothes mode.",
            ),
            DetectorInfo(
                name="ensemble",
                description="Multi-detector consensus (GD+YOLO+BiRefNet+SegFormer). Best accuracy.",
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
        supported_detectors=["groundingdino", "segformer", "ensemble"],
        endpoints={
            "jobs": "POST /jobs — production (nsfw, clothes, person)",
            "nsfw_test": "POST /nsfw-test — experimental (full parameter control)",
        },
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
    summary="Create clothes/person removal job",
    description=(
        "Upload an AI-generated image and start a clothes or person removal pipeline.\n\n"
        "## Modes\n"
        "| Mode | Description |\n|------|-------------|\n"
        "| `clothes` | Default — removes detected clothing |\n"
        "| `person` | Removes entire torso (head preserved) |\n\n"
        "**NSFW?** Use `POST /jobs/nsfw` (production) or `POST /jobs/nsfw-test` (experimental).\n\n"
        "**Upscale?** `upscale=true` (default) applies 4x-UltraSharp ESRGAN after inpainting. `upscale=false` returns original resolution."
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
        description="AI-generated image file (PNG, JPEG, WebP).",
    ),
    mode: RemovalMode = Form(
        default=RemovalMode.CLOTHES,
        description="Processing mode: `clothes` (default) or `person`.",
    ),
    classes: str | None = Form(
        default="spaghetti strap, camisole, top, blouse",
        description="Clothing classes to detect (comma-separated).",
    ),
    prompt: str = Form(
        default="bare skin, realistic skin texture, photorealistic",
        description="Inpainting prompt.",
    ),
    negative_prompt: str = Form(
        default="deformed, blurry, cartoon, low quality",
        description="Negative prompt.",
    ),
    box_threshold: float = Form(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 detection threshold.",
    ),
    text_threshold: float = Form(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 text matching threshold.",
    ),
    inpaint_strength: float = Form(
        default=0.70, ge=0.0, le=1.0,
        description="SE8 inpaint denoise strength.",
    ),
    per_garment: bool = Form(
        default=False,
        description="Inpaint each garment separately.",
    ),
    webhook_url: str | None = Form(
        default=None,
        description="Webhook URL for completion notification.",
    ),
    detector: DetectorType = Form(
        default=DetectorType.GROUNDINGDINO,
        description="Detection engine: `groundingdino` (default), `segformer`, or `ensemble`.",
    ),
    face_restore: bool = Form(
        default=False,
        description="Apply face restoration (CodeFormer/GFPGAN) after compositing.",
    ),
    face_restore_model: str = Form(
        default="CodeFormer",
        description="Face restoration model: `CodeFormer` or `GFPGAN`.",
    ),
    face_restore_fidelity: float = Form(
        default=0.5, ge=0.0, le=1.0,
        description="CodeFormer fidelity: 0.0 = more restoration, 1.0 = more identity.",
    ),
    upscale: bool = Form(
        default=True,
        description="Apply 4x-UltraSharp ESRGAN upscale after inpainting. Default: true.",
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
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum: {settings.max_file_size_mb}MB.")

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
        "upscale": upscale,
        "face_restore": face_restore,
        "face_restore_model": face_restore_model,
        "face_restore_fidelity": face_restore_fidelity,
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
        message="Job started",
    )


# ─── NSFW Production ────────────────────────────────────────────────────────

@router.post(
    "/jobs/nsfw",
    response_model=CreateClothesRemovalResponse,
    status_code=201,
    summary="Create NSFW production job",
    description=(
        "Upload an AI-generated image and start the **production** NSFW pipeline.\n\n"
        "Fixed quality standards — no parameter tuning:\n"
        "- 5 attempts with progressive strength (0.86→0.98)\n"
        "- LustifyNSFW model (NSFW+inpainting specialist)\n"
        "- Multidimensional scoring (skin + pose + clothes)\n"
        "- Pose validation (MediaPipe)\n"
        "- FaceID identity preservation\n"
        "- 4x-UltraSharp ESRGAN upscale (`upscale=false` to skip)"
    ),
    responses={
        201: {"description": "Job created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid file type or size"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_nsfw_job(
    file: UploadFile = File(
        ...,
        description="AI-generated image file (PNG, JPEG, WebP).",
    ),
    prompt: str = Form(
        default="NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, detailed breast anatomy, realistic nipples, areola details, natural skin pores, skin texture, skin imperfections, realistic body proportions, maintaining exact same body posture, keeping original body position, not moving, not rotating, same stance, identical pose, skin tone matching the person's arms and face, consistent skin color throughout, seamless skin transition, matching skin tone with surrounding body, photorealistic, professional studio photography, soft lighting, sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd",
        description="Inpainting prompt.",
    ),
    negative_prompt: str = Form(
        default="(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limbs, missing limbs, floating limbs, severed limbs, mutated hands and fingers, extra fingers, missing fingers, long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, clothes, fabric, bra, straps, underwear, pattern, floral, textile, cartoon, anime, sketch, (changed pose, moved body, different position, rotated torso:1.5), (shifted weight, leaning, tilting, bending, twisting:1.4), (new angle, different posture:1.3)",
        description="Negative prompt.",
    ),
    box_threshold: float = Form(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 detection threshold.",
    ),
    text_threshold: float = Form(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 text matching threshold.",
    ),
    webhook_url: str | None = Form(
        default=None,
        description="Webhook URL for completion notification.",
    ),
    detector: DetectorType = Form(
        default=DetectorType.GROUNDINGDINO,
        description="Detection engine: `groundingdino` (default), `segformer`, or `ensemble`.",
    ),
    face_restore: bool = Form(
        default=False,
        description="Apply face restoration (CodeFormer/GFPGAN) after compositing.",
    ),
    face_restore_model: str = Form(
        default="CodeFormer",
        description="Face restoration model: `CodeFormer` or `GFPGAN`.",
    ),
    face_restore_fidelity: float = Form(
        default=0.5, ge=0.0, le=1.0,
        description="CodeFormer fidelity: 0.0 = more restoration, 1.0 = more identity.",
    ),
    upscale: bool = Form(
        default=True,
        description="Apply 4x-UltraSharp ESRGAN upscale after inpainting. Default: true.",
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
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum: {settings.max_file_size_mb}MB.")

    image_b64 = base64.b64encode(content).decode("utf-8")
    mime = file.content_type or "image/png"
    image_data_uri = f"data:{mime};base64,{image_b64}"

    # ── Create job ──
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    request_data = {
        "image": image_data_uri,
        "mode": "nsfw",
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "box_threshold": box_threshold,
        "text_threshold": text_threshold,
        "webhook_url": webhook_url,
        "detector": detector.value,
        "upscale": upscale,
        "face_restore": face_restore,
        "face_restore_model": face_restore_model,
        "face_restore_fidelity": face_restore_fidelity,
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
        message="NSFW job started",
    )


# ─── NSFW Test (Experimental) ──────────────────────────────────────────────

@router.post(
    "/jobs/nsfw-test",
    response_model=CreateClothesRemovalResponse,
    status_code=201,
    summary="Create NSFW test job (experimental)",
    description=(
        "Upload an AI-generated image and start an **experimental** nsfw_test pipeline.\n\n"
        "Full parameter control for testing and tuning:\n"
        "- Custom denoising strength progression\n"
        "- Base model selection (LustifyNSFW / JuggernautXL)\n"
        "- FaceID weight tuning\n"
        "- Inpaint mask strategy\n"
        "- Face blending mode\n"
        "- 4x-UltraSharp ESRGAN upscale (`upscale=false` to skip)"
    ),
    responses={
        201: {"description": "Job created successfully"},
        400: {"model": ErrorResponse, "description": "Invalid file type or size"},
        422: {"model": ErrorResponse, "description": "Validation error"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_nsfw_test_job(
    file: UploadFile = File(
        ...,
        description="AI-generated image file (PNG, JPEG, WebP).",
    ),
    classes: str | None = Form(
        default="spaghetti strap, camisole, top, blouse",
        description="Clothing classes to detect (comma-separated). Ignored in nsfw_test.",
    ),
    prompt: str = Form(
        default="NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, detailed breast anatomy, realistic nipples, areola details, natural skin pores, skin texture, skin imperfections, realistic body proportions, maintaining exact same body posture, keeping original body position, not moving, not rotating, same stance, identical pose, skin tone matching the person's arms and face, consistent skin color throughout, seamless skin transition, matching skin tone with surrounding body, photorealistic, professional studio photography, soft lighting, sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd",
        description="Inpainting prompt.",
    ),
    negative_prompt: str = Form(
        default="(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limbs, missing limbs, floating limbs, severed limbs, mutated hands and fingers, extra fingers, missing fingers, long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, clothes, fabric, bra, straps, underwear, pattern, floral, textile, cartoon, anime, sketch, (changed pose, moved body, different position, rotated torso:1.5), (shifted weight, leaning, tilting, bending, twisting:1.4), (new angle, different posture:1.3)",
        description="Negative prompt.",
    ),
    box_threshold: float = Form(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 detection threshold.",
    ),
    text_threshold: float = Form(
        default=0.10, ge=0.0, le=1.0,
        description="SE10 text matching threshold.",
    ),
    inpaint_strength: float = Form(
        default=1.0, ge=0.0, le=1.0,
        description="SE8 inpaint denoise strength.",
    ),
    per_garment: bool = Form(
        default=False,
        description="Inpaint each garment separately.",
    ),
    webhook_url: str | None = Form(
        default=None,
        description="Webhook URL for completion notification.",
    ),
    detector: DetectorType = Form(
        default=DetectorType.GROUNDINGDINO,
        description="Detection engine: `groundingdino` (default), `segformer`, or `ensemble`.",
    ),
    inpaint_mode: str = Form(
        default="invert_mask",
        description="Mask strategy: `body_mask`, `clothes_mask`, or `invert_mask` (default).",
    ),
    use_faceid: bool = Form(
        default=True,
        description="Enable IP-Adapter FaceID to preserve facial identity.",
    ),
    faceid_weight: float = Form(
        default=0.8, ge=0.0, le=1.5,
        description="IP-Adapter FaceID weight (0.7-1.0 recommended).",
    ),
    test_inpaint_strength: float = Form(
        default=0.86, ge=0.0, le=1.0,
        description="Base denoising strength. Pipeline runs 5 attempts from this value (0.86→0.98).",
    ),
    base_model: str = Form(
        default=DEFAULT_BASE_MODEL,
        description="Base SDXL checkpoint. LustifyNSFW (recommended) or JuggernautXL.",
    ),
    face_blend_mode: str = Form(
        default="laplacian",
        description="Face-body blending: `laplacian` (smoother) or `alpha` (legacy).",
    ),
    face_restore: bool = Form(
        default=False,
        description="Apply face restoration (CodeFormer/GFPGAN) after compositing.",
    ),
    face_restore_model: str = Form(
        default="CodeFormer",
        description="Face restoration model: `CodeFormer` or `GFPGAN`.",
    ),
    face_restore_fidelity: float = Form(
        default=0.5, ge=0.0, le=1.0,
        description="CodeFormer fidelity: 0.0 = more restoration, 1.0 = more identity.",
    ),
    upscale: bool = Form(
        default=True,
        description="Apply 4x-UltraSharp ESRGAN upscale after inpainting. Default: true.",
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
    if len(content) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum: {settings.max_file_size_mb}MB.")

    image_b64 = base64.b64encode(content).decode("utf-8")
    mime = file.content_type or "image/png"
    image_data_uri = f"data:{mime};base64,{image_b64}"

    # ── Create job ──
    job_id = f"{JOB_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    request_data = {
        "image": image_data_uri,
        "mode": "nsfw_test",
        "classes": classes,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "box_threshold": box_threshold,
        "text_threshold": text_threshold,
        "inpaint_strength": inpaint_strength,
        "per_garment": per_garment,
        "webhook_url": webhook_url,
        "detector": detector.value,
        "inpaint_mode": inpaint_mode,
        "use_faceid": use_faceid,
        "faceid_weight": faceid_weight,
        "test_inpaint_strength": test_inpaint_strength,
        "base_model": base_model,
        "face_blend_mode": face_blend_mode,
        "upscale": upscale,
        "face_restore": face_restore,
        "face_restore_model": face_restore_model,
        "face_restore_fidelity": face_restore_fidelity,
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
        message="NSFW test job started",
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
