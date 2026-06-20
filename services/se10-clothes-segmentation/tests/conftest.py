"""Root test configuration for SE10 Clothes Segmentation."""
import os
import sys

# Set env vars before any app imports
os.environ.setdefault("APP_NAME", "SE10 Clothes Segmentation Test")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("PORT", "8010")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/10")
os.environ.setdefault("SE10_API_KEY", "test-key-123")
os.environ.setdefault("LOG_LEVEL", "DEBUG")
os.environ.setdefault("CHECKPOINT_DIR", "./checkpoints")
os.environ.setdefault("EXTERNAL_DIR", "./external")
os.environ.setdefault("DEVICE", "cpu")

# Ensure app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
