"""File serving routes for SE9 Image Engine.

Serves generated images by date and filename.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Header, Response
from fastapi.responses import FileResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ACCEPT_FORMATS = {"png", "jpg", "jpeg", "webp"}

router = APIRouter(tags=["Files"])


@router.get("/files/{date}/{file_name}")
def get_output_file(date: str, file_name: str, accept: str = Header(None)):
    """Get a specific output image by date and filename."""
    settings = get_settings()
    output_dir = settings.output_dir

    accept_formats = ACCEPT_FORMATS

    ext = None
    if accept is not None:
        try:
            _, ext = accept.lower().split("/")
            if ext not in accept_formats:
                ext = None
        except ValueError:
            ext = None
    else:
        ext = file_name.split(".")[-1]
        if ext not in accept_formats:
            ext = None

    if not file_name.endswith(tuple(f".{f}" for f in accept_formats)):
        return Response(status_code=404)

    file_path = os.path.join(output_dir, date, file_name)

    if not os.path.isfile(file_path):
        return Response(status_code=404)

    if ext is None:
        try:
            return FileResponse(file_path)
        except FileNotFoundError:
            return Response(status_code=404)

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type=f"image/{ext}")
    except Exception as e:
        logger.error("Failed to serve file %s: %s", file_path, e)
        return Response(status_code=500)
