"""Unit tests for AI image detector."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestAIImageDetector:
    """Tests for check_image_is_ai_generated."""

    @patch("app.services.ai_image_detector._model", None)
    @patch("app.services.ai_image_detector._transform", None)
    @patch("app.services.ai_image_detector._load_model")
    def test_unavailable_model_returns_true(self, mock_load):
        """When model fails to load, allow image by default."""
        from app.services.ai_image_detector import check_image_is_ai_generated

        # Model stays None after load
        def set_model_none():
            import app.services.ai_image_detector as mod
            mod._model = None
            mod._transform = None

        mock_load.side_effect = set_model_none

        is_ai, conf = check_image_is_ai_generated(b"\x89PNG\r\n\x1a\n")
        assert is_ai is True
        assert conf == 0.0

    @patch("app.services.ai_image_detector._model")
    @patch("app.services.ai_image_detector._transform")
    def test_ai_generated_image_returns_true(self, mock_transform, mock_model):
        """AI-generated image should return True."""
        import torch
        from app.services.ai_image_detector import check_image_is_ai_generated

        # Mock transform returns a tensor
        mock_transform.return_value = torch.zeros(3, 224, 224)

        # Mock model returns [ai_prob=0.95, real_prob=0.05]
        mock_output = torch.tensor([[0.95, 0.05]])
        mock_model.return_value = mock_output
        mock_model.eval.return_value = mock_model

        # Create minimal valid JPEG bytes
        from PIL import Image
        import io
        img = Image.new("RGB", (10, 10), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        with patch("torch.cuda.is_available", return_value=False):
            is_ai, conf = check_image_is_ai_generated(jpeg_bytes)

        assert is_ai is True
        assert conf > 0.5

    @patch("app.services.ai_image_detector._model")
    @patch("app.services.ai_image_detector._transform")
    def test_real_photo_returns_false(self, mock_transform, mock_model):
        """Real photo should return False."""
        import torch
        from app.services.ai_image_detector import check_image_is_ai_generated

        mock_transform.return_value = torch.zeros(3, 224, 224)

        # Mock model returns [ai_prob=0.05, real_prob=0.95]
        mock_output = torch.tensor([[0.05, 0.95]])
        mock_model.return_value = mock_output
        mock_model.eval.return_value = mock_model

        from PIL import Image
        import io
        img = Image.new("RGB", (10, 10), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        jpeg_bytes = buf.getvalue()

        with patch("torch.cuda.is_available", return_value=False):
            is_ai, conf = check_image_is_ai_generated(jpeg_bytes)

        assert is_ai is False
        assert conf < 0.5
