import pytest
import struct
import zlib
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import get_settings


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def api_key():
    return get_settings().se9_api_key


@pytest.fixture
def auth_header(api_key):
    return {"X-API-Key": api_key}


@pytest.fixture
def sample_png():
    width, height = 8, 8
    raw_data = b""
    for y in range(height):
        raw_data += b"\x00"
        for x in range(width):
            raw_data += bytes([x * 32, y * 32, 128])
    compressed = zlib.compress(raw_data)

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = zlib.crc32(c) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + c + struct.pack(">I", crc)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", compressed)
    png += chunk(b"IEND", b"")
    return png
