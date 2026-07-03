"""BiRefNet-portrait detector — SOTA person segmentation with ONNX Runtime.

BiRefNet-portrait provides:
- SOTA person segmentation (DIS benchmark leader)
- Binary person mask output (alpha matte)
- MIT license
- ONNX exportable, runs on CPU without GPU
- ~200MB model, ~5-10s on CPU for 1024x1024 input

This module wraps onnxruntime inference for BiRefNet-portrait-ONNX
and outputs supervision.Detections for compatibility with SE10 pipeline.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import supervision as sv
from PIL import Image

from common.log_utils import get_logger

logger = get_logger(__name__)

# BiRefNet-portrait ONNX model config
BIREFNET_INPUT_SIZE = (1024, 1024)


class BiRefNetDetector:
    """BiRefNet-portrait person detector with mask output."""

    def __init__(self, model_path: str = "birefnet-portrait.onnx") -> None:
        self._model_path = model_path
        self._session: Any = None
        self._input_name: str | None = None

    def load(self) -> None:
        """Load BiRefNet-portrait ONNX model."""
        t0 = time.time()
        import onnxruntime as ort

        model_path = Path(self._model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"BiRefNet ONNX model not found: {model_path}. "
                "Download from https://huggingface.co/onnx-community/BiRefNet-portrait-ONNX"
            )

        # Prefer CUDA, fallback to CPU
        available = ort.get_available_providers()
        if "CUDAExecutionProvider" in available:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            logger.info("BiRefNet using CUDA provider")
        else:
            providers = ["CPUExecutionProvider"]
            logger.info("BiRefNet using CPU provider")

        self._session = ort.InferenceSession(
            str(model_path), providers=providers
        )
        self._input_name = self._session.get_inputs()[0].name

        logger.info(
            "BiRefNet-portrait loaded | path=%s providers=%s time=%.1fs",
            self._model_path, self._session.get_providers(), time.time() - t0,
        )

    def _preprocess(self, image_bgr: np.ndarray) -> np.ndarray:
        """Preprocess image for BiRefNet inference.

        - Resize to 1024x1024
        - Normalize to [0, 1]
        - Transpose to CHW
        - Add batch dimension
        """
        h_orig, w_orig = image_bgr.shape[:2]

        # Resize to 1024x1024
        resized = cv2.resize(
            image_bgr, BIREFNET_INPUT_SIZE, interpolation=cv2.INTER_LANCZOS4
        )

        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Normalize to [0, 1] and convert to float32
        normalized = rgb.astype(np.float32) / 255.0

        # Transpose to CHW: (H, W, C) -> (C, H, W)
        chw = normalized.transpose(2, 0, 1)

        # Add batch dimension: (1, C, H, W)
        batch = chw[np.newaxis, ...]

        return batch

    def _postprocess(
        self, output: np.ndarray, h_orig: int, w_orig: int, threshold: float = 0.5
    ) -> np.ndarray:
        """Postprocess BiRefNet output to binary mask.

        Args:
            output: Raw ONNX output (1, 1, H, W) or (1, H, W)
            h_orig: Original image height
            w_orig: Original image width
            threshold: Threshold for binary mask

        Returns:
            Binary mask of shape (h_orig, w_orig) as bool
        """
        # Remove batch dimension and channel dimension
        alpha = output.squeeze()
        if alpha.ndim == 3:
            alpha = alpha[0]

        # Sigmoid (BiRefNet outputs logits, not probabilities)
        alpha = 1.0 / (1.0 + np.exp(-alpha.astype(np.float32)))

        # Resize to original dimensions
        alpha_resized = cv2.resize(
            alpha, (w_orig, h_orig), interpolation=cv2.INTER_LINEAR
        )

        # Threshold to binary mask
        binary = (alpha_resized > threshold).astype(bool)

        return binary

    def predict(
        self,
        image_bgr: np.ndarray,
        threshold: float = 0.5,
    ) -> sv.Detections:
        """Run BiRefNet-portrait inference and return supervision.Detections.

        Args:
            image_bgr: OpenCV BGR image (H, W, 3).
            threshold: Threshold for binary mask (0.0-1.0).

        Returns:
            sv.Detections with xyxy, confidence, class_id, and mask.
        """
        if self._session is None:
            raise RuntimeError("BiRefNet model not loaded. Call load() first.")

        t0 = time.time()
        h_orig, w_orig = image_bgr.shape[:2]

        # Preprocess
        input_data = self._preprocess(image_bgr)

        # Run inference
        raw_output = self._session.run(None, {self._input_name: input_data})[0]

        # Postprocess to binary mask
        binary_mask = self._postprocess(raw_output, h_orig, w_orig, threshold)

        # Compute confidence as mean alpha value in masked region
        alpha_raw = 1.0 / (1.0 + np.exp(-raw_output.squeeze().astype(np.float32)))
        alpha_resized = cv2.resize(alpha_raw, (w_orig, h_orig), interpolation=cv2.INTER_LINEAR)
        confidence = float(np.mean(alpha_resized[binary_mask])) if binary_mask.any() else 0.0

        # Find bounding box from mask
        if binary_mask.any():
            ys, xs = np.where(binary_mask)
            bbox = np.array([[xs.min(), ys.min(), xs.max(), ys.max()]])
        else:
            bbox = np.empty((0, 4))

        processing_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            "BiRefNet-portrait prediction | confidence=%.3f time=%.1fms",
            confidence, processing_ms,
        )

        return sv.Detections(
            xyxy=bbox,
            confidence=np.array([confidence]) if confidence > 0 else np.array([]),
            class_id=np.array([0], dtype=int) if confidence > 0 else np.array([], dtype=int),
            mask=np.array([binary_mask]) if binary_mask.any() else None,
        )
