"""NSFW Production Pipeline — retry + pose validation + best selection.

Inherits from NSFWPipelineBase (Template Method).
Customizes: 6-layer mask construction, per-attempt pose, debug grid, attempts.json.
"""
from __future__ import annotations

import base64
import json
import os

import cv2 as _cv2
import numpy as _np

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.services.head_detector import detect_head_mask, detect_face_only, detect_face_oval_mask
from app.services._helpers import (
    CLOTHES_CLASSES, SCORING,
    get_nsfw_config,
    decode_image as _decode_image,
    to_data_uri as _to_data_uri,
    strip_data_uri as _strip_data_uri,
    fix_b64_padding as _fix_b64_padding,
    combine_masks as _combine_masks,
    detect_skin_hsv as _detect_skin_hsv,
    detect_person_with_fallbacks,
)
from app.services.ip_adapter_utils import build_clothes_neutral_ref
from app.services.pipeline_base import NSFWPipelineBase
from app.services.debug_utils import (
    save_debug_image, build_debug_grid, save_mask_overlay, save_detection_metadata, save_garment_masks,
)
from app.services.faceid_extractor import extract_faceid_embedding

logger = get_logger(__name__)


class NSFWProductionPipeline(NSFWPipelineBase):
    """Production NSFW pipeline — 6-layer mask, per-attempt pose, debug grid.

    Overrides:
    - build_masks: 6-layer layered approach (person → hair → face → protection → inpaint → dilate)
    - build_ip_adapter_ref: Clothes-neutral ref using head_mask for skin tone sampling
    - get_openpose_image: Uses pose_cn_b64 from SE10 detection
    - should_detect_pose_per_attempt: True
    - _save_attempts_metadata: Custom format with debug grid
    - get_prompt_negative: Uses config NSFW prompt (ignores user prompt)
    """

    def __init__(self, job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
        super().__init__(job, store)
        self.head_adjusted: _np.ndarray | None = None

    def get_nsfw_config(self):
        return get_nsfw_config("production")

    def should_include_pose(self) -> bool:
        return True

    def should_detect_pose_per_attempt(self) -> bool:
        return True

    def get_openpose_image(self) -> str | None:
        return getattr(self, "_pose_cn_b64", None)

    def get_prompt_negative(self) -> tuple[str, str]:
        """Production uses config NSFW prompt — ignores user prompt."""
        if self.job.request.prompt:
            logger.info("Job %s: ignoring user prompt on /jobs/nsfw route, using config NSFW prompt",
                        self.job_id)
        nsfw_cfg = self._nsfw_cfg
        return nsfw_cfg.prompt, nsfw_cfg.negative

    async def build_masks(self) -> None:
        """6-layer layered mask construction.

        Layer 1: Person silhouette (SE10) — background already removed
        Layer 2: Hair protection — head_mask (ellipse, tight neck)
        Layer 3: Face protection — face_oval_mask (MediaPipe landmarks)
        Layer 4: Combined protection = hair OR face
        Layer 5: Inpaint = person − protection (clothing + exposed skin)
        Layer 6: Dilate + close for smooth SE8 edges
        """
        nsfw_cfg = self._nsfw_cfg
        orig_img = self.orig_img
        person_binary = self.person_binary

        # Find person bbox
        contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours found")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        # ─── Layer 2: Hair protection (tight neck — does NOT eat clothing) ──
        self.hair_mask = detect_head_mask(
            orig_img=orig_img, person_binary=person_binary,
            person_bbox=(px, py, pw, ph),
            max_head_pct=nsfw_cfg.hd_max_head_pct,
            neck_margin_below=nsfw_cfg.hd_neck_margin_below,
            dilate_kernel_size=nsfw_cfg.hd_dilate_kernel_size,
            dilate_iterations=nsfw_cfg.hd_dilate_iterations,
            expand_up=nsfw_cfg.hd_expand_up,
            expand_w=nsfw_cfg.hd_expand_w,
        )

        # ─── Layer 3: Face protection (MediaPipe Face Mesh oval) ─────────
        self.face_mask = detect_face_oval_mask(
            orig_img=orig_img, person_binary=person_binary,
            feather_bottom_px=nsfw_cfg.fp_feather_bottom_px,
        )
        if _cv2.countNonZero(self.face_mask) == 0:
            logger.warning("Job %s: face_oval_mask empty, falling back to haarcascade", self.job_id)
            self.face_mask = detect_face_only(
                orig_img=orig_img, person_binary=person_binary,
                margin_above=nsfw_cfg.fp_margin_above,
                margin_below=nsfw_cfg.fp_margin_below,
                margin_sides=nsfw_cfg.fp_margin_sides,
            )

        # ─── Layer 4: Combined protection = hair OR face ─────────────────
        protection_mask = _cv2.bitwise_or(self.hair_mask, self.face_mask)
        logger.info("Job %s: protection mask — hair=%d px, face=%d px, combined=%d px",
                     self.job_id,
                     _cv2.countNonZero(self.hair_mask),
                     _cv2.countNonZero(self.face_mask),
                     _cv2.countNonZero(protection_mask))

        # ─── Layer 5: Inpaint = person − protection ──────────────────────
        inpaint_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(protection_mask))

        # ─── Layer 6: Dilate + close for smooth SE8 edges ────────────────
        dilation_px = max(10, int(min(self.orig_w, self.orig_h) * nsfw_cfg.fp_dilation_pct))
        expand_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
        inpaint_mask = _cv2.dilate(inpaint_mask, expand_kernel, iterations=2)

        # Clip to expanded person (no background leaking)
        person_expanded = _cv2.dilate(person_binary, expand_kernel, iterations=3)
        inpaint_mask = _cv2.bitwise_and(inpaint_mask, person_expanded)

        # ─── Layer 6b: Ghost face suppression zone ──────────────────────
        # Erode inpaint mask near face boundary to prevent SE8 from
        # hallucinating facial features at the mask/protection junction
        face_zone = _cv2.dilate(protection_mask, expand_kernel, iterations=2)
        ghost_erosion_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
        inpaint_near_face = _cv2.bitwise_and(inpaint_mask, face_zone)
        inpaint_near_face = _cv2.erode(inpaint_near_face, ghost_erosion_k, iterations=1)
        inpaint_elsewhere = _cv2.bitwise_and(inpaint_mask, _cv2.bitwise_not(face_zone))
        inpaint_mask = _cv2.bitwise_or(inpaint_elsewhere, inpaint_near_face)

        # Morphological closing to fill small holes
        close_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
        inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_k, iterations=2)

        self.inpaint_mask = inpaint_mask
        self.head_adjusted = self.hair_mask

        clothes_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
        hair_pct = _cv2.countNonZero(self.hair_mask) / self.hair_mask.size * 100
        logger.info("Job %s: nsfw inpaint=%.1f%% hair=%.1f%%",
                     self.job_id, clothes_pct, hair_pct)

    async def build_ip_adapter_ref(self) -> None:
        """Clothes-neutral IP-Adapter reference using head_mask for skin tone sampling.

        The encoder sees pose/face/body-shape but NOT clothing texture.
        This prevents attention leaking to clothing regions → no sweater residual.
        """
        # Need clothes_combined for IP-Adapter ref
        clothes_seg = await self.se10.segment(
            image_bytes=self.image_bytes,
            filename=f"{self.job_id}_clothes_ref.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
            box_threshold=0.12, text_threshold=0.08,
            mode="clothes", detector="ensemble",
        )

        clothes_combined = None
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            for mb in clothes_seg.get("masks", []):
                raw_c = _strip_data_uri(mb)
                c_bytes = base64.b64decode(_fix_b64_padding(raw_c))
                cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                if cm is not None:
                    if cm.shape[:2] != (self.orig_h, self.orig_w):
                        cm = _cv2.resize(cm, (self.orig_w, self.orig_h))
                    cb = (cm > 127).astype(_np.uint8) * 255
                    clothes_combined = cb if clothes_combined is None else _cv2.bitwise_or(clothes_combined, cb)

        self.ip_ref_img = build_clothes_neutral_ref(
            self.orig_img, clothes_combined, self.person_binary, self.hair_mask)

        # Save debug overlays
        self._save_production_debug_overlays(clothes_combined)

    def _save_production_debug_overlays(self, clothes_combined: _np.ndarray | None) -> None:
        """Save production-specific debug overlays."""
        inpaint_pct = (self.inpaint_mask > 0).sum() / self.inpaint_mask.size * 100
        clothes_orig_pct = (clothes_combined > 0).sum() / clothes_combined.size * 100 if clothes_combined is not None else 0

        # Mask overlay
        mask_overlay = self.orig_img.copy()
        mask_color = _cv2.cvtColor(self.inpaint_mask, _cv2.COLOR_GRAY2BGR)
        mask_color[:, :, 0] = 0
        mask_color[:, :, 2] = 0
        mask_overlay = _cv2.addWeighted(mask_overlay, 0.6, mask_color, 0.4, 0)
        _cv2.putText(mask_overlay,
                     f"Inpaint mask: {inpaint_pct:.1f}% | clothes: {clothes_orig_pct:.1f}%",
                     (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        _cv2.putText(mask_overlay, f"LustifyNSFW | FaceID={'on' if self.faceid_embedding else 'off'}",
                     (10, 50), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        save_debug_image(self.output_dir, 30, "mask_overlay", mask_overlay)

        # Head protection overlay
        face_overlay = self.orig_img.copy()
        hm_color = _cv2.cvtColor(self.hair_mask, _cv2.COLOR_GRAY2BGR)
        hm_color[:, :, 1] = 0
        hm_color[:, :, 2] = 0
        face_overlay = _cv2.addWeighted(face_overlay, 0.6, hm_color, 0.4, 0)
        inp_color = _cv2.cvtColor(self.inpaint_mask, _cv2.COLOR_GRAY2BGR)
        inp_color[:, :, 0] = 0
        inp_color[:, :, 2] = 0
        face_overlay = _cv2.addWeighted(face_overlay, 0.7, inp_color, 0.3, 0)
        head_pct = _cv2.countNonZero(self.hair_mask) / self.hair_mask.size * 100
        _cv2.putText(face_overlay,
                     f"Head protect: {head_pct:.1f}% | Inpaint: {inpaint_pct:.1f}%",
                     (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 100, 0), 2)
        save_debug_image(self.output_dir, 31, "face_protect_overlay", face_overlay)

    def _save_attempts_metadata(self) -> None:
        """Save attempts metadata + debug grid."""
        super()._save_attempts_metadata()

        # Save debug grid
        try:
            inpaint_pct = (_cv2.countNonZero(self.inpaint_mask) / self.inpaint_mask.size) * 100.0
            panels = [
                ("00_original", self.orig_img, "1. Original"),
                ("01_person", self.person_binary, "2. Person (SE10)"),
                ("02_head_full", self.hair_mask, "3. Head (face+hair)"),
                ("03b_face_only", self.face_mask, "4. Face Only (protected)"),
            ]
            if self.clothes_seg.get("masks"):
                # Get clothes combined for grid
                clothes_combined = _combine_masks(
                    self.clothes_seg["masks"], self.orig_h, self.orig_w)
                if clothes_combined is not None:
                    panels.append(("04_clothes", clothes_combined, "5. Clothes (Florence-2)"))
            panels.extend([
                ("06_inpaint_mask", self.inpaint_mask, f"6. Inpaint Mask ({inpaint_pct:.1f}%)"),
                ("07_head_adjusted", self.head_adjusted, f"7. Head Adjusted"),
                ("result", self._best_composited, f"8. Result ({self._best_try}, score={self._best_score:.3f})"),
            ])
            grid = build_debug_grid(panels)
            _cv2.imwrite(os.path.join(self.output_dir, f"{self.job_id}_debug_grid.png"), grid)
        except Exception as exc:
            logger.warning("Job %s: debug grid failed (%s)", self.job_id, exc)


async def run_nsfw(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Entry point for production NSFW pipeline.

    Pre-scans for multiple persons. If >1 person detected, routes to
    MultiPersonPipeline for per-person processing.
    """
    from app.services.detection_fallbacks import detect_all_persons
    from app.infrastructure.http_client import SE10Client

    se10 = SE10Client()
    try:
        image_bytes = _decode_image(job.request.image)
        orig_img = _cv2.imdecode(
            _np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode image")
        orig_h, orig_w = orig_img.shape[:2]

        persons, _, _ = await detect_all_persons(
            se10, image_bytes, job.job_id, orig_h, orig_w,
            min_area_pct=5.0, include_pose=False,
        )

        if len(persons) > 1:
            logger.info("Job %s: %d persons detected, using multi-person pipeline",
                        job.job_id, len(persons))
            from app.services.pipeline_multi_person import MultiPersonPipeline
            mp = MultiPersonPipeline(job, store)
            await mp.run()
        else:
            if persons:
                logger.info("Job %s: 1 person detected, using standard pipeline", job.job_id)
            else:
                logger.info("Job %s: 0 persons detected, using standard pipeline (fallback)", job.job_id)
            pipeline = NSFWProductionPipeline(job, store)
            await pipeline.run()
    finally:
        await se10.close()
