"""YOLO11-seg detector — fast person segmentation with masks.

YOLO11-seg provides:
- Pixel-level masks (not just bboxes)
- ~500ms inference on CPU, ~30ms on GPU
- Trained on COCO with 80 classes including "person" (class 0)

This module wraps ultralytics YOLO11-seg and outputs supervision.Detections
for compatibility with the existing SE10 pipeline.
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

# COCO class ID for "person"
PERSON_CLASS_ID = 0


class YOLODetector:
    """YOLO11-seg person detector with mask output."""

    def __init__(self, model_path: str = "yolo11m-seg.pt", device: str = "cpu") -> None:
        self._model_path = model_path
        self._device = device
        self._model: Any = None

    def load(self) -> None:
        """Load YOLO11-seg model."""
        t0 = time.time()
        from ultralytics import YOLO
        self._model = YOLO(self._model_path)
        logger.info(
            "YOLO11-seg loaded | path=%s device=%s time=%.1fs",
            self._model_path, self._device, time.time() - t0,
        )

    def predict(
        self,
        image_bgr: np.ndarray,
        confidence: float = 0.25,
        classes: list[int] | None = None,
        imgsz: int = 1024,
    ) -> sv.Detections:
        """Run YOLO11-seg inference and return supervision.Detections.

        Args:
            image_bgr: OpenCV BGR image (H, W, 3).
            confidence: Minimum confidence threshold.
            classes: COCO class IDs to filter. Default [0] = person only.
            imgsz: Inference image size.

        Returns:
            sv.Detections with xyxy, confidence, class_id, and mask.
        """
        if self._model is None:
            raise RuntimeError("YOLO model not loaded. Call load() first.")

        if classes is None:
            classes = [PERSON_CLASS_ID]

        t0 = time.time()
        h, w = image_bgr.shape[:2]

        results = self._model.predict(
            image_bgr,
            conf=confidence,
            classes=classes,
            imgsz=imgsz,
            device=self._device,
            verbose=False,
        )

        all_boxes: list[np.ndarray] = []
        all_confidences: list[float] = []
        all_class_ids: list[int] = []
        all_masks: list[np.ndarray] = []

        for r in results:
            if r.boxes is None or len(r.boxes) == 0:
                continue

            for box, mask in zip(r.boxes, r.masks if r.masks is not None else [None] * len(r.boxes)):
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].cpu().numpy()

                all_boxes.append(xyxy)
                all_confidences.append(conf)
                all_class_ids.append(cls)

                if mask is not None:
                    # Resize mask to original image dimensions
                    mask_np = mask.data[0].cpu().numpy()
                    mask_resized = cv2.resize(
                        mask_np, (w, h), interpolation=cv2.INTER_LINEAR
                    )
                    mask_binary = (mask_resized > 0.5).astype(bool)
                    all_masks.append(mask_binary)
                else:
                    # No mask — create binary from bbox
                    mask_empty = np.zeros((h, w), dtype=bool)
                    x1, y1, x2, y2 = [int(v) for v in xyxy]
                    mask_empty[y1:y2, x1:x2] = True
                    all_masks.append(mask_empty)

        processing_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            "YOLO11-seg prediction | detections=%d time=%.1fms",
            len(all_boxes), processing_ms,
        )

        if not all_boxes:
            return sv.Detections(
                xyxy=np.empty((0, 4)),
                confidence=np.array([]),
                class_id=np.array([], dtype=int),
                mask=None,
            )

        return sv.Detections(
            xyxy=np.array(all_boxes),
            confidence=np.array(all_confidences),
            class_id=np.array(all_class_ids, dtype=int),
            mask=np.array(all_masks) if all_masks else None,
        )
