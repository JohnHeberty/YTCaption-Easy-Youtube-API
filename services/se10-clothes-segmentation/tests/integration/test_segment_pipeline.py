"""Integration test for the full segment pipeline (requires models)."""
import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image


def _make_test_image() -> bytes:
    """Create a simple test image."""
    img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.integration
class TestSegmentPipeline:
    """Integration tests that exercise the actual segmentor (skipped if models not available)."""

    @pytest.fixture(autouse=True)
    def _skip_without_models(self):
        """Skip if checkpoints are not present."""
        checkpoints_dir = Path(os.environ.get("CHECKPOINT_DIR", "./checkpoints")).resolve()
        gd_ckpt = checkpoints_dir / "groundingdino_swint_ogc.pth"
        sam2_ckpt = checkpoints_dir / "sam2_hiera_tiny.pt"
        if not gd_ckpt.exists() or not sam2_ckpt.exists():
            pytest.skip("ML checkpoints not found — skipping integration tests")

    def test_segment_returns_result(self):
        from app.core.config import ClothesSegSettings
        from app.services.segmentor import ClothesSegmentor

        settings = ClothesSegSettings(
            APP_NAME="test",
            REDIS_URL="redis://localhost:6379/10",
            DEVICE="cpu",
        )
        seg = ClothesSegmentor(settings=settings)
        result = seg.segment(image_bytes=_make_test_image())

        assert "detected" in result
        assert "objects" in result
        assert "processing_time_ms" in result
        assert isinstance(result["objects"], list)
