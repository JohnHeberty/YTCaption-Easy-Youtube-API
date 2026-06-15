"""Unit tests for TranscriptionProcessor — timeout, model status, unload, disk space."""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


@pytest.fixture
def proc_with_mocked_init():
    """Create a processor instance without calling real __init__."""
    with patch('app.services.processor.TranscriptionProcessor.__init__', lambda self: None):
        from app.services.processor import TranscriptionProcessor
        p = TranscriptionProcessor()
        return p


# --------------------------------------------------------------------------- #
# _run_with_timeout                                                            #
# --------------------------------------------------------------------------- #


class TestRunWithTimeout:

    @pytest.mark.asyncio
    async def test_success_returns_result(self, proc_with_mocked_init):
        processor = proc_with_mocked_init

        async def sample_coro():
            return "done"

        result = await processor._run_with_timeout(
            sample_coro(), 5, "test_op"
        )

        assert result == "done"

    @pytest.mark.asyncio
    async def test_timeout_raises_exception(self, proc_with_mocked_init):
        processor = proc_with_mocked_init

        from app.shared.exceptions import AudioTranscriptionException

        async def slow_coro():
            await asyncio.sleep(10)
            return "should not reach"

        with pytest.raises(AudioTranscriptionException) as exc_info:
            await processor._run_with_timeout(
                slow_coro(), 0, "slow_op"
            )

        assert "Timeout ao executar 'slow_op' após 0s" in str(exc_info.value)


# --------------------------------------------------------------------------- #
# get_model_status                                                             #
# --------------------------------------------------------------------------- #


class TestGetModelStatus:

    def test_not_loaded_returns_correct_defaults(self, proc_with_mocked_init):
        processor = proc_with_mocked_init
        processor.model_loaded = False
        processor.model = None
        processor.device = 'cpu'
        processor.settings = {'whisper_model': 'small'}

        with patch('app.services.processor.torch.cuda.is_available', return_value=False):
            status = processor.get_model_status()

        assert status["loaded"] is False
        assert status["model_name"] == "small"
        assert status["device"] is None
        assert status["memory"]["cuda_available"] is False
        assert status["memory"]["vram_mb"] == 0.0

    def test_model_name_defaults_to_base(self, proc_with_mocked_init):
        processor = proc_with_mocked_init
        processor.model_loaded = False
        processor.model = None
        processor.device = None
        processor.settings = {}

        with patch('app.services.processor.torch.cuda.is_available', return_value=False):
            status = processor.get_model_status()

        assert status["model_name"] == "base"


# --------------------------------------------------------------------------- #
# unload_model                                                                 #
# --------------------------------------------------------------------------- #


class TestUnloadModel:

    def test_already_unloaded_returns_success(self, proc_with_mocked_init):
        processor = proc_with_mocked_init
        processor.model = None
        processor.model_loaded = False
        processor.settings = {'whisper_model': 'base'}

        report = processor.unload_model()

        assert report["success"] is True
        assert "Modelo já estava descarregado" in report["message"]


# --------------------------------------------------------------------------- #
# _check_disk_space                                                            #
# --------------------------------------------------------------------------- #


class TestCheckDiskSpace:

    def test_sufficient_space_returns_true(self, proc_with_mocked_init, tmp_path):
        processor = proc_with_mocked_init

        file_path = tmp_path / "input.wav"
        file_path.write_bytes(b"x" * 1024)

        mock_usage = MagicMock()
        mock_usage.free = 1024 * 1024 * 1024

        with patch('shutil.disk_usage', return_value=mock_usage):
            result = processor._check_disk_space(str(file_path), str(tmp_path))

        assert result is True

    def test_insufficient_space_returns_false(self, proc_with_mocked_init, tmp_path):
        processor = proc_with_mocked_init

        file_size = 1024 * 1024 * 500
        file_path = tmp_path / "big.wav"
        file_path.write_bytes(b"x" * min(file_size, 64))

        with patch('os.path.getsize', return_value=file_size):
            mock_usage = MagicMock()
            mock_usage.free = 1024 * 1024 * 100

            with patch('shutil.disk_usage', return_value=mock_usage):
                result = processor._check_disk_space(str(file_path), str(tmp_path))

        assert result is False
