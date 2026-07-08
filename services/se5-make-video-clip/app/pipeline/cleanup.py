"""
Pipeline Cleanup — Pure filesystem operations for cleaning pipeline stages.

Zero external service dependencies — only pathlib + settings.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from common.log_utils import get_logger

logger = get_logger(__name__)


class PipelineCleanup:
    """Handles all file cleanup across pipeline stages (raw, transform, validate)."""

    def __init__(self, settings: Any) -> None:
        self._settings = settings

    def ensure_directories(self) -> None:
        """Create all required pipeline directories."""
        dirs = [
            'data/raw/shorts',
            'data/raw/audio',
            'data/transform/videos',
            'data/validate/in_progress',
            'data/approved/videos',
            'data/approved/output',
        ]
        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def cleanup_stale_validations(self, job_id: str, max_age_minutes: int = 30) -> None:
        """Remove abandoned validation files from crashed jobs."""
        validate_dir = Path("data/validate/in_progress")
        if not validate_dir.exists():
            return

        current_time = time.time()
        max_age_seconds = max_age_minutes * 60
        cleaned = 0

        for file_path in validate_dir.glob("*_PROCESSING_*.mp4"):
            try:
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    logger.warning(
                        "Cleaning stale validation file: %s (age: %.1f min)",
                        file_path.name, file_age / 60,
                    )
                    file_path.unlink()
                    cleaned += 1
            except Exception as e:
                logger.error("Error cleaning %s: %s", file_path, e)

        if cleaned > 0:
            logger.info("Cleaned %d stale validation files", cleaned)

    def cleanup_rejected_video(self, video_id: str, job_id: str | None = None) -> None:
        """Remove a rejected video from ALL pipeline folders."""
        cleaned = 0

        try:
            shorts_path = Path(self._settings['shorts_cache_dir']) / f"{video_id}.mp4"
            if shorts_path.exists():
                shorts_path.unlink()
                logger.info("Removed from shorts: %s", video_id)
                cleaned += 1

            transform_dir = Path(self._settings['transform_dir'])
            for file_path in transform_dir.glob(f"{video_id}*.mp4"):
                file_path.unlink()
                logger.info("Removed from transform: %s", file_path.name)
                cleaned += 1

            validate_dir = Path(self._settings['validate_dir']) / "in_progress"
            if job_id:
                pattern = f"{job_id}_{video_id}*.mp4"
            else:
                pattern = f"*_{video_id}*.mp4"
            for file_path in validate_dir.glob(pattern):
                file_path.unlink()
                logger.info("Removed from validate: %s", file_path.name)
                cleaned += 1

            if cleaned > 0:
                logger.info("Cleaned %d files for rejected video: %s", cleaned, video_id)

        except Exception as e:
            logger.error("Error cleaning rejected video %s: %s", video_id, e)

    def cleanup_orphaned_files(self, max_age_minutes: int = 30) -> None:
        """Remove orphaned files older than max_age from all pipeline folders."""
        now = time.time()
        max_age_seconds = max_age_minutes * 60
        cleaned_total = 0

        folders = {
            'shorts': Path(self._settings['shorts_cache_dir']),
            'transform': Path(self._settings['transform_dir']),
            'validate': Path(self._settings['validate_dir']) / 'in_progress',
        }

        for folder_name, folder_path in folders.items():
            if not folder_path.exists():
                continue

            cleaned = 0
            try:
                for file_path in folder_path.glob("*.mp4"):
                    file_age = now - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        logger.warning(
                            "Cleaning orphaned file in %s: %s (age: %.1f min)",
                            folder_name, file_path.name, file_age / 60,
                        )
                        file_path.unlink()
                        cleaned += 1
                        cleaned_total += 1
            except Exception as e:
                logger.error("Error cleaning %s: %s", folder_name, e)

            if cleaned > 0:
                logger.info("Cleaned %d files from %s/", cleaned, folder_name)

        if cleaned_total > 0:
            logger.info(
                "Total orphaned files cleaned: %d (age > %d min)",
                cleaned_total, max_age_minutes,
            )
        else:
            logger.debug("No orphaned files found (age > %d min)", max_age_minutes)

    def cleanup_job_files(self, job_id: str) -> None:
        """Remove ALL files related to a specific job across all pipeline stages."""
        cleaned_total = 0

        folders = {
            'shorts': Path(self._settings['shorts_cache_dir']),
            'transform': Path(self._settings['transform_dir']),
            'validate': Path(self._settings['validate_dir']) / 'in_progress',
        }

        logger.info("Starting cleanup for job %s across all pipeline stages...", job_id)

        for folder_name, folder_path in folders.items():
            if not folder_path.exists():
                logger.debug("Skipping %s (folder doesn't exist)", folder_name)
                continue

            cleaned = 0
            try:
                pattern = f"{job_id}_*.mp4"
                for file_path in folder_path.glob(pattern):
                    logger.debug("Removing %s/%s", folder_name, file_path.name)
                    file_path.unlink()
                    cleaned += 1
                    cleaned_total += 1

                if cleaned > 0:
                    logger.info("Cleaned %d files from %s/ for job %s", cleaned, folder_name, job_id)
            except Exception as e:
                logger.error("Error cleaning %s for job %s: %s", folder_name, job_id, e)

        if cleaned_total > 0:
            logger.info("Job %s cleanup complete: %d files removed", job_id, cleaned_total)
        else:
            logger.debug("No files found for job %s (already cleaned or no files created)", job_id)

    def cleanup_previous_stages(self, video_id: str) -> None:
        """Remove video from previous pipeline stages (raw + transform)."""
        logger.info("CLEANUP: Removing %s from previous stages", video_id)

        raw_dir = Path("data/raw/shorts")
        transform_dir = Path("data/transform/videos")

        for path in raw_dir.glob(f"{video_id}.*"):
            if path.is_file():
                path.unlink()
                logger.info("  Removed: %s", path)

        for path in transform_dir.glob(f"{video_id}.*"):
            if path.is_file():
                path.unlink()
                logger.info("  Removed: %s", path)

    def cleanup_all_stages(self, video_id: str) -> None:
        """Remove video from ALL pipeline stages (raw + transform + validate)."""
        logger.info("CLEANUP COMPLETO: Removing %s from all stages", video_id)

        stage_dirs = [
            Path("data/raw/shorts"),
            Path("data/transform/videos"),
            Path("data/validate/in_progress"),
        ]

        for stage_dir in stage_dirs:
            for path in stage_dir.glob(f"{video_id}.*"):
                if path.is_file():
                    path.unlink()
                    logger.info("  Removed: %s", path)
