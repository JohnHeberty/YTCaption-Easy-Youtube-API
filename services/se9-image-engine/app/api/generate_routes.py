"""V1 Generation routes for SE9 Image Engine.

Clean-room rewrite of FOOOCUS fooocusapi/routes/generate_v1.py.
V1 accepts multipart/form-data for image inputs.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, File, Header, Query, Request, UploadFile

from app.api.api_utils import call_worker
from app.domain.models import (
    GeneratedImageResult,
    ImageEnhanceRequest,
    ImgInpaintOrOutpaintRequest,
    ImgPromptRequest,
    ImgUpscaleOrVaryRequest,
    TextToImageRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/generation", tags=["GenerateV1"])


@router.post(
    "/text-to-image",
    response_model=List[GeneratedImageResult],
    tags=["GenerateV1"],
)
async def text_to_image(
    request: Request,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None,
        alias="accept",
        description="Override Accept header, 'image/png' for output bytes",
    ),
):
    """Text to Image Generation."""
    if accept_query:
        accept = accept_query
    body = await request.json()
    req = TextToImageRequest(**body)
    return call_worker(req, accept)


@router.post(
    "/image-upscale-vary",
    response_model=List[GeneratedImageResult],
    tags=["GenerateV1"],
)
async def image_upscale_vary(
    request: Request,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image upscale or vary."""
    if accept_query:
        accept = accept_query
    body = await request.json()
    req = ImgUpscaleOrVaryRequest(**body)
    return call_worker(req, accept)


@router.post(
    "/image-inpaint-outpaint",
    response_model=List[GeneratedImageResult],
    tags=["GenerateV1"],
)
async def image_inpaint_outpaint(
    request: Request,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image inpaint or outpaint."""
    if accept_query:
        accept = accept_query
    body = await request.json()
    req = ImgInpaintOrOutpaintRequest(**body)
    return call_worker(req, accept)


@router.post(
    "/image-prompt",
    response_model=List[GeneratedImageResult],
    tags=["GenerateV1"],
)
async def image_prompt(
    request: Request,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image Prompt — prompt-based image generation."""
    if accept_query:
        accept = accept_query
    body = await request.json()
    req = ImgPromptRequest(**body)
    return call_worker(req, accept)


@router.post(
    "/image-enhance",
    response_model=List[GeneratedImageResult],
    tags=["GenerateV1"],
)
async def image_enhance(
    request: Request,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image Enhance."""
    if accept_query:
        accept = accept_query
    body = await request.json()
    req = ImageEnhanceRequest(**body)
    return call_worker(req, accept)
