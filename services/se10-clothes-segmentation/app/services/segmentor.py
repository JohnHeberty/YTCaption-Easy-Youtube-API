"""ClothesSegmentor — GroundingDINO + SAM2 clothing detection and segmentation.

Refactored from the original clothes-segmentation prototype.
- Removed sys.path hacks (uses editable installs instead)
- SAM2 image set once per request, all boxes predicted in batch
- Structured logging, GPU auto-detect, error handling
"""

import base64
import io
import time
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np
import supervision as sv
import torch
from PIL import Image

from common.log_utils import get_logger
from app.core.config import ClothesSegSettings
from app.core.constants import (
    CLOTHING_CLASSES,
    DEFAULT_BOX_THRESHOLD,
    DEFAULT_TEXT_THRESHOLD,
    DEFAULT_MAX_AREA_PCT,
    DEFAULT_MAX_OBJECTS,
    CHECKPOINT_GROUNDINGDINO,
    CHECKPOINT_SAM2_TINY,
    GD_CONFIG_SwinT,
    SAM2_CONFIG_TINY,
)

logger = get_logger(__name__)


class ClothesSegmentor:
    """GroundingDINO + SAM2 pipeline for clothing segmentation."""

    def __init__(self, settings: ClothesSegSettings):
        self.settings = settings
        self._device = self._resolve_device(settings.device)
        self._checkpoints_dir = Path(settings.checkpoint_dir).resolve()
        self._external_dir = Path(settings.external_dir).resolve()

        logger.info(
            "Initializing segmentor | device=%s checkpoints=%s",
            self._device, self._checkpoints_dir,
        )

        self._gd_model = None
        self._sam2_predictor = None
        self._load_models()

    @property
    def device(self) -> str:
        """Return the device name as a string (public API)."""
        return str(self._device)

    # ------------------------------------------------------------------ #
    #  Device resolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_device(device_str: str) -> torch.device:
        if device_str == "auto":
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return torch.device(device_str)

    # ------------------------------------------------------------------ #
    #  Model loading
    # ------------------------------------------------------------------ #

    def _load_models(self):
        t0 = time.time()

        # GroundingDINO
        gd_repo = self._external_dir / "GroundingDINO"
        gd_config = gd_repo / GD_CONFIG_SwinT
        gd_checkpoint = self._checkpoints_dir / CHECKPOINT_GROUNDINGDINO

        if not gd_checkpoint.exists():
            raise FileNotFoundError(
                f"GroundingDINO checkpoint not found: {gd_checkpoint}"
            )

        from groundingdino.util.inference import Model as GDModel

        self._gd_model = GDModel(
            model_config_path=str(gd_config),
            model_checkpoint_path=str(gd_checkpoint),
            device=str(self._device),
        )
        logger.info("GroundingDINO loaded")

        # SAM2 — config name must be relative to the sam2 package for Hydra
        sam2_checkpoint = self._checkpoints_dir / CHECKPOINT_SAM2_TINY

        if not sam2_checkpoint.exists():
            raise FileNotFoundError(f"SAM2 checkpoint not found: {sam2_checkpoint}")

        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor

        sam2_model = build_sam2(
            SAM2_CONFIG_TINY,
            str(sam2_checkpoint),
            device=self._device,
            apply_postprocessing=False,
        )
        self._sam2_predictor = SAM2ImagePredictor(sam2_model)
        logger.info("SAM2 loaded")

        logger.info("All models loaded in %.1fs", time.time() - t0)

    # ------------------------------------------------------------------ #
    #  Geometry helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_inside(box1, box2) -> bool:
        x1, y1, x2, y2 = box1
        x1i, y1i, x2i, y2i = box2
        return x1 >= x1i and y1 >= y1i and x2 <= x2i and y2 <= y2i

    # ------------------------------------------------------------------ #
    #  Core segmentation
    # ------------------------------------------------------------------ #

    def segment(
        self,
        image_bytes: bytes,
        classes: Optional[List[str]] = None,
        box_threshold: Optional[float] = None,
        text_threshold: Optional[float] = None,
        max_area_pct: Optional[float] = None,
        max_objects: Optional[int] = None,
    ) -> dict:
        """Run full segmentation pipeline on image bytes.

        Returns:
            dict with keys: detected, objects, mask_image, processing_time_ms
        """
        t0 = time.time()
        classes = classes or CLOTHING_CLASSES
        box_threshold = box_threshold or self.settings.box_threshold
        text_threshold = text_threshold or self.settings.text_threshold
        max_area_pct = max_area_pct or self.settings.max_area_pct
        max_objects = max_objects or self.settings.max_objects

        # Decode image
        img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        original_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        height, width, _ = original_image.shape
        image_area = height * width

        # 1. GroundingDINO detection
        detections = self._gd_model.predict_with_classes(
            image=original_image,
            classes=classes,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
        )

        # 2. Area filtering
        area_filtered = detections[(detections.area / image_area) < max_area_pct]

        # 3. Nesting filtering (remove boxes inside other boxes)
        filtered_boxes, filtered_confidences, filtered_class_ids = [], [], []
        for i, box1 in enumerate(area_filtered.xyxy):
            is_inside = False
            for j, box2 in enumerate(area_filtered.xyxy):
                if i != j and self._is_inside(box1, box2):
                    is_inside = True
                    break
            if not is_inside:
                filtered_boxes.append(box1)
                filtered_confidences.append(area_filtered.confidence[i])
                filtered_class_ids.append(area_filtered.class_id[i])

        final_detections = sv.Detections(
            xyxy=np.array(filtered_boxes) if filtered_boxes else np.empty((0, 4)),
            confidence=np.array(filtered_confidences),
            class_id=np.array(filtered_class_ids),
        )

        # Cap to max_objects (by confidence)
        if len(final_detections) > max_objects:
            top_idx = np.argsort(-final_detections.confidence)[:max_objects]
            final_detections = final_detections[top_idx]

        if len(final_detections) == 0:
            return {
                "detected": False,
                "objects": [],
                "mask_image": None,
                "processing_time_ms": round((time.time() - t0) * 1000, 1),
            }

        # 4. SAM2 segmentation — set image ONCE, predict all boxes
        rgb_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
        self._sam2_predictor.set_image(rgb_image)

        result_masks = []
        for box in final_detections.xyxy:
            masks, scores, _ = self._sam2_predictor.predict(
                point_coords=None,
                point_labels=None,
                box=box[None, :],
                multimask_output=True,
            )
            result_masks.append(masks[np.argmax(scores)])

        final_detections.mask = np.array(result_masks)

        # 5. Annotate
        mask_annotator = sv.MaskAnnotator()
        box_annotator = sv.BoxAnnotator()
        labels = [
            f"{classes[c]} {conf:.2f}"
            for c, conf in zip(final_detections.class_id, final_detections.confidence)
        ]
        annotated = mask_annotator.annotate(
            scene=original_image.copy(), detections=final_detections
        )
        annotated = box_annotator.annotate(
            scene=annotated, detections=final_detections
        )
        for xyxy, label in zip(final_detections.xyxy, labels):
            x, y = int(xyxy[0]), int(xyxy[1])
            cv2.putText(
                annotated, label, (x, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2,
            )

        # 6. Build binary masks (one per object, for inpainting)
        binary_masks = []
        for mask_arr in final_detections.mask:
            mask_uint8 = (mask_arr.astype(np.uint8)) * 255
            _, mask_buffer = cv2.imencode(".png", mask_uint8)
            mask_b64_str = f"data:image/png;base64,{base64.b64encode(mask_buffer).decode('utf-8')}"
            binary_masks.append(mask_b64_str)

        # 7. Build response
        areas = final_detections.area if len(final_detections) > 0 else np.array([])
        detected_objects = [
            {
                "class_name": classes[cls_id],
                "confidence": round(float(conf), 4),
                "bbox": [int(b) for b in xyxy],
                "area_pct": round(float(areas[i] / image_area) * 100, 2),
            }
            for i, (cls_id, conf, xyxy) in enumerate(zip(
                final_detections.class_id,
                final_detections.confidence,
                final_detections.xyxy,
            ))
        ]

        _, buffer = cv2.imencode(".jpg", annotated)
        mask_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

        processing_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            "Segmentation complete | objects=%d time=%.1fms",
            len(detected_objects), processing_ms,
        )

        return {
            "detected": True,
            "objects": detected_objects,
            "mask_image": mask_b64,
            "masks": binary_masks,
            "processing_time_ms": processing_ms,
        }
