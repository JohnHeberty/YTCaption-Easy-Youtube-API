"""Shared test fixtures for SE9 tests."""
import os
import shutil
import tempfile

import httpx
import pytest

from app.core.config import settings


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "outputs"))


@pytest.fixture(scope="session")
def csv_data_dir():
    """Path to CSV fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def output_dir():
    """Persistent output directory for E2E test artifacts."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    yield OUTPUT_DIR
    # Don't cleanup — user may want to inspect videos


@pytest.fixture
def temp_dir():
    """Temporary directory cleaned up after test."""
    d = tempfile.mkdtemp(prefix="se9_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _check_service_sync(url: str, timeout: float = 3.0) -> bool:
    """Check if a service is reachable via /ping or /health (sync)."""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{url}/ping")
            if r.status_code == 200:
                return True
            r = client.get(f"{url}/health")
            return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def services_online():
    """Auto-detect if SE7 and SE8 are available.

    Returns dict with se7/se8 booleans.
    """
    return {
        "se7": _check_service_sync(settings.se7_url),
        "se8": _check_service_sync(settings.se8_url),
    }


@pytest.fixture(scope="session")
def all_services_online(services_online):
    """True only if BOTH SE7 and SE8 are reachable."""
    return services_online["se7"] and services_online["se8"]
