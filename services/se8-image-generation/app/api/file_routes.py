"""File serving routes for SE8 Image Engine.

Serves generated images by date and filename.
"""

from __future__ import annotations
from common.log_utils import get_logger

import os
from pathlib import Path

from fastapi import APIRouter, Header, Response, status
from fastapi.responses import FileResponse

from app.core.config import get_settings

logger = get_logger(__name__)

ACCEPT_FORMATS = {"png", "jpg", "jpeg", "webp"}

router = APIRouter(tags=["Files"])


@router.get("/files/{date}/{file_name}")
def get_output_file(date: str, file_name: str, accept: str = Header(None)) -> Response:
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
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    file_path = os.path.join(output_dir, date, file_name)

    if not os.path.isfile(file_path):
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    if ext is None:
        try:
            return FileResponse(file_path)
        except FileNotFoundError:
            return Response(status_code=status.HTTP_404_NOT_FOUND)

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type=f"image/{ext}")
    except OSError as e:
        logger.error("Failed to serve file %s: %s", file_path, e)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
