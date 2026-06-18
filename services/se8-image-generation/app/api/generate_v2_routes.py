"""V2 Generation routes for SE8 Image Engine.

V2 uses JSON with base64-encoded images.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Header, Query

from app.api.api_utils import call_worker
from app.domain.models import (
    GeneratedImageResult,
    ImageEnhanceRequestJson,
    ImagePromptJson,
    ImgInpaintOrOutpaintRequestJson,
    ImgPromptRequestJson,
    ImgUpscaleOrVaryRequestJson,
    Text2ImgRequestWithPrompt,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/generation", tags=["GenerateV2"])


@router.post(
    "/text-to-image-with-ip",
    tags=["GenerateV2"],
)
def text_to_image_with_ip(
    req: Text2ImgRequestWithPrompt,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None,
        alias="accept",
        description="Override Accept header, 'image/png' for output bytes",
    ),
):
    """Text to image with image prompts (JSON, base64 images)."""
    if accept_query:
        accept = accept_query
    while len(req.image_prompts) <= 4:
        req.image_prompts.append(ImagePromptJson())
    return call_worker(req, accept)


@router.post(
    "/image-upscale-vary",
    tags=["GenerateV2"],
)
def image_upscale_vary_v2(
    req: ImgUpscaleOrVaryRequestJson,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image upscale or vary (V2 — JSON)."""
    if accept_query:
        accept = accept_query
    while len(req.image_prompts) <= 4:
        req.image_prompts.append(ImagePromptJson())
    return call_worker(req, accept)


@router.post(
    "/image-inpaint-outpaint",
    tags=["GenerateV2"],
)
def image_inpaint_outpaint_v2(
    req: ImgInpaintOrOutpaintRequestJson,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image inpaint or outpaint (V2 — JSON)."""
    if accept_query:
        accept = accept_query
    while len(req.image_prompts) <= 4:
        req.image_prompts.append(ImagePromptJson())
    return call_worker(req, accept)


@router.post(
    "/image-prompt",
    tags=["GenerateV2"],
)
def image_prompt_v2(
    req: ImgPromptRequestJson,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image prompt (V2 — JSON)."""
    if accept_query:
        accept = accept_query
    while len(req.image_prompts) <= 4:
        req.image_prompts.append(ImagePromptJson())
    return call_worker(req, accept)


@router.post(
    "/image-enhance",
    tags=["GenerateV2"],
)
def image_enhance_v2(
    req: ImageEnhanceRequestJson,
    accept: Optional[str] = Header(None),
    accept_query: Optional[str] = Query(
        None, alias="accept", description="Override Accept header"
    ),
):
    """Image enhance (V2 — JSON)."""
    if accept_query:
        accept = accept_query
    return call_worker(req, accept)
