"""Unit tests for ClothesSegSettings."""
import pytest

from app.core.config import ClothesSegSettings, get_settings


@pytest.mark.unit
class TestClothesSegSettings:
    def test_default_values(self):
        s = ClothesSegSettings(
            APP_NAME="test",
            REDIS_URL="redis://localhost:6379/10",
        )
        assert s.port == 8010
        assert s.box_threshold == 0.10
        assert s.text_threshold == 0.10
        assert s.worker_threads == 2

    def test_device_auto_or_cpu(self):
        s = ClothesSegSettings(
            APP_NAME="test",
            REDIS_URL="redis://localhost:6379/10",
        )
        assert s.device in ("auto", "cpu")

    def test_singleton_get_settings(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_getitem(self):
        s = ClothesSegSettings(
            APP_NAME="test",
            REDIS_URL="redis://localhost:6379/10",
        )
        assert s["port"] == 8010
        assert s["nonexistent"] is None
