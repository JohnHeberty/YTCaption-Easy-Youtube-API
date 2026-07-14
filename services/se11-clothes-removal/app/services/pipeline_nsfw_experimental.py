"""NSFW Experimental Pipeline — invert mask + low denoise + FaceID.

Inherits from NSFWPipelineBase (Template Method).
Customizes: 3 mask modes, pose detection once, OpenPose stick figure, show/ copy.
"""
from __future__ import annotations

import base64
import json
import os
import time

import cv2 as _cv2
import numpy as _np

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.services.head_detector import detect_head_mask, detect_face_only, detect_face_oval_mask
from app.services._helpers import (
    CLOTHES_CLASSES, DEFAULT_CLOTHES_NEGATIVE, SCORING,
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
    save_debug_image, save_mask_overlay, save_detection_metadata, save_garment_masks,
)
from app.services.faceid_extractor import extract_faceid_embedding
from app.validators.pose_detector import detect_pose, compare_poses, render_pose_stick_figure

logger = get_logger(__name__)


class NSFWExperimentalPipeline(NSFWPipelineBase):
    """Experimental NSFW pipeline — 3 mask modes, pose once, OpenPose stick figure.

    Overrides:
    - build_masks: 3 modes (invert_mask, clothes_mask, body_mask)
    - build_ip_adapter_ref: Clothes-neutral ref without head_mask
    - get_openpose_image: Generates OpenPose stick figure via render_pose_stick_figure
    - should_detect_pose_per_attempt: False (detect once)
    - get_prompt_negative: Uses config NSFW prompt
    - _save_attempts_metadata: Custom format with v2_meta.json
    - _copy_to_show: Copies result to show/
    """

    def __init__(self, job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
        super().__init__(job, store)
        self._orig_pose = None

    def get_nsfw_config(self):
        return get_nsfw_config("experimental")

    def should_include_pose(self) -> bool:
        return False

    def should_detect_pose_per_attempt(self) -> bool:
        return False

    def get_prompt_negative(self) -> tuple[str, str]:
        """Experimental uses config NSFW prompt."""
        nsfw_cfg = self._nsfw_cfg
        return nsfw_cfg.prompt, DEFAULT_CLOTHES_NEGATIVE

    def get_openpose_image(self) -> str | None:
        """Generate OpenPose stick figure via render_pose_stick_figure."""
        if self._orig_pose is None:
            return None
        try:
            openpose_img = render_pose_stick_figure(self._orig_pose, thickness=4)
            save_debug_image(self.output_dir, 5, "openpose", openpose_img)
            _, op_buf = _cv2.imencode(".png", openpose_img)
            openpose_b64 = _to_data_uri(base64.b64encode(op_buf).decode("utf-8"), mime="image/png")
            logger.info("Job %s: OpenPose stick figure generated", self.job_id)
            return openpose_b64
        except Exception as exc:
            logger.warning("Job %s: OpenPose generation failed: %s", self.job_id, exc)
            return None

    async def build_masks(self) -> None:
        """Build masks — 3 modes: invert_mask, clothes_mask, body_mask.

        invert_mask (default): layered protection (clothes → close → dilate → protect hair/face)
        clothes_mask: simple clothes mask + dilation
        body_mask: person minus head mask
        """
        nsfw_cfg = self._nsfw_cfg
        inpaint_mode = getattr(self.job.request, "inpaint_mode", "invert_mask")

        if self.clothes_combined is None:
            logger.warning("Job %s: no clothes detected, using body mask fallback", self.job_id)
            self.clothes_combined = self.person_binary.copy()

        if inpaint_mode == "invert_mask":
            await self._build_invert_mask()
        elif inpaint_mode == "clothes_mask":
            self._build_clothes_mask()
        else:
            self._build_body_mask()

        inpaint_pct = (self.inpaint_mask > 0).sum() / self.inpaint_mask.size * 100
        clothes_pct = (self.clothes_combined > 0).sum() / self.clothes_combined.size * 100
        logger.info("Job %s: mask=%s inpaint=%.1f%% clothes_orig=%.1f%%",
                     self.job_id, inpaint_mode, inpaint_pct, clothes_pct)

        # Save mask overlay
        save_mask_overlay(self.output_dir, 3, f"inpaint_mask_{inpaint_mode}",
                         self.orig_img, self.inpaint_mask)

    async def _build_invert_mask(self) -> None:
        """Layered protection: clothes → close → dilate → protect hair/face."""
        nsfw_cfg = self._nsfw_cfg
        inpaint_mask = self.clothes_combined.copy()

        # Close gaps between clothing items
        close_k = _cv2.getStructuringElement(
            _cv2.MORPH_ELLIPSE, (nsfw_cfg.cg_close_kernel_size, nsfw_cfg.cg_close_kernel_size))
        inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_k)

        # Constrain to person silhouette
        inpaint_mask = _cv2.bitwise_and(inpaint_mask, self.person_binary)

        # Dilate
        dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
        inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=1)

        # Find person bbox
        contours, _ = _cv2.findContours(self.person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=_cv2.contourArea)
            px, py, pw, ph = _cv2.boundingRect(largest)

            # Hair protection
            hair_mask = detect_head_mask(
                orig_img=self.orig_img, person_binary=self.person_binary,
                person_bbox=(px, py, pw, ph),
                max_head_pct=nsfw_cfg.hd_max_head_pct,
                neck_margin_below=nsfw_cfg.hd_neck_margin_below,
                dilate_kernel_size=nsfw_cfg.hd_dilate_kernel_size,
                dilate_iterations=nsfw_cfg.hd_dilate_iterations,
                expand_up=nsfw_cfg.hd_expand_up,
                expand_w=nsfw_cfg.hd_expand_w,
            )

            # Face protection
            face_mask = detect_face_oval_mask(
                orig_img=self.orig_img, person_binary=self.person_binary,
                feather_bottom_px=nsfw_cfg.fp_feather_bottom_px,
            )
            if _cv2.countNonZero(face_mask) == 0:
                face_mask = detect_face_only(
                    orig_img=self.orig_img, person_binary=self.person_binary,
                    margin_above=nsfw_cfg.fp_margin_above,
                    margin_below=nsfw_cfg.fp_margin_below,
                    margin_sides=nsfw_cfg.fp_margin_sides,
                )

            protection_mask = _cv2.bitwise_or(hair_mask, face_mask)
            inpaint_mask = _cv2.bitwise_and(inpaint_mask, _cv2.bitwise_not(protection_mask))
            logger.info("Job %s: layered protection applied (hair=%d face=%d)",
                        self.job_id, _cv2.countNonZero(hair_mask), _cv2.countNonZero(face_mask))

            # Smooth edges: dynamic dilation based on fp_dilation_pct
            dilation_px = max(10, int(min(self.orig_w, self.orig_h) * nsfw_cfg.fp_dilation_pct))
            expand_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
            inpaint_mask = _cv2.dilate(inpaint_mask, expand_kernel, iterations=2)

            # Clip to expanded person (no background leaking)
            person_expanded = _cv2.dilate(self.person_binary, expand_kernel, iterations=3)
            inpaint_mask = _cv2.bitwise_and(inpaint_mask, person_expanded)

            # Ghost face suppression zone: erode near face boundary to prevent
            # SE8 from hallucinating facial features at mask/protection junction
            face_zone = _cv2.dilate(protection_mask, expand_kernel, iterations=2)
            ghost_erosion_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
            inpaint_near_face = _cv2.bitwise_and(inpaint_mask, face_zone)
            inpaint_near_face = _cv2.erode(inpaint_near_face, ghost_erosion_k, iterations=1)
            inpaint_elsewhere = _cv2.bitwise_and(inpaint_mask, _cv2.bitwise_not(face_zone))
            inpaint_mask = _cv2.bitwise_or(inpaint_elsewhere, inpaint_near_face)

            # Morphological closing to fill small holes
            close_smooth = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
            inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_smooth, iterations=2)

        self.inpaint_mask = inpaint_mask

    def _build_clothes_mask(self) -> None:
        """Simple clothes mask + dilation."""
        inpaint_mask = self.clothes_combined.copy()
        dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (21, 21))
        inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=2)
        self.inpaint_mask = inpaint_mask

    def _build_body_mask(self) -> None:
        """Body mask: person minus head."""
        nsfw_cfg = self._nsfw_cfg
        contours, _ = _cv2.findContours(self.person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            raise ValueError("No contours found")
        largest = max(contours, key=_cv2.contourArea)
        px, py, pw, ph = _cv2.boundingRect(largest)

        head_mask = detect_head_mask(
            orig_img=self.orig_img, person_binary=self.person_binary,
            person_bbox=(px, py, pw, ph),
            max_head_pct=nsfw_cfg.hd_max_head_pct,
            neck_margin_below=nsfw_cfg.hd_neck_margin_below,
            dilate_kernel_size=nsfw_cfg.hd_dilate_kernel_size,
            dilate_iterations=nsfw_cfg.hd_dilate_iterations,
        )
        inpaint_mask = _cv2.bitwise_and(self.person_binary, _cv2.bitwise_not(head_mask))
        dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
        inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=2)
        self.inpaint_mask = inpaint_mask

    async def build_ip_adapter_ref(self) -> None:
        """Clothes-neutral IP-Adapter reference (simpler version, no head_mask)."""
        self.ip_ref_img = build_clothes_neutral_ref(
            self.orig_img, self.clothes_combined, self.person_binary)

        save_debug_image(self.output_dir, 4, "neutral_ref", self.ip_ref_img)

    async def _detect_person(self) -> None:
        """Override to also detect pose once after person detection."""
        await super()._detect_person()
        # Detect pose once (experimental does this before the loop)
        self._orig_pose = self._detect_pose_once()
        if self._orig_pose:
            self._save_pose_debug()

    def _save_pose_debug(self) -> None:
        """Save pose landmarks overlay on original."""
        try:
            pose_overlay = self.orig_img.copy()
            h, w = pose_overlay.shape[:2]
            sx = w / self._orig_pose.image_width
            sy = h / self._orig_pose.image_height
            for lm in self._orig_pose.landmarks:
                if lm.visibility > 0.3:
                    color = (0, 255, 0) if lm.group != "HEAD" else (255, 255, 0)
                    _cv2.circle(pose_overlay, (int(lm.x * sx), int(lm.y * sy)), 4, color, -1)
            # Draw body connections
            body_conns = [(0,1),(1,2),(1,5),(2,3),(3,4),(5,6),(6,7),(1,8),(1,11),(8,9),(9,10),(11,12),(12,13)]
            body_px = {}
            for lm in self._orig_pose.landmarks:
                if lm.visibility > 0.3:
                    body_px[lm.index] = (int(lm.x * sx), int(lm.y * sy))
            for i, j in body_conns:
                p1, p2 = body_px.get(i), body_px.get(j)
                if p1 and p2:
                    _cv2.line(pose_overlay, p1, p2, (0, 255, 0), 2)
            total = len(self._orig_pose.landmarks) + len(self._orig_pose.hand_left_landmarks) + len(self._orig_pose.hand_right_landmarks)
            _cv2.putText(pose_overlay, f"Pose: {total} keypoints (body+hands)",
                        (10, 25), _cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            save_debug_image(self.output_dir, 6, "pose_landmarks", pose_overlay)
        except Exception as e:
            logger.debug("Failed to save pose overlay: %s", e)

    def _save_attempts_metadata(self) -> None:
        """Save v2_meta.json with custom experimental format."""
        nsfw_cfg = self._nsfw_cfg
        base_strength = getattr(self.job.request, "test_inpaint_strength", nsfw_cfg.base_strength) or nsfw_cfg.base_strength

        best_meta = {}
        for m in self._all_attempts_meta:
            if m.get("composite_score", float("inf")) == self._best_score:
                best_meta = m
                break

        all_poses_changed = all(m.get("pose_changed", True) for m in self._all_attempts_meta if m.get("status") == "ok")

        meta = {
            "mode": "nsfw_test_v2",
            "scoring": "multidimensional_v2",
            "scoring_weights": {
                "skin": SCORING.skin, "head": SCORING.head,
                "landmark": SCORING.landmark, "clothes": SCORING.clothes,
            },
            "inpaint_mode": getattr(self.job.request, "inpaint_mode", "invert_mask"),
            "strength": float(base_strength),
            "faceid": self.faceid_embedding is not None,
            "faceid_weight": float(getattr(self.job.request, "faceid_weight", nsfw_cfg.ip_adapter_faceid_weight) or nsfw_cfg.ip_adapter_faceid_weight),
            "face_restore": getattr(self.job.request, "face_restore", False),
            "original_skin_pct": float(round(self.original_skin_pct, 1)),
            "attempts": len(self._all_attempts_meta),
            "best_composite_score": float(self._best_score),
            "best_skin_ratio": float(best_meta.get("skin_ratio", 0.0)),
            "best_result_skin_pct": float(best_meta.get("result_skin_pct", 0.0)),
            "best_head_pct": float(best_meta.get("head_pct", 0.0)),
            "best_clothes_pct": float(best_meta.get("result_clothes_pct", 0.0)),
            "best_max_landmark_pct": float(best_meta.get("max_landmark_pct", 0.0)),
            "best_pose_changed": bool(best_meta.get("pose_changed", True)),
            "all_poses_changed": bool(all_poses_changed),
            "person_coverage": float(round((self.person_binary > 0).sum() / self.person_binary.size * 100, 1)),
            "clothes_coverage": float(round((self.clothes_combined > 0).sum() / self.clothes_combined.size * 100, 1)) if self.clothes_combined is not None else 0.0,
            "inpaint_coverage": float(round((self.inpaint_mask > 0).sum() / self.inpaint_mask.size * 100, 1)),
            "attempts_detail": self._all_attempts_meta,
        }
        with open(os.path.join(self.output_dir, "v2_meta.json"), "w") as ef:
            json.dump(meta, ef, indent=2)

    def _copy_to_show(self, composited: _np.ndarray) -> None:
        """Copy result to show/ directory."""
        try:
            show_dir = "/root/YTCaption-Easy-Youtube-API/show"
            os.makedirs(show_dir, exist_ok=True)
            _cv2.imwrite(os.path.join(show_dir, f"v2_{self.job_id}_result.png"), composited)
            logger.info("Job %s: result copied to show/", self.job_id)
        except Exception as exc:
            logger.warning("Job %s: show/ copy failed: %s", self.job_id, exc)


async def run_nsfw_experimental(
    job: ClothesRemovalJob,
    store: ClothesRemovalJobStore,
) -> None:
    """Entry point for experimental NSFW pipeline. Maintains backward compatibility."""
    pipeline = NSFWExperimentalPipeline(job, store)
    await pipeline.run()
