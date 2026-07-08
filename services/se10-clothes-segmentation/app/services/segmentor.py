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
from app.services.segformer_detector import CLOTHING_IDS
from app.services.segment_helpers import (
    annotate_detections,
    build_detected_objects,
    filter_detections,
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
        self._cleanup_memory()
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
        self._cleanup_memory()
        logger.info("GPU models unloaded (SegFormer kept)")

    def _check_idle_unload(self) -> None:
        """Unload models if idle for too long."""
        if self._idle_timeout <= 0:
            return
        elapsed = time.time() - self._last_used
        if elapsed > self._idle_timeout:
            logger.info("Idle for %.0fs (timeout=%ds), unloading models", elapsed, self._idle_timeout)
            self.unload_all()

    @staticmethod
    def _cleanup_memory() -> None:
        """Force garbage collection and OS memory reclaim."""
        import gc
        gc.collect()
        try:
            import ctypes
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    #  Geometry helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_inside(box1: Any, box2: Any) -> bool:
        from app.services.segment_helpers import is_inside
        return is_inside(box1, box2)

    # ------------------------------------------------------------------ #
    #  Core segmentation
    # ------------------------------------------------------------------ #

    def _empty_result(self, t0: float) -> dict[str, Any]:
        """Standard empty result when no detections found."""
        return {
            "detected": False,
            "objects": [],
            "mask_image": None,
            "processing_time_ms": round((time.time() - t0) * 1000, 1),
        }

    def _detect(self, original_image: np.ndarray, detector: str, mode: str,
                classes: list[str], box_threshold: float, text_threshold: float):
        """Run detection with the specified detector. Returns (detections, has_masks)."""
        if detector == "ensemble" and self._ensemble_detector is not None:
            ensemble_result = self._ensemble_detector.detect_ensemble(
                image_bgr=original_image, classes=classes,
                box_threshold=box_threshold, text_threshold=text_threshold, mode=mode,
            )
            detections = ensemble_result["detections"]
            if detections is None or len(detections) == 0:
                logger.info("Ensemble: no detection | method=%s results=%s",
                            ensemble_result["method"], ensemble_result["detector_results"])
                return None, False
            logger.info("Ensemble: detected | method=%s coverage=%.1f%%",
                        ensemble_result["method"], ensemble_result["coverage_pct"])
            has_masks = detections.mask is not None if detections.mask is not None else False
            return detections, has_masks
        elif detector == "yolo11" and self._yolo_detector is not None:
            detections = self._yolo_detector.predict(
                original_image, confidence=box_threshold or 0.25, classes=[0])
            if len(detections) == 0:
                return None, False
            return detections, detections.mask is not None
        else:
            detections = self._segformer_detector.segment_to_sv_detections(original_image)
            return detections, detections.mask is not None

    def _filter_detections(self, detections, detector: str, max_area_pct: float,
                           image_area: int, max_objects: int, has_masks: bool):
        """Filter by area, nesting, and cap to max_objects."""
        return filter_detections(detections, detector, max_area_pct, image_area, max_objects, has_masks)

    def _annotate(self, original_image, final_detections, detector: str, classes: list[str]):
        """Build annotated image with masks and labels."""
        return annotate_detections(original_image, final_detections, detector, classes)

    def _build_objects(self, final_detections, detector: str, classes: list[str], image_area: int):
        """Build detected_objects list and binary masks."""
        return build_detected_objects(final_detections, detector, classes, image_area)

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

        # 1. Detection
        detections, has_masks = self._detect(original_image, detector, mode, classes, box_threshold, text_threshold)
        if detections is None:
            return self._empty_result(t0)

        # 2. Filtering (area + nesting + cap)
        final_detections = self._filter_detections(detections, detector, max_area_pct, image_area, max_objects, has_masks)
        if len(final_detections) == 0:
            return self._empty_result(t0)

        # 3. Annotate
        annotated = self._annotate(original_image, final_detections, detector, classes)

        # 4. Build objects and masks
        detected_objects, binary_masks = self._build_objects(final_detections, detector, classes, image_area)

        _, buffer = cv2.imencode(".jpg", annotated)
        mask_b64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

        # 5. Optional pose control image
        controlnet_image: str | None = None
        pose_landmarks: list[dict[str, Any]] = []
        if include_pose:
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
                    controlnet_image = f"data:image/png;base64,{base64.b64encode(pose_buf).decode('utf-8')}"
                    pose_landmarks = [lm.to_dict() for lm in landmarks]
                    logger.info("Pose control image generated | landmarks=%d", len(landmarks))
                else:
                    logger.info("No pose detected for control image")
            except Exception as exc:
                logger.warning("Failed to generate pose control image: %s", exc)

        processing_ms = round((time.time() - t0) * 1000, 1)
        logger.info("Segmentation complete | objects=%d time=%.1fms", len(detected_objects), processing_ms)

        self._last_used = time.time()
        self._cleanup_memory()

        return {
            "detected": True,
            "objects": detected_objects,
            "mask_image": mask_b64,
            "masks": binary_masks,
            "controlnet_image": controlnet_image,
            "pose_landmarks": pose_landmarks,
            "processing_time_ms": processing_ms,
        }
