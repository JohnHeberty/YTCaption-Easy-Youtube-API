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
                description="Removes entire torso region. Head is preserved via adaptive detection.",
            ),
            ModeInfo(
                name="nsfw",
                description=(
                    "Production NSFW pipeline (5 attempts + scoring + pose validation). "
                    "Fixed quality standards, no parameter tuning. Use POST /jobs."
                ),
                recommended=True,
            ),
            ModeInfo(
                name="nsfw_test",
                description=(
                    "Experimental NSFW pipeline with full parameter control. "
                    "Use POST /nsfw-test for all experimental parameters."
                ),
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
    summary="Create clothes removal job (production)",
    description=(
        "Upload an AI-generated image and start a **production** clothes removal pipeline.\n\n"
        "## Workflow\n"
        "1. **SE10** detects the person and clothing items\n"
        "2. **Head protection** via adaptive detection\n"
        "3. **SE8** inpaints the masked region (5 attempts in `nsfw` mode)\n"
        "4. **Pose validation** ensures the result matches the input pose\n"
        "5. Returns the best result across all attempts\n\n"
        "## Modes\n"
        "| Mode | Description |\n|------|-------------|\n"
        "| `nsfw` ⭐ | Production NSFW pipeline (5 attempts + scoring + pose validation) |\n"
        "| `clothes` | Removes detected clothing items |\n"
        "| `person` | Removes entire torso (head preserved) |\n\n"
        "**Note:** For `nsfw_test` (experimental), use `POST /nsfw-test`."
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
            "Only AI-generated images are allowed."
        ),
    ),
    mode: RemovalMode = Form(
        default=RemovalMode.NSFW,
        description=(
            "**Processing mode:**\n"
            "- `nsfw` ⭐ — Production pipeline (5 attempts, scoring, pose validation).\n"
            "- `clothes` — Removes detected clothing items.\n"
            "- `person` — Removes entire torso (head preserved)."
        ),
    ),
    classes: str | None = Form(
        default="spaghetti strap, camisole, top, blouse",
        description=(
            "**Clothing classes to detect** (comma-separated).\n"
            "Only used in `clothes` mode. Ignored in `nsfw` mode."
        ),
    ),
    prompt: str = Form(
        default="NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, detailed breast anatomy, realistic nipples, areola details, natural skin pores, skin texture, skin imperfections, realistic body proportions, maintaining exact same body posture, keeping original body position, not moving, not rotating, same stance, identical pose, skin tone matching the person's arms and face, consistent skin color throughout, seamless skin transition, matching skin tone with surrounding body, photorealistic, professional studio photography, soft lighting, sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd",
        description="Inpainting prompt. Leave default for best results.",
    ),
    negative_prompt: str = Form(
        default="(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limbs, missing limbs, floating limbs, severed limbs, mutated hands and fingers, extra fingers, missing fingers, long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, clothes, fabric, bra, straps, underwear, pattern, floral, textile, cartoon, anime, sketch, (changed pose, moved body, different position, rotated torso:1.5), (shifted weight, leaning, tilting, bending, twisting:1.4), (new angle, different posture:1.3)",
        description="Negative prompt. Leave default for best results.",
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
        default=0.65, ge=0.0, le=1.0,
        description="Inpainting strength. In `nsfw` mode, pipeline overrides with retry loop (0.86→0.98).",
    ),
    per_garment: bool = Form(
        default=False,
        description="Inpaint each garment separately. Only used in `clothes` mode.",
    ),
    webhook_url: str | None = Form(
        default=None,
        description="Webhook URL for completion notification.",
    ),
    detector: DetectorType = Form(
        default=DetectorType.GROUNDINGDINO,
        description="Detection engine: `groundingdino` (default) or `florence2`.",
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

    # ── Build request data (production only — no experimental params) ──
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
        message="Clothes removal job started",
    )


# ─── NSFW Test (Experimental) ──────────────────────────────────────────────

@router.post(
    "/nsfw-test",
    response_model=CreateClothesRemovalResponse,
    status_code=201,
    summary="Create nsfw_test job (experimental)",
    description=(
        "Upload an AI-generated image and start an **experimental** nsfw_test pipeline.\n\n"
        "Full parameter control for testing and tuning:\n"
        "- Custom denoising strength progression\n"
        "- Base model selection (LustifyNSFW / JuggernautXL)\n"
        "- FaceID weight tuning\n"
        "- Inpaint mask strategy\n"
        "- Face blending mode\n\n"
        "## Workflow\n"
        "Same as `POST /jobs` but with all experimental parameters exposed."
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
        description="Detection engine: `groundingdino` (default) or `florence2`.",
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
        default="lustifySDXLNSFW_v20-inpainting.safetensors",
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
