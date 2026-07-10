"""Test fixtures for SE7 Audio Generation."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Set required env vars before any module imports trigger settings loading
os.environ.setdefault("APP_NAME", "Audio Generation Service")
os.environ.setdefault("REDIS_URL", "redis://192.168.1.110:6379/7")

# Ensure the service module is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _set_api_key():
    """Set API_KEY env var so tests can authenticate."""
    os.environ["API_KEY"] = "se7-test-key-2026"
    yield
    os.environ.pop("API_KEY", None)
