"""Shared E2E test fixtures for all services."""
from __future__ import annotations

import importlib
import io
import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


API_KEY = os.getenv("API_KEY", "test-api-key-2026")


def load_service_app(service_dir_name: str):
    """Load a service's FastAPI app with full module isolation.

    Removes all ``app`` and ``app.*`` entries from ``sys.modules``,
    sets ``sys.path`` to the correct service directory, and returns
    a fresh ``(app, verify_api_key)`` tuple.

    Call this inside every fixture/client helper that needs the service app.
    """
    service_path = str(
        Path(__file__).resolve().parent.parent / "services" / service_dir_name
    )

    # 1. Remove all cached 'app' modules so we get a clean import
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]

    # 2. Ensure the correct service dir is first in sys.path
    if service_path in sys.path:
        sys.path.remove(service_path)
    sys.path.insert(0, service_path)

    # 3. Import fresh
    mod = importlib.import_module("app.main")
    return mod.app, mod.verify_api_key


@pytest.fixture(scope="session")
def api_headers() -> dict[str, str]:
    """Standard API key header for authenticated requests."""
    return {"X-API-Key": API_KEY}


@pytest.fixture(scope="session")
def fake_redis():
    """Provide a fakeredis instance."""
    try:
        import fakeredis
        return fakeredis.FakeRedis(decode_responses=True)
    except ImportError:
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.ping.return_value = True
        mock.get.return_value = None
        mock.set.return_value = True
        mock.keys.return_value = []
        mock.flushdb.return_value = True
        return mock


@pytest.fixture
def sample_image_bytes() -> bytes:
    """Minimal valid PNG image (1x1 pixel, transparent)."""
    import struct
    import zlib

    def _create_png() -> bytes:
        signature = b"\x89PNG\r\n\x1a\n"

        def _chunk(chunk_type: bytes, data: bytes) -> bytes:
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            return struct.pack(">I", len(data)) + c + crc

        ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
        raw = b"\x00\x00\x00\x00\x00"
        idat_data = zlib.compress(raw)

        return (
            signature
            + _chunk(b"IHDR", ihdr_data)
            + _chunk(b"IDAT", idat_data)
            + _chunk(b"IEND", b"")
        )

    return _create_png()


@pytest.fixture
def sample_wav_bytes() -> bytes:
    """Minimal valid WAV file (1 sample, 8-bit mono)."""
    import struct
    sample_rate = 44100
    num_channels = 1
    bits_per_sample = 8
    data = b"\x80"
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        sample_rate * num_channels * bits_per_sample // 8,
        num_channels * bits_per_sample // 8,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + data


@pytest.fixture
def sample_audio_file(tmp_path, sample_wav_bytes):
    """Write sample WAV to temp file and return path."""
    p = tmp_path / "test_audio.wav"
    p.write_bytes(sample_wav_bytes)
    return str(p)


@pytest.fixture
def sample_image_file(tmp_path, sample_image_bytes):
    """Write sample PNG to temp file and return path."""
    p = tmp_path / "test_image.png"
    p.write_bytes(sample_image_bytes)
    return str(p)
