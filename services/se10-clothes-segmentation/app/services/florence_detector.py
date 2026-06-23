"""FlorenceDetector — Microsoft Florence-2 alternative detector for clothing segmentation.

Uses Florence-2 encoder-decoder model for better clothing detection accuracy.
Interface matches GroundingDinODetector for easy swapping.
"""
from __future__ import annotations

import io
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import supervision as sv
import torch
from PIL import Image

from common.log_utils import get_logger

logger = get_logger(__name__)


class FlorenceDetector:
    """Florence-2 detector with same interface as GroundingDinODetector.

    Uses HuggingFace transformers to load Florence-2 model for
    open-vocabulary object detection.
    """

    def __init__(self, device: str = "cpu", model_name: str = "microsoft/Florence-2-base") -> None:
        self._device = device
        self._model_name = model_name
        self._model = None
        self._processor = None
        self._load_model()

    def _load_model(self) -> None:
        """Load Florence-2 model from HuggingFace."""
        t0 = time.time()
        try:
            from transformers import AutoModelForCausalLM, AutoProcessor

            logger.info("Loading Florence-2 model: %s", self._model_name)
            self._model = AutoModelForCausalLM.from_pretrained(
                self._model_name,
                trust_remote_code=True,
                torch_dtype=torch.float32,
            )
            self._processor = AutoProcessor.from_pretrained(
                self._model_name,
                trust_remote_code=True,
            )
            logger.info("Florence-2 loaded in %.1fs", time.time() - t0)
        except Exception as e:
            logger.error("Failed to load Florence-2: %s", e)
            raise

    def predict_with_classes(
        self,
        image: np.ndarray,
        classes: list[str],
        box_threshold: float = 0.25,
        text_threshold: float = 0.25,
    ) -> sv.Detections:
        """Run Florence-2 detection on image.

        Args:
            image: BGR image as numpy array (H, W, 3)
            classes: List of class names to detect
            box_threshold: Minimum confidence for bounding boxes
            text_threshold: Not used by Florence-2 (kept for interface compatibility)

        Returns:
            supervision.Detections with xyxy, confidence, class_id
        """
        t0 = time.time()

        # Convert BGR to RGB PIL Image
        img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img_rgb)

        # Format prompt for Florence-2 object detection
        # Florence-2 uses "Object detection: <classes>" format
        classes_text = ", ".join(classes)
        prompt = f"Object detection: {classes_text}"

        # Run inference
        inputs = self._processor(text=prompt, images=pil_image, return_tensors="pt")

        with torch.no_grad():
            generated_ids = self._model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=1024,
                num_beams=3,
            )

        # Decode output
        generated_text = self._processor.batch_decode(
            generated_ids, skip_special_tokens=False
        )[0]

        # Parse Florence-2 output format
        # Florence-2 outputs structured text with bounding boxes and labels
        detections = self._parse_florence_output(
            generated_text, image.shape, classes, box_threshold
        )

        elapsed = time.time() - t0
        logger.info(
            "Florence-2 detection: %d objects in %.1fs",
            len(detections), elapsed,
        )

        return detections

    def _parse_florence_output(
        self,
        text: str,
        image_shape: tuple,
        classes: list[str],
        threshold: float,
    ) -> sv.Detections:
        """Parse Florence-2 text output into supervision Detections.

        Florence-2 output format:
        `<loc_0><loc_0><loc_0><loc_0> label1 <loc_1><loc_1><loc_1><loc_1> label2 ...`

        Coordinates are normalized (0-1000) and need to be converted to pixel values.
        """
        import re

        h, w = image_shape[:2]
        boxes = []
        confidences = []
        class_ids = []

        # Find all bounding box + label patterns
        # Pattern: <loc_XXX><loc_XXX><loc_XXX><loc_XXX> label
        pattern = r'<loc_(\d+)><loc_(\d+)><loc_(\d+)><loc_(\d+)>\s*([^<]+)'
        matches = re.findall(pattern, text)

        for match in matches:
            y1_norm, x1_norm, y2_norm, x2_norm, label = match

            # Convert normalized coordinates (0-1000) to pixels
            y1 = float(y1_norm) / 1000.0 * h
            x1 = float(x1_norm) / 1000.0 * w
            y2 = float(y2_norm) / 1000.0 * h
            x2 = float(x2_norm) / 1000.0 * w

            # Ensure coordinates are valid
            if x1 >= x2 or y1 >= y2:
                continue

            # Match label to classes
            label_lower = label.strip().lower()
            matched_class_id = -1
            for i, cls in enumerate(classes):
                if cls.lower() in label_lower or label_lower in cls.lower():
                    matched_class_id = i
                    break

            if matched_class_id >= 0:
                boxes.append([x1, y1, x2, y2])
                confidences.append(0.8)  # Florence-2 doesn't output confidence, use default
                class_ids.append(matched_class_id)

        if not boxes:
            return sv.Detections(
                xyxy=np.empty((0, 4), dtype=np.float32),
                confidence=np.array([], dtype=np.float32),
                class_id=np.array([], dtype=int),
            )

        return sv.Detections(
            xyxy=np.array(boxes, dtype=np.float32),
            confidence=np.array(confidences, dtype=np.float32),
            class_id=np.array(class_ids, dtype=int),
        )
