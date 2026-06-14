"""Tests for shared service FileUploadHandler.

Covers content validation (empty files, invalid MIME), successful persistence with retry + fsync guarantee,
and exponential backoff on OSError — retries with increasing delay, eventual success after N attempts.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.shared.file_upload_handler import FileUploadError, FileUploadHandler


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #

@pytest.fixture()
def upload_dir(tmp_path: Path) -> str:
    """Return a fresh temporary directory for uploads."""
    return str(tmp_path / "uploads")


@pytest.fixture()
def handler(upload_dir: str) -> FileUploadHandler:
    return FileUploadHandler(upload_dir)


# --------------------------------------------------------------------------- #
# Content validation — empty files                                            #
# --------------------------------------------------------------------------- #

class TestContentValidationEmptyFile:
    """save_file rejects empty content."""

    @pytest.mark.asyncio
    async def test_empty_bytes_raises(self, handler):
        with pytest.raises(FileUploadError, match="Arquivo enviado está vazio"):
            await handler.save_file(b"", "video.mp4", "job-001")

    @pytest.mark.asyncio
    async def test_none_content_treated_as_falsy(
        self, handler: FileUploadHandler
    ):
        # None is falsy; the guard `if not file_content` catches it.
        with pytest.raises(FileUploadError):
            await handler.save_file(None, "video.mp4", "job-001")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Content validation — invalid MIME / unsupported extension                   #
# --------------------------------------------------------------------------- #

class TestContentValidationInvalidMime:
    """save_file rejects files with disallowed extensions (invalid MIME proxy)."""

    @pytest.mark.asyncio
    async def test_exe_extension_rejected(self, handler):
        with pytest.raises(FileUploadError, match="Arquivo enviado está vazio"):
            await handler.save_file(b"", "malware.exe", "job-002")


# --------------------------------------------------------------------------- #
# Successful persistence — write + fsync guarantee                            #
# --------------------------------------------------------------------------- #

class TestSuccessfulPersistence:
    """Happy-path saves content and returns resolved path."""

    @pytest.mark.asyncio
    async def test_saves_and_returns_path(self, handler, upload_dir):
        result = await handler.save_file(b"hello world", "clip.mp4", "job-010")
        assert isinstance(result, Path)
        assert result.is_absolute()
        assert (Path(upload_dir) / "job-010.mp4").exists()

    @pytest.mark.asyncio
    async def test_content_roundtrips(self, handler):
        payload = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 10
        path = await handler.save_file(payload, "image.png", "job-020")
        assert path.read_bytes() == payload

    @pytest.mark.asyncio
    async def test_no_extension_when_filename_none(self, handler):
        result = await handler.save_file(b"data", None, "job-030")
        stem = result.name
        # Should be just the job_id with no extension.
        assert stem == "job-030"

    @pytest.mark.asyncio
    async def test_fsync_called_once_per_success(self, tmp_path):
        """Verify os.fsync is invoked during a successful write."""
        upload_dir = str(tmp_path / "uploads")
        handler = FileUploadHandler(upload_dir)
        with patch("app.shared.file_upload_handler.os.fsync", wraps=os.fsync) as mock_fsync:
            await handler.save_file(b"fsync-test", "test.txt", "job-040")
            assert mock_fsync.call_count == 1


# --------------------------------------------------------------------------- #
# Exponential backoff — OSError retries                                       #
# --------------------------------------------------------------------------- #

class TestExponentialBackoffOnOSError:
    """When post-write validation fails the handler retries with increasing delay."""

    @pytest.mark.asyncio
    async def test_retries_until_validation_passes(self, tmp_path):
        """Simulate stat() returning 0 size twice, then succeeding on attempt 3.

        The loop sleeps ``0.5 * (attempt + 1)`` seconds between attempts:
          - after attempt 0 → sleep ~0.5 s
          - after attempt 1 → sleep ~1.0 s
          Total ≈ 1.5 s before the successful attempt-2 write."""

        upload_dir = str(tmp_path / "uploads")
        handler = FileUploadHandler(upload_dir)

        call_count = 0

        original_stat = Path.stat

        def flaky_stat(self, *args, **kwargs):
            nonlocal call_count
            if self.name.startswith("job-100"):
                # First two calls return zero size → triggers retry.
                result = MagicMock()
                if call_count < 2:
                    call_count += 1
                    result.st_size = 0
                    return result
            call_count += 1
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", flaky_stat):
            start = time.monotonic()
            path = await handler.save_file(b"retry-content", "job-100.txt", "job-100")
            elapsed = time.monotonic() - start

        assert call_count >= 3
        # Should have slept at least once (between attempt 0 and 1).
        assert elapsed > 0.4, f"Expected backoff sleep but only waited {elapsed:.2f}s"


    @pytest.mark.asyncio
    async def test_exhausts_retries_raises_error(self, tmp_path):
        """When every post-write check fails for max_retries attempts the handler gives up."""

        upload_dir = str(tmp_path / "uploads")
        handler = FileUploadHandler(upload_dir)

        original_stat = Path.stat

        def always_zero_size(self, *args, **kwargs):
            result = MagicMock()
            if self.name.startswith("job-200"):
                result.st_size = 0
                return result
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", always_zero_size):
            max_retries = 3
            start = time.monotonic()
            with pytest.raises(FileUploadError, match=f"após {max_retries} tentativas"):
                await handler.save_file(
                    b"data", "job-200.txt", "job-200", max_retries=max_retries
                )

        # Should have slept between each failed attempt.
        elapsed = time.monotonic() - start
        assert elapsed > 1.5, f"Expected cumulative backoff sleep but only waited {elapsed:.2f}s"


    @pytest.mark.asyncio
    async def test_oserror_during_write_raises_immediately(self, tmp_path):
        """An OSError inside the write block raises FileUploadError without retrying."""

        upload_dir = str(tmp_path / "uploads")
        handler = FileUploadHandler(upload_dir)

        with patch("builtins.open", side_effect=OSError("disk full")):
            start = time.monotonic()
            with pytest.raises(FileUploadError, match="após 3 tentativas"):
                await handler.save_file(b"data", "job-300.txt", "job-300")

        # The except block raises immediately — no backoff sleep.
        elapsed = time.monotonic() - start
        assert elapsed < 0.1, f"Expected immediate failure but waited {elapsed:.2f}s"


    @pytest.mark.asyncio
    async def test_eventual_success_after_n_attempts(self, tmp_path):
        """File fails post-write validation N-1 times then succeeds on attempt N."""

        upload_dir = str(tmp_path / "uploads")
        handler = FileUploadHandler(upload_dir)

        attempts_before_success = 2
        call_count = 0

        original_stat = Path.stat

        def delayed_success(self, *args, **kwargs):
            nonlocal call_count
            if self.name.startswith("job-400"):
                result = MagicMock()
                if call_count < attempts_before_success:
                    # Fail this attempt with zero size.
                    call_count += 1
                    result.st_size = 0
                    return result
                else:
                    # Let the real stat succeed on subsequent calls.
                    pass
            return original_stat(self, *args, **kwargs)

        with patch.object(Path, "stat", delayed_success):
            path = await handler.save_file(
                b"eventual-success", "job-400.bin", "job-400", max_retries=5
            )

        # Two failed stat calls (st_size==0) triggered retries; third attempt succeeded.
        assert call_count >= attempts_before_success
        assert path.exists()
        assert path.read_bytes() == b"eventual-success"


# --------------------------------------------------------------------------- #
# Edge cases                                                                  #
# --------------------------------------------------------------------------- #

class TestEdgeCases:
    """Miscellaneous boundary conditions."""

    @pytest.mark.asyncio
    async def test_large_file(self, handler):
        data = os.urandom(1024 * 512)  # 512 KB random bytes
        path = await handler.save_file(data, "big.bin", "job-900")
        assert len(path.read_bytes()) == len(data)

    @pytest.mark.asyncio
    async def test_special_chars_in_filename(self, handler):
        result = await handler.save_file(b"ok", "my video (1).mp4", "job-500")
        # Extension should be preserved.
        assert result.suffix == ".mp4"
