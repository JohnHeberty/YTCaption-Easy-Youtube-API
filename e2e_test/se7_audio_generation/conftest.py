"""Conftest for SE7 Audio Generation E2E tests.

Adds the SE7 service directory and shared/ to sys.path so that
``app.*`` and ``common.*`` modules are importable from the e2e_test root.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure service and shared directories are importable
_svc_root = str(Path(__file__).resolve().parent.parent.parent / "services" / "se7-audio-generation")
_shared_root = str(Path(__file__).resolve().parent.parent.parent / "shared")

if _svc_root not in sys.path:
    sys.path.insert(0, _svc_root)
if _shared_root not in sys.path:
    sys.path.insert(0, _shared_root)

# Minimal env so settings loading doesn't fail
os.environ.setdefault("API_KEY", "test-api-key-2026")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/7")
