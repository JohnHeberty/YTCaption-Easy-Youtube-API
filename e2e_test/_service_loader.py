"""Service module loader with isolation.

Each test file calls ``load_app(service_dir_name)`` inside its fixture
to get a fresh ``app`` module, regardless of which service was imported
before.  This solves the ``sys.modules['app']`` collision when multiple
services are tested in the same pytest session.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

_E2E_ROOT = Path(__file__).resolve().parent
_SERVICES_ROOT = _E2E_ROOT.parent / "services"


def load_app(service_dir_name: str):
    """Return ``(app, verify_api_key)`` for *service_dir_name*.

    ``service_dir_name`` is the directory under ``services/``, e.g.
    ``"se10-clothes-segmentation"``.
    """
    service_path = str(_SERVICES_ROOT / service_dir_name)

    # 1. Evict every ``app`` / ``app.*`` module so we get a clean import
    to_remove = [k for k in sys.modules if k == "app" or k.startswith("app.")]
    for k in to_remove:
        del sys.modules[k]

    # 1b. Also evict any prometheus_client metrics already registered
    #     (they live in a global registry and re-importing counters crashes)
    try:
        from prometheus_client import REGISTRY as _reg
        collectors = list(_reg._names_to_collectors.values())
        for c in collectors:
            try:
                _reg.unregister(c)
            except KeyError:
                pass
    except Exception:
        pass

    # 2. Put the correct service at the front of sys.path
    if service_path in sys.path:
        sys.path.remove(service_path)
    sys.path.insert(0, service_path)

    # 3. Patch ResilientRedisStore._test_connection so module-level
    #    get_job_store() calls don't try to connect to real Redis
    with patch("common.redis_utils.resilient_store.ResilientRedisStore._test_connection"):
        mod = importlib.import_module("app.main")

    return mod.app, mod.verify_api_key
