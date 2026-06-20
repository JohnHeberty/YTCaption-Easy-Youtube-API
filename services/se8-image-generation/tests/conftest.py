import os
import sys

os.environ["SE8_API_KEY"] = "se8-test-key-2026"
os.environ["REDIS_URL"] = "redis://localhost:6379/9"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/9"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/9"
os.environ["APP_NAME"] = "SE8 Image Engine"
os.environ["ENVIRONMENT"] = "development"
os.environ["OUTPUT_DIR"] = "/tmp/se8-test-outputs"
os.environ["GPU_MODE"] = "lazy"
os.environ["MODEL_IDLE_TIMEOUT"] = "300"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.config import get_settings
get_settings.cache_clear()


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: Unit tests (no external deps)")
    config.addinivalue_line("markers", "integration: Integration tests (requires Docker)")
    config.addinivalue_line("markers", "gpu: Tests requiring GPU")
    config.addinivalue_line("markers", "slow: Slow tests")
