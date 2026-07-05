"""SegFormerDetector — SegFormer B2 for clothing/human semantic segmentation.

Uses mattmdjaga/segformer_b2_clothes fine-tuned on ATR dataset.
18 classes: Background, Hat, Hair, Sunglasses, Upper-clothes, Skirt, Pants, Dress,
            Belt, Left-shoe, Right-shoe, Face, Left-leg, Right-leg, Left-arm,
            Right-arm, Bag, Scarf.
"""
from __future__ import annotations

import time
from typing import Any

import cv2
import numpy as np
import supervision as sv
import torch
from PIL import Image

from common.log_utils import get_logger

logger = get_logger(__name__)

# SegFormer B2 clothes segmentation labels (ATR dataset)
LABELS = [
    "Background", "Hat", "Hair", "Sunglasses", "Upper-clothes", "Skirt",
    "Pants", "Dress", "Belt", "Left-shoe", "Right-shoe", "Face",
    "Left-leg", "Right-leg", "Left-arm", "Right-arm", "Bag", "Scarf",
]

# Clothing class IDs (what we want to segment as "clothes")
CLOTHING_IDS = {4, 5, 6, 7}  # Upper-clothes, Skirt, Pants, Dress

# Body parts we want to EXCLUDE from clothes mask
BODY_IDS = {1, 2, 3, 11, 12, 13, 14, 15, 16, 17, 18, 19}  # Hat, Hair, Sunglasses, Face, legs, arms, shoes


class SegFormerDetector:
    """SegFormer B2 clothes segmentation detector.

    Produces pixel-level semantic segmentation masks for 18 classes
    including specific clothing items (upper-clothes, skirt, pants, dress).
    """

    def __init__(self, device: str = "cpu", model_name: str | None = None) -> None:
        self._device = device
        self._model_name = model_name or "mattmdjaga/segformer_b2_clothes"
        self._model = None
        self._processor = None
        self._load_model()

    def _load_model(self) -> None:
        t0 = time.time()
        try:
            from transformers import (
                AutoImageProcessor,
                AutoModelForSemanticSegmentation,
            )

            logger.info("Loading SegFormer B2: %s", self._model_name)

            self._processor = AutoImageProcessor.from_pretrained(self._model_name)
            self._model = AutoModelForSemanticSegmentation.from_pretrained(self._model_name)

            if self._device == "cuda" and torch.cuda.is_available():
                self._model = self._model.cuda()
                logger.info("SegFormer B2 loaded on GPU")
            else:
                self._model = self._model.cpu()
                logger.info("SegFormer B2 loaded on CPU")

            self._model.eval()
            logger.info("SegFormer B2 loaded in %.1fs", time.time() - t0)
        except Exception as e:
            logger.error("Failed to load SegFormer B2: %s", e)
            raise

    def segment_clothes(
        self,
        image_bgr: np.ndarray,
        clothing_ids: set[int] | None = None,
    ) -> dict[str, Any]:
        """Run SegFormer segmentation and extract clothing masks.

        Args:
            image_bgr: BGR image as numpy array (H, W, 3)
            clothing_ids: Set of class IDs to treat as clothing.
                         Default: {4, 5, 6, 7} (Upper-clothes, Skirt, Pants, Dress)

        Returns:
            dict with keys:
            - clothing_mask: binary np.ndarray (H, W) — union of all clothing classes
            - per_class: dict[class_id → np.ndarray(H, W)] — individual class masks
            - detected_classes: list of (class_id, class_name, area_pct)
            - processing_time_ms: float
        """
        t0 = time.time()
        if clothing_ids is None:
            clothing_ids = CLOTHING_IDS

        h, w = image_bgr.shape[:2]
        image_area = h * w

        # Convert BGR to RGB PIL
        img_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(img_rgb)

        # Run inference
        inputs = self._processor(images=pil_image, return_tensors="pt")
        device = next(self._model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)

        # Get segmentation map (argmax over 18 classes)
        logits = outputs.logits.cpu()
        upsampled = torch.nn.functional.interpolate(
            logits,
            size=(h, w),
            mode="bilinear",
            align_corners=False,
        )
        seg_map = upsampled.argmax(dim=1)[0].numpy()  # (H, W), values 0-17

        # Build clothing mask (union of clothing class IDs)
        clothing_mask = np.zeros((h, w), dtype=bool)
        per_class: dict[int, np.ndarray] = {}
        detected_classes: list[tuple[int, str, float]] = []

        for cls_id in clothing_ids:
            cls_mask = seg_map == cls_id
            if cls_mask.any():
                area_pct = float(cls_mask.sum() / image_area * 100)
                per_class[cls_id] = cls_mask
                clothing_mask |= cls_mask
                detected_classes.append((cls_id, LABELS[cls_id], area_pct))

        # Close gaps between clothing items (e.g. hoodie→pants gap on exposed belly)
        # Large kernel bridges the gap between separate clothing detections
        close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (120, 120))
        clothing_mask_closed = cv2.morphologyEx(
            clothing_mask.astype(np.uint8) * 255, cv2.MORPH_CLOSE, close_kernel
        )

        # Per-class: close internal holes then keep only largest component
        for cls_id in list(per_class.keys()):
            mask_uint8 = per_class[cls_id].astype(np.uint8) * 255
            cls_closed = cv2.morphologyEx(mask_uint8, cv2.MORPH_CLOSE, close_kernel)

            # Flood-fill internal holes
            h_f, w_f = cls_closed.shape
            flood = cls_closed.copy()
            flood_mask = np.zeros((h_f + 2, w_f + 2), np.uint8)
            cv2.floodFill(flood, flood_mask, (0, 0), 128)
            internal_holes = (cls_closed == 255) & (~((flood == 128)))
            filled = cls_closed.copy()
            filled[internal_holes] = 255

            # Keep only largest connected component
            num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(filled, connectivity=8)
            if num_labels > 1:
                largest_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
                filled = (labels == largest_label).astype(np.uint8) * 255

            per_class[cls_id] = filled > 0

        # Rebuild union mask from cleaned per-class masks
        clothing_mask = np.zeros((h, w), dtype=bool)
        for cls_mask in per_class.values():
            clothing_mask |= cls_mask

        total_clothing_pct = float(clothing_mask.sum() / image_area * 100)

        elapsed_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            "SegFormer B2: clothing=%.1f%% classes=%d time=%.1fms",
            total_clothing_pct, len(detected_classes), elapsed_ms,
        )

        return {
            "clothing_mask": clothing_mask,
            "per_class": per_class,
            "detected_classes": detected_classes,
            "total_clothing_pct": total_clothing_pct,
            "processing_time_ms": elapsed_ms,
            "seg_map": seg_map,
        }

    def segment_to_sv_detections(
        self,
        image_bgr: np.ndarray,
        clothing_ids: set[int] | None = None,
    ) -> sv.Detections:
        """Run SegFormer and return SEPARATE supervision Detections per clothing class.

        Each clothing class (Upper-clothes, Skirt, Pants, Dress) becomes its own
        detection with its own bounding box and mask. This prevents area filtering
        from rejecting the entire detection when multiple classes are present.
        """
        h, w = image_bgr.shape[:2]
        result = self.segment_clothes(image_bgr, clothing_ids)
        per_class = result["per_class"]

        if not per_class:
            return sv.Detections(
                xyxy=np.empty((0, 4), dtype=np.float32),
                confidence=np.array([], dtype=np.float32),
                class_id=np.array([], dtype=int),
                mask=np.empty((0, h, w), dtype=bool),
            )

        xyxy_list = []
        mask_list = []
        class_id_list = []
        confidence_list = []

        for cls_id, cls_mask in per_class.items():
            # Bounding box from this class mask
            ys, xs = np.where(cls_mask)
            x1, y1, x2, y2 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

            # Pad bbox by 5% for better mask coverage
            pad_x = int((x2 - x1) * 0.05)
            pad_y = int((y2 - y1) * 0.05)
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w - 1, x2 + pad_x)
            y2 = min(h - 1, y2 + pad_y)

            xyxy_list.append([x1, y1, x2, y2])
            mask_list.append(cls_mask)
            class_id_list.append(cls_id)
            confidence_list.append(1.0)

        return sv.Detections(
            xyxy=np.array(xyxy_list, dtype=np.float32),
            confidence=np.array(confidence_list, dtype=np.float32),
            class_id=np.array(class_id_list, dtype=int),
            mask=np.array(mask_list),
        )

    def unload(self) -> None:
        """Unload model to free memory."""
        self._model = None
        self._processor = None
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("SegFormer B2 unloaded")
