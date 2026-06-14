"""Handle file uploads for transcription jobs.

Validates uploaded content, persists to disk with retry semantics, and returns
file metadata ready to be attached to a ``Job`` instance.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional


class FileUploadError(Exception):
    """Raised when file upload or persistence fails."""


class FileUploadHandler:
    """Save uploaded files with retry and fsync guarantees."""

    def __init__(self, upload_dir: str) -> None:
        self.upload_dir = Path(upload_dir).resolve()
        self._ensure_upload_dir()

    # -- public API ------------------------------------------------------------

    async def save_file(
        self,
        file_content: bytes,
        original_filename: Optional[str],
        job_id: str,
        max_retries: int = 3,
    ) -> Path:
        """Persist *file_content* under ``upload_dir/<job_id><ext>``.

        Returns the absolute path to the saved file.
        Raises :class:`FileUploadError` on validation or persistence failure.
        """
        if not file_content:
            raise FileUploadError("Arquivo enviado está vazio")

        original_extension = Path(original_filename).suffix if original_filename else ""
        file_path = self.upload_dir / f"{job_id}{original_extension}"

        saved = await self._write_with_retry(file_path, file_content, max_retries)
        return saved.resolve()

    # -- internal --------------------------------------------------------------

    def _ensure_upload_dir(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    async def _write_with_retry(
        self, path: Path, content: bytes, max_retries: int
    ) -> Path:
        for attempt in range(max_retries):
            try:
                with open(path, "wb") as fh:
                    fh.write(content)
                    fh.flush()
                    os.fsync(fh.fileno())

                if path.exists() and path.stat().st_size > 0:
                    return path
            except Exception as exc:
                raise FileUploadError(
                    f"Falha ao salvar arquivo após {max_retries} tentativas"
                ) from exc

            time.sleep(0.5 * (attempt + 1))

        raise FileUploadError(f"Falha ao salvar arquivo após {max_retries} tentativas")
