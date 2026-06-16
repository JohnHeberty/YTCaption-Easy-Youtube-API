import os
import sys

os.environ["FOOOCUS_API_URL"] = "http://mock-fooocus:8888"
os.environ["FOOOCUS_API_KEY"] = ""
os.environ["SE8_API_KEY"] = "se8-test-key-2026"
os.environ["REDIS_URL"] = "redis://localhost:6379/8"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/8"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/8"
os.environ["APP_NAME"] = "Image Generation Service"
os.environ["ENVIRONMENT"] = "development"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.config import get_settings
get_settings.cache_clear()


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (no external deps)")
    config.addinivalue_line("markers", "integration: Integration tests (requires Docker)")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "real: Tests requiring real services")
