"""Concrete local-file storage manager implementing IStorageManager."""

import os
import time
from pathlib import Path
from typing import Optional, List

from ..domain.interfaces import IStorageManager


class LocalFileStorage(IStorageManager):
    """Local filesystem implementation of the storage abstraction.

    Handles raw file I/O (write, read, delete) so that higher-level services
    no longer call open() / os.fsync() / Path.unlink() directly.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()

    # -- IStorageManager -----------------------------------------------------

    def save_file(self, content: bytes, filename: str) -> Path:
        file_path = self._resolve(filename)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        if not (file_path.exists() and file_path.stat().st_size > 0):
            raise OSError(
                f"File was not persisted correctly: {file_path}"
            )

        return file_path

    def get_file(self, path: Path) -> bytes:
        resolved = self._resolve(path) if isinstance(path, str) else path
        with open(resolved, "rb") as f:
            return f.read()

    def delete_file(self, path: Path) -> None:
        p = self._resolve(path) if isinstance(path, str) else path
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass  # caller decides whether to log / raise

    def cleanup_temp_files(self, pattern: str) -> int:
        removed = 0
        for candidate in self.base_dir.glob(pattern):
            if candidate.is_file():
                try:
                    age_days = (time.time() - candidate.stat().st_mtime) / 86400
                    if age_days > 1:
                        candidate.unlink(missing_ok=True)
                        removed += 1
                except OSError:
                    pass

        return removed

    def check_disk_space(self, required_mb: float) -> bool:
        try:
            stat = os.statvfs(str(self.base_dir))
            free_bytes = stat.f_bavail * stat.f_frsize
            required_bytes = int(required_mb * 1024 * 1024)

            return free_bytes >= required_bytes
        except OSError:
            return False

    # -- internal ------------------------------------------------------------

    def _resolve(self, path_like):
        """Return an absolute Path for a filename or relative path."""
        if isinstance(path_like, Path):
            return path_like.absolute()

        p = self.base_dir / str(path_like)
        return p.resolve()


__all__ = ["LocalFileStorage"]
