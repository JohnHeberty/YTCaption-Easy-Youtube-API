"""Shared test fixtures for SE9 tests."""
import asyncio
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


async def _check_service(url: str, timeout: float = 3.0) -> bool:
    """Check if a service is reachable via /ping or /health."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{url}/ping")
            if r.status_code == 200:
                return True
            r = await client.get(f"{url}/health")
            return r.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session")
def services_online():
    """Auto-detect if SE7 and SE8 are available.

    Returns dict with se7/se8 booleans.
    """
    async def _check():
        se7 = await _check_service(settings.se7_url)
        se8 = await _check_service(settings.se8_url)
        return {"se7": se7, "se8": se8}

    return asyncio.get_event_loop().run_until_complete(_check())


@pytest.fixture(scope="session")
def all_services_online(services_online):
    """True only if BOTH SE7 and SE8 are reachable."""
    return services_online["se7"] and services_online["se8"]
