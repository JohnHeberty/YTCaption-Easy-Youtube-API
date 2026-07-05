"""ClothesSegmentor — SegFormer B2 pixel-level clothing detection.

Primary detector: SegFormer B2 (18 clothing classes, pixel-level masks)
Optional: YOLO11-seg (person detection), ensemble voting
"""
from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import supervision as sv
import torch
from PIL import Image

from common.log_utils import get_logger
from app.core.config import ClothesSegSettings
from app.services.pose_renderer import PoseRenderer
from app.core.constants import (
    CLOTHING_CLASSES,
    PERSON_CLASSES,
    DEFAULT_BOX_THRESHOLD,
    DEFAULT_TEXT_THRESHOLD,
    DEFAULT_MAX_AREA_PCT,
    DEFAULT_MAX_AREA_PCT_PERSON,
    DEFAULT_MAX_OBJECTS,
)

logger = get_logger(__name__)

# YOLO11-seg model path — download if not present
YOLO_MODEL_PATH = os.environ.get("YOLO_MODEL_PATH", "yolo11m-seg.pt")


class ClothesSegmentor:
    """SegFormer B2 pixel-level clothing segmentation."""

    def __init__(self, settings: ClothesSegSettings) -> None:
        self.settings = settings
        self._device = self._resolve_device(settings.device)
        self._checkpoints_dir = Path(settings.checkpoint_dir).resolve()
        self._last_used = time.time()
        self._idle_timeout = int(os.environ.get("SE10_IDLE_TIMEOUT", "120"))

        logger.info(
            "Initializing segmentor | device=%s checkpoints=%s",
            self._device, self._checkpoints_dir,
        )

        self._yolo_detector: Any = None
        self._segformer_detector: Any = None
        self._ensemble_detector: Any = None
        self._pose_renderer: PoseRenderer | None = None
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
            # Check CUDA_VISIBLE_DEVICES — if empty, force CPU
            cuda_visible = os.environ.get("CUDA_VISIBLE_DEVICES", "")
            if cuda_visible == "" or cuda_visible is None:
                return torch.device("cpu")
            return torch.device("cuda" if torch.cuda.is_available() else "cpu")
        # Map friendly names to torch device types
        device_map = {"gpu": "cuda", "cuda": "cuda", "cpu": "cpu"}
        resolved = device_map.get(device_str.lower(), device_str)
        return torch.device(resolved)

    # ------------------------------------------------------------------ #
    #  Model loading
    # ------------------------------------------------------------------ #

    def _load_models(self) -> None:
        t0 = time.time()
        self._load_gpu_models()

        # SegFormer B2 (pixel-level clothing segmentation)
        try:
            from app.services.segformer_detector import SegFormerDetector
            segformer_device = "cuda" if self._device.type == "cuda" else "cpu"
            self._segformer_detector = SegFormerDetector(device=segformer_device)
            logger.info("SegFormer B2 loaded | device=%s", segformer_device)
        except Exception as e:
            logger.warning("SegFormer B2 not available: %s", e)
            self._segformer_detector = None

        # Ensemble detector (SegFormer PRIMARY + YOLO11 secondary)
        if self._yolo_detector is not None or self._segformer_detector is not None:
            from app.services.ensemble_detector import EnsembleDetector
            self._ensemble_detector = EnsembleDetector()
            if self._yolo_detector is not None:
                self._ensemble_detector.set_yolo(self._yolo_detector)
            if self._segformer_detector is not None:
                self._ensemble_detector.set_segformer(self._segformer_detector)
            logger.info("Ensemble detector ready (SegFormer=%s, YOLO=%s)",
                        self._segformer_detector is not None,
                        self._yolo_detector is not None)

        # Pose renderer — lazy loaded (only when include_pose=True)
        self._pose_renderer: PoseRenderer | None = None

        logger.info("All models loaded in %.1fs", time.time() - t0)

    def _load_gpu_models(self) -> None:
        t0 = time.time()

        # GroundingDINO + SAM2 + BiRefNet: DISABLED — replaced by SegFormer B2.
        # These models either fail to load or are never used in the pipeline.
        # See LIÇÕES.md for details.

        # YOLO11-seg (optional — loaded if model file exists or downloadable)
        try:
            from app.services.yolo_detector import YOLODetector
            yolo_device = "cuda" if self._device.type == "cuda" else "cpu"
            yolo_path = os.environ.get("YOLO_MODEL_PATH", "/app/yolo11m-seg.pt")
            self._yolo_detector = YOLODetector(
                model_path=yolo_path, device=yolo_device
            )
            self._yolo_detector.load()
            logger.info("YOLO11-seg loaded | device=%s", yolo_device)
        except Exception as e:
            logger.warning("YOLO11-seg not available: %s", e)
            self._yolo_detector = None

        logger.info("GPU models loaded in %.1fs", time.time() - t0)

    # ------------------------------------------------------------------ #
    #  Model lifecycle — unload to free RAM
    # ------------------------------------------------------------------ #

    def unload_all(self) -> None:
        """Unload ALL models."""
        self._yolo_detector = None
        self._segformer_detector = None
        self._ensemble_detector = None
        self._pose_renderer = None
        import gc
        gc.collect()
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass
        logger.info("All models unloaded")

    def unload_gpu_models(self) -> None:
        """Unload GPU models (YOLO) to free VRAM for SE8.
        Keeps SegFormer loaded to avoid reload penalty.
        """
        self._yolo_detector = None
        self._ensemble_detector = None
        self._pose_renderer = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass
        logger.info("GPU models unloaded (SegFormer kept)")

    def _check_idle_unload(self) -> None:
        """Unload models if idle for too long."""
        if self._idle_timeout <= 0:
            return
        elapsed = time.time() - self._last_used
        if elapsed > self._idle_timeout:
            logger.info("Idle for %.0fs (timeout=%ds), unloading models", elapsed, self._idle_timeout)
            self.unload_all()

    # ------------------------------------------------------------------ #
    #  Geometry helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_inside(box1: Any, box2: Any) -> bool:
        x1, y1, x2, y2 = box1
        x1i, y1i, x2i, y2i = box2
        return x1 >= x1i and y1 >= y1i and x2 <= x2i and y2 <= y2i

    # ------------------------------------------------------------------ #
    #  Core segmentation
    # ------------------------------------------------------------------ #

    def segment(
        self,
        image_bytes: bytes,
        classes: list[str] | None = None,
        box_threshold: float | None = None,
        text_threshold: float | None = None,
        max_area_pct: float | None = None,
        max_objects: int | None = None,
        mode: str = "clothes",
        detector: str = "segformer",
        include_pose: bool = False,
    ) -> dict[str, Any]:
        """Run full segmentation pipeline on image bytes.

        Args:
            mode: "clothes" for clothing detection, "person" for person detection.
                  When "person", defaults to PERSON_CLASSES and relaxes area filter to 80%.
            detector: "segformer" (default, pixel-level), "yolo11", or "ensemble" (multi-detector).
            include_pose: If True, also generate an OpenPose-style control image
                          from MediaPipe Pose landmarks.

        Returns:
            dict with keys: detected, objects, mask_image, masks, controlnet_image,
                            pose_landmarks, processing_time_ms
        """
        t0 = time.time()

        # Check if models need to be reloaded after idle timeout
        if self._yolo_detector is None and self._segformer_detector is None:
            logger.info("Models unloaded due to idle, reloading...")
            self._load_models()
        elif self._yolo_detector is None and self._segformer_detector is not None:
            # GPU models were unloaded (unload_gpu_models) but SegFormer stays.
            # Reload GPU models (YOLO) — SegFormer stays.
            logger.info("GPU models were unloaded, reloading (SegFormer kept)...")
            self._load_gpu_models()
            # Rebuild ensemble with reloaded GPU detectors + existing SegFormer
            from app.services.ensemble_detector import EnsembleDetector
            self._ensemble_detector = EnsembleDetector()
            if self._yolo_detector is not None:
                self._ensemble_detector.set_yolo(self._yolo_detector)
            if self._segformer_detector is not None:
                self._ensemble_detector.set_segformer(self._segformer_detector)

        if mode == "person":
            classes = classes or PERSON_CLASSES
            max_area_pct = max_area_pct or DEFAULT_MAX_AREA_PCT_PERSON
        else:
            classes = classes or CLOTHING_CLASSES
            max_area_pct = max_area_pct or self.settings.max_area_pct
            # SegFormer per-class masks are naturally bounded — increase max_area_pct
            # A hoodie can cover 40%+ of the image, which is valid per-class
            if (detector == "segformer" or detector == "ensemble") and max_area_pct < 0.80:
                max_area_pct = 0.80
        box_threshold = box_threshold or self.settings.box_threshold
        text_threshold = text_threshold or self.settings.text_threshold
        max_objects = max_objects or self.settings.max_objects

        # Decode image
        img_pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        original_image = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        height, width, _ = original_image.shape
        image_area = height * width

        # 1. Detection — supports segformer, yolo11, ensemble
        if detector == "ensemble" and self._ensemble_detector is not None:
            # Multi-detector consensus voting
            ensemble_result = self._ensemble_detector.detect_ensemble(
                image_bgr=original_image,
                classes=classes,
                box_threshold=box_threshold,
                text_threshold=text_threshold,
                mode=mode,
            )
            detections = ensemble_result["detections"]
            if detections is None or len(detections) == 0:
                logger.info(
                    "Ensemble: no detection | method=%s results=%s",
                    ensemble_result["method"],
                    ensemble_result["detector_results"],
                )
                return {
                    "detected": False,
                    "objects": [],
                    "mask_image": None,
                    "processing_time_ms": round((time.time() - t0) * 1000, 1),
                }
            logger.info(
                "Ensemble: detected | method=%s coverage=%.1f%%",
                ensemble_result["method"],
                ensemble_result["coverage_pct"],
            )
            # If YOLO already gave us masks, use them directly
            if detections.mask is not None:
                # Skip to step 5 (annotate) — masks already available
                has_masks = True
            else:
                has_masks = False
        elif detector == "yolo11" and self._yolo_detector is not None:
            # YOLO11-seg direct detection
            detections = self._yolo_detector.predict(
                original_image, confidence=box_threshold or 0.25, classes=[0]
            )
            if len(detections) == 0:
                return {
                    "detected": False,
                    "objects": [],
                    "mask_image": None,
                    "processing_time_ms": round((time.time() - t0) * 1000, 1),
                }
            has_masks = detections.mask is not None
        elif detector == "segformer" and self._segformer_detector is not None:
            detections = self._segformer_detector.segment_to_sv_detections(original_image)
            has_masks = detections.mask is not None
        else:
            # Default: SegFormer
            detections = self._segformer_detector.segment_to_sv_detections(original_image)
            has_masks = detections.mask is not None

        # 2. Area filtering
        area_filtered = detections[(detections.area / image_area) < max_area_pct]

        # 3. Nesting filtering (remove boxes inside other boxes)
        # Skip for SegFormer — per-class masks are independent and valid even if bboxes overlap
        filtered_boxes: list[Any] = []
        filtered_confidences: list[Any] = []
        filtered_class_ids: list[Any] = []
        filtered_masks: list[Any] = []
        has_mask_data = area_filtered.mask is not None

        if (detector == "segformer" or (detector == "ensemble" and has_mask_data and len(area_filtered) > 0 and area_filtered.class_id[0] in (4, 5, 6, 7))) and has_mask_data:
            # SegFormer: skip nesting filter — each class is independent
            for i in range(len(area_filtered)):
                filtered_boxes.append(area_filtered.xyxy[i])
                filtered_confidences.append(area_filtered.confidence[i])
                filtered_class_ids.append(area_filtered.class_id[i])
                filtered_masks.append(area_filtered.mask[i])
        else:
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
                    if has_mask_data:
                        filtered_masks.append(area_filtered.mask[i])

        final_detections = sv.Detections(
            xyxy=np.array(filtered_boxes) if filtered_boxes else np.empty((0, 4)),
            confidence=np.array(filtered_confidences),
            class_id=np.array(filtered_class_ids),
            mask=np.array(filtered_masks) if filtered_masks else None,
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

        # 4. Masks — SegFormer and YOLO11-seg already provide masks
        # SAM2 removed — SegFormer returns pixel-level masks directly

        # 5. Annotate
        mask_annotator = sv.MaskAnnotator()
        box_annotator = sv.BoxAnnotator()
        # Build labels — handle YOLO class IDs (0=person) vs text classes
        labels = []
        for cls_id, conf in zip(final_detections.class_id, final_detections.confidence):
            if detector in ("yolo11", "ensemble") and cls_id == 0:
                labels.append(f"person {conf:.2f}")
            elif detector in ("segformer",) or (detector == "ensemble" and cls_id in (4, 5, 6, 7)):
                from app.services.segformer_detector import LABELS as SEGLABELS
                label = SEGLABELS[cls_id] if cls_id < len(SEGLABELS) else f"class_{cls_id}"
                labels.append(f"{label} {conf:.2f}")
            elif cls_id < len(classes):
                labels.append(f"{classes[cls_id]} {conf:.2f}")
            else:
                labels.append(f"class_{cls_id} {conf:.2f}")
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
        binary_masks: list[str] = []
        if final_detections.mask is not None:
            for mask_arr in final_detections.mask:
                mask_uint8 = (mask_arr.astype(np.uint8)) * 255
                _, mask_buffer = cv2.imencode(".png", mask_uint8)
                mask_b64_str = f"data:image/png;base64,{base64.b64encode(mask_buffer).decode('utf-8')}"
                binary_masks.append(mask_b64_str)

        # 7. Build response
        areas = final_detections.area if len(final_detections) > 0 else np.array([])
        detected_objects: list[dict[str, Any]] = []
        for i, (cls_id, conf, xyxy) in enumerate(zip(
            final_detections.class_id,
            final_detections.confidence,
            final_detections.xyxy,
        )):
            if detector == "segformer" or (detector == "ensemble" and cls_id in (4, 5, 6, 7)):
                from app.services.segformer_detector import LABELS as SEGLABELS
                class_name = SEGLABELS[cls_id] if cls_id < len(SEGLABELS) else f"class_{cls_id}"
            elif cls_id < len(classes):
                class_name = classes[cls_id]
            else:
                class_name = f"class_{cls_id}"

            detected_objects.append({
                "class_name": class_name,
                "confidence": round(float(conf), 4),
                "bbox": [int(b) for b in xyxy],
                "area_pct": round(float(areas[i] / image_area) * 100, 2),
            })

        _, buffer = cv2.imencode(".jpg", annotated)
        mask_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

        # 8. Optional pose control image
        controlnet_image: str | None = None
        pose_landmarks: list[dict[str, Any]] = []
        if include_pose:
            # Lazy-init PoseRenderer on first use
            if self._pose_renderer is None:
                self._pose_renderer = PoseRenderer(
                    min_detection_confidence=self.settings.pose_min_confidence
                )
            try:
                rgb_image = cv2.cvtColor(original_image, cv2.COLOR_BGR2RGB)
                landmarks = self._pose_renderer.detect(rgb_image)
                if landmarks is not None:
                    pose_canvas = self._pose_renderer.render_stick_figure(
                        landmarks, image_size=(height, width)
                    )
                    _, pose_buf = cv2.imencode(".png", pose_canvas)
                    controlnet_image = (
                        f"data:image/png;base64,{base64.b64encode(pose_buf).decode('utf-8')}"
                    )
                    pose_landmarks = [lm.to_dict() for lm in landmarks]
                    logger.info("Pose control image generated | landmarks=%d", len(landmarks))
                else:
                    logger.info("No pose detected for control image")
            except Exception as exc:
                logger.warning("Failed to generate pose control image: %s", exc)

        processing_ms = round((time.time() - t0) * 1000, 1)
        logger.info(
            "Segmentation complete | objects=%d time=%.1fms",
            len(detected_objects), processing_ms,
        )

        # Release intermediate tensors and force OS to reclaim memory
        self._last_used = time.time()
        import gc
        gc.collect()
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass

        return {
            "detected": True,
            "objects": detected_objects,
            "mask_image": mask_b64,
            "masks": binary_masks,
            "controlnet_image": controlnet_image,
            "pose_landmarks": pose_landmarks,
            "processing_time_ms": processing_ms,
        }
