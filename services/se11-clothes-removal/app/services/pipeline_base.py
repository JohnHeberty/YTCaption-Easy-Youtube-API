"""NSFW Pipeline Base — Template Method for shared pipeline logic.

Provides the common skeleton for both production and experimental NSFW pipelines.
Subclasses override abstract methods to customize behavior.
"""
from __future__ import annotations

import base64
import json
import os
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import cv2 as _cv2
import numpy as _np

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.services.head_detector import detect_head_mask, detect_face_only, detect_face_oval_mask
from app.services.faceid_extractor import extract_faceid_embedding
from app.services._helpers import (
    CLOTHES_CLASSES, SCORING,
    get_nsfw_config,
    decode_image as _decode_image,
    to_data_uri as _to_data_uri,
    strip_data_uri as _strip_data_uri,
    fix_b64_padding as _fix_b64_padding,
    combine_masks as _combine_masks,
    detect_skin_hsv as _detect_skin_hsv,
    compute_composite_score as _compute_composite_score,
    detect_person_with_fallbacks,
    upscale_result as _upscale_result,
    restore_face as _restore_face,
)
from app.services.ip_adapter_utils import build_clothes_neutral_ref
from app.services.debug_utils import (
    save_debug_image,
    save_mask_overlay,
    save_detection_metadata,
    save_garment_masks,
)

if TYPE_CHECKING:
    from app.services.config_loader import NSFWConfig

logger = get_logger(__name__)

# ─── Scoring aliases (backward compat) ──────────────────────────────────────
SCORE_W_SKIN = SCORING.skin
SCORE_W_HEAD = SCORING.head
SCORE_W_LANDMARK = SCORING.landmark
SCORE_W_CLOTHES = SCORING.clothes
SCORE_EARLY_STOP = SCORING.early_stop


class NSFWPipelineBase(ABC):
    """Template Method for NSFW pipelines.

    Orchestrates the common pipeline steps:
    1. Decode image
    2. Detect person (SE10)
    3. Detect clothes (SE10)
    4. Extract FaceID embedding
    5. Build masks (ABSTRACT — subclass implements)
    6. Build IP-Adapter reference (ABSTRACT — subclass implements)
    7. Run inpaint loop with retry + scoring
    8. Finalize (upscale, face restore, save result)
    """

    def __init__(self, job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
        self.job = job
        self.store = store
        self.se10 = SE10Client()
        self.se8 = SE8Client()

        # Common state
        self.job_id: str = job.job_id
        self.orig_img: _np.ndarray | None = None
        self.orig_h: int = 0
        self.orig_w: int = 0
        self.image_bytes: bytes = b""
        self.person_binary: _np.ndarray | None = None
        self.person_seg: dict = {}
        self.clothes_seg: dict = {}
        self.clothes_combined: _np.ndarray | None = None
        self.faceid_embedding: list[list[float]] | None = None
        self.inpaint_mask: _np.ndarray | None = None
        self.hair_mask: _np.ndarray | None = None
        self.face_mask: _np.ndarray | None = None
        self.ip_ref_img: _np.ndarray | None = None
        self.ip_ref_b64: str = ""
        self.mask_b64: str = ""
        self.image_b64: str = ""
        self.output_dir: str = ""
        self._nsfw_cfg: NSFWConfig | None = None
        self.original_skin_pct: float = 0.0

    # ─── Template Method (final) ────────────────────────────────────────────

    async def run(self) -> None:
        """Main entry point — orchestrates the pipeline."""
        try:
            self._nsfw_cfg = self.get_nsfw_config()
            await self._decode_image()
            await self._detect_person()
            await self._detect_clothes()
            await self._extract_faceid()
            await self.build_masks()
            await self.build_ip_adapter_ref()
            self._prepare_se8_inputs()
            await self._run_inpaint_loop()
            await self._finalize()
        except Exception as e:
            logger.error("Job %s nsfw failed: %s", self.job_id, e, exc_info=True)
            self.job.status = ClothesRemovalJobStatus.FAILED
            self.job.error = str(e)
            self.job.updated_at = now_brazil()
            self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
        finally:
            await self.se10.close()
            await self.se8.close()

    # ─── Common pipeline steps ──────────────────────────────────────────────

    async def _decode_image(self) -> None:
        """Decode image from job request."""
        self.image_bytes = _decode_image(self.job.request.image)
        logger.info("Job %s: image decoded (%d bytes)", self.job_id, len(self.image_bytes))

        self.orig_img = _cv2.imdecode(
            _np.frombuffer(self.image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if self.orig_img is None:
            raise ValueError("Failed to decode image")
        self.orig_h, self.orig_w = self.orig_img.shape[:2]

        self.output_dir = os.path.join(settings.output_dir, self.job_id)
        os.makedirs(self.output_dir, exist_ok=True)

        save_debug_image(self.output_dir, 0, "original", self.orig_img)

    async def _detect_person(self) -> None:
        """Detect person using SE10 with fallbacks."""
        self.job.update_stage("detecting", "processing", progress=10.0)
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))

        self.person_binary, self.person_seg, pose_cn_b64 = await detect_person_with_fallbacks(
            self.se10, self.image_bytes, self.job_id, self.orig_h, self.orig_w,
            include_pose=self.should_include_pose(),
        )
        if self.person_binary is None:
            self.job.status = ClothesRemovalJobStatus.COMPLETED
            self.job.error = "No person detected"
            self.job.progress = 100.0
            self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
            return

        self._pose_cn_b64 = pose_cn_b64
        save_debug_image(self.output_dir, 1, "person", self.person_binary)
        logger.info("Job %s: person detected (%.1f%% coverage)",
                     self.job_id, (self.person_binary > 0).sum() / self.person_binary.size * 100)

    async def _detect_clothes(self) -> None:
        """Detect clothes using SE10."""
        self.job.update_stage("detecting", "processing", progress=25.0)
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))

        self.clothes_seg = await self.se10.segment(
            image_bytes=self.image_bytes,
            filename=f"{self.job_id}_clothes.jpg",
            classes=CLOTHES_CLASSES,
            box_threshold=0.12,
            text_threshold=0.08,
            mode="clothes",
            detector="ensemble",
        )

        if self.clothes_seg.get("detected") and self.clothes_seg.get("masks"):
            self.clothes_combined = _combine_masks(
                self.clothes_seg["masks"], self.orig_h, self.orig_w)
        else:
            self.clothes_combined = None

        clothes_pct = (self.clothes_combined > 0).sum() / self.clothes_combined.size * 100 if self.clothes_combined is not None else 0.0
        logger.info("Job %s: clothes detected (%.1f%% coverage)", self.job_id, clothes_pct)

        save_detection_metadata(
            self.output_dir, self.person_seg, self.clothes_seg,
            self.person_binary, clothes_pct, self.orig_w, self.orig_h,
            faceid_embedding=self.faceid_embedding,
            base_model=self._nsfw_cfg.base_model if self._nsfw_cfg else "",
        )
        save_garment_masks(self.output_dir, self.clothes_seg, self.orig_h, self.orig_w)

    async def _extract_faceid(self) -> None:
        """Extract FaceID embedding for identity preservation."""
        self.faceid_embedding = extract_faceid_embedding(self.orig_img, self.person_binary)
        if self.faceid_embedding:
            logger.info("Job %s: FaceID embedding extracted (512-d)", self.job_id)
        else:
            logger.warning("Job %s: FaceID extraction failed, continuing without", self.job_id)

    def _prepare_se8_inputs(self) -> None:
        """Prepare base64 inputs for SE8 inpaint call."""
        _, mask_buf = _cv2.imencode(".png", self.inpaint_mask)
        self.mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")
        self.image_b64 = _to_data_uri(base64.b64encode(self.image_bytes).decode("utf-8"), mime="image/jpeg")

        if self.ip_ref_img is not None:
            _, ip_ref_buf = _cv2.imencode(".jpg", self.ip_ref_img, [_cv2.IMWRITE_JPEG_QUALITY, 90])
            self.ip_ref_b64 = _to_data_uri(base64.b64encode(ip_ref_buf).decode("utf-8"), mime="image/jpeg")

    # ─── Inpaint loop with retry + scoring ──────────────────────────────────

    async def _run_inpaint_loop(self) -> None:
        """Run the SE8 inpaint loop with retry + scoring + early stop."""
        nsfw_cfg = self._nsfw_cfg
        max_attempts = nsfw_cfg.max_attempts
        base_strength = nsfw_cfg.base_strength
        self.original_skin_pct = _detect_skin_hsv(self.orig_img)
        logger.info("Job %s: original skin_pct=%.1f%% (HSV baseline)", self.job_id, self.original_skin_pct)

        # Build OpenPose ControlNet image
        openpose_b64 = self.get_openpose_image()

        # Build prompt/negative
        prompt, negative = self.get_prompt_negative()
        nsfw_loras = nsfw_cfg.loras

        best_composited = None
        best_score = float("inf")
        best_try: str | None = None
        tries_metadata: dict[str, dict | None] = {f"try_{i}": None for i in range(1, max_attempts + 1)}
        all_attempts_meta: list[dict] = []

        self.job.update_stage("inpainting", "processing", progress=35.0)
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))

        # Detect pose once if configured
        orig_pose = None
        if not self.should_detect_pose_per_attempt():
            orig_pose = self._detect_pose_once()

        for attempt in range(1, max_attempts + 1):
            try_tag = f"try_{attempt}"
            try_dir = os.path.join(self.output_dir, try_tag)
            os.makedirs(try_dir, exist_ok=True)

            # Delay between attempts
            if attempt > 1:
                import asyncio as _asyncio
                delay = nsfw_cfg.inter_attempt_delay
                if nsfw_cfg.inter_attempt_multiplier:
                    delay *= attempt
                await _asyncio.sleep(delay)

            strength = base_strength + nsfw_cfg.strength_step * (attempt - 1)
            cfg = {"strength": strength, "field": nsfw_cfg.inpaint_respective_field, "erode": 0, "seed": -1}

            logger.info("Job %s: attempt %d/%d — strength=%.2f field=%.2f",
                        self.job_id, attempt, max_attempts, cfg["strength"], cfg["field"])

            # Build IP-Adapter prompts
            ip_adapter_prompts = self._build_ip_adapter_prompts(openpose_b64, nsfw_cfg)

            # Call SE8 inpaint
            result1 = await self.se8.inpaint(
                image_b64=self.image_b64, mask_b64=self.mask_b64,
                prompt=prompt, negative_prompt=negative,
                inpaint_additional_prompt=prompt,
                inpaint_strength=cfg["strength"],
                inpaint_respective_field=cfg["field"],
                inpaint_erode_or_dilate=cfg["erode"],
                loras=nsfw_loras,
                image_prompts=ip_adapter_prompts,
                base_model=nsfw_cfg.base_model,
                invert_mask=True,
                ip_adapter_faceid_embeds=self.faceid_embedding,
                ip_adapter_faceid_weight=nsfw_cfg.ip_adapter_faceid_weight,
                se8_params=nsfw_cfg.se8_advanced_params(),
            )

            if not result1 or not result1.get("base64"):
                logger.warning("Job %s: SE8 empty on attempt %d", self.job_id, attempt)
                tries_metadata[try_tag] = {
                    "pose_changed": True, "confidence": 0.0,
                    "head_pct": 0.0, "torso_pct": 0.0, "limbs_pct": 0.0,
                    "max_landmark_pct": 999.0, "overall_score": 999.0,
                    "params": cfg, "error": "SE8 empty",
                    "recommendation": "retry" if attempt < max_attempts else "release_anyway",
                }
                all_attempts_meta.append({
                    "attempt": attempt, "strength": strength,
                    "status": "empty", "pose_score": 999.0,
                })
                continue

            inpainted_bytes = base64.b64decode(result1["base64"])
            inpainted_img = _cv2.imdecode(
                _np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            if inpainted_img is not None and inpainted_img.shape[:2] != (self.orig_h, self.orig_w):
                inpainted_img = _cv2.resize(inpainted_img, (self.orig_w, self.orig_h))

            # Face preservation: with LustifyNSFW, face is preserved natively
            composited = inpainted_img.copy()

            # Optional face restore
            face_restore = getattr(self.job.request, "face_restore", False)
            if face_restore:
                restored = await self._do_face_restore(composited, try_dir)
                if restored is not None:
                    composited = restored

            _cv2.imwrite(os.path.join(try_dir, "result.png"), composited)
            _cv2.imwrite(os.path.join(try_dir, "inpaint_mask.png"), self.inpaint_mask)
            if self.hair_mask is not None:
                _cv2.imwrite(os.path.join(try_dir, "head_adjusted.png"), self.hair_mask)
            if self.face_mask is not None:
                _cv2.imwrite(os.path.join(try_dir, "face_mask.png"), self.face_mask)

            # Pose validation
            pose_changed, head_avg, torso_avg, limbs_avg, hands_avg, max_landmark = \
                await self._validate_pose(attempt, composited, orig_pose)

            # Result clothes detection
            result_clothes_pct = await self._detect_result_clothes(composited)

            # Skin detection
            result_skin_pct = _detect_skin_hsv(composited)
            skin_ratio = result_skin_pct / self.original_skin_pct if self.original_skin_pct > 0 else 1.0

            # Composite score
            composite_score = _compute_composite_score(
                skin_ratio=skin_ratio, head_avg=head_avg,
                clothes_pct=result_clothes_pct, max_landmark=max_landmark)

            # Build attempt metadata
            attempt_meta = {
                "attempt": attempt, "strength": float(strength), "status": "ok",
                "pose_score": float(head_avg), "pose_changed": bool(pose_changed),
                "result_clothes_pct": round(result_clothes_pct, 3),
                "result_skin_pct": round(result_skin_pct, 3),
                "skin_ratio": round(skin_ratio, 3),
                "composite_score": float(composite_score),
                "pose_changed": bool(pose_changed),
                "head_pct": round(head_avg, 3),
                "torso_pct": round(torso_avg, 3),
                "limbs_pct": round(limbs_avg, 3),
                "hands_pct": round(hands_avg, 3),
                "max_landmark_pct": round(max_landmark, 3),
            }

            # Store in both formats (production uses dict, experimental uses list)
            tries_metadata[try_tag] = attempt_meta
            all_attempts_meta.append(attempt_meta)

            # Save debug image
            save_debug_image(
                self.output_dir, 50 + attempt,
                f"try_{attempt}_s{strength:.2f}_cs{composite_score:.2f}_cl{result_clothes_pct:.1f}_{'OK' if not pose_changed else 'CHG'}",
                composited)

            logger.info("Job %s: %s composite=%.3f skin_ratio=%.2f head=%.3f landmark=%.3f clothes=%.1f",
                        self.job_id, try_tag, composite_score, skin_ratio, head_avg, max_landmark, result_clothes_pct)

            if composite_score < best_score:
                best_score = composite_score
                best_try = try_tag
                best_composited = composited.copy()

            # Early stop
            if self._should_early_stop(attempt, composite_score, pose_changed):
                break

        # Store results for finalize
        self._best_composited = best_composited
        self._best_score = best_score
        self._best_try = best_try
        self._tries_metadata = tries_metadata
        self._all_attempts_meta = all_attempts_meta

    # ─── Finalize ───────────────────────────────────────────────────────────

    async def _finalize(self) -> None:
        """Upscale, save result, and update job status."""
        if self._best_composited is None:
            logger.warning("Job %s: no valid result, marking FAILED", self.job_id)
            self.job.status = ClothesRemovalJobStatus.FAILED
            self.job.error = "All attempts failed"
            self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
            return

        composited = self._best_composited

        # Upscale
        upscale_enabled = getattr(self.job.request, "upscale", True)
        if upscale_enabled:
            upscaled = await _upscale_result(self.se8, composited, logger)
            if upscaled is not None:
                composited = upscaled
                logger.info("Job %s: upscale completed (%dx%d)", self.job_id, upscaled.shape[1], upscaled.shape[0])

        # Save result
        _, fb = _cv2.imencode(".png", composited)
        result_path = os.path.join(self.output_dir, f"{self.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        # Save attempts metadata
        self._save_attempts_metadata()

        # Copy to show/ if experimental
        self._copy_to_show(composited)

        # Update job
        self.job.result_path = result_path
        self.job.status = ClothesRemovalJobStatus.COMPLETED
        self.job.progress = 100.0
        self.job.objects_detected = 1
        self.job.update_stage("inpainting", "completed", progress=100.0)
        self.job.updated_at = now_brazil()
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
        logger.info("Job %s: completed — best=%s (score=%.3f) — %s",
                     self.job_id, self._best_try, self._best_score, result_path)

    def _save_attempts_metadata(self) -> None:
        """Save attempts metadata JSON. Override for custom format."""
        tries_clean = {k: v for k, v in self._tries_metadata.items() if v is not None}
        best_meta = tries_clean.get(self._best_try, {}) if self._best_try else {}
        attempts_summary = {
            "job_id": self.job_id,
            "scoring": "multidimensional_v2",
            "scoring_weights": {
                "skin": SCORE_W_SKIN, "head": SCORE_W_HEAD,
                "landmark": SCORE_W_LANDMARK, "clothes": SCORE_W_CLOTHES,
            },
            "original_skin_pct": float(round(self.original_skin_pct, 1)),
            "total_attempts": sum(1 for v in tries_clean.values() if v is not None),
            "best_try": self._best_try,
            "best_composite_score": self._best_score if self._best_score < float("inf") else None,
            "best_skin_ratio": float(best_meta.get("skin_ratio", 0.0)),
            "best_head_pct": float(best_meta.get("head_pct", 0.0)),
            "best_max_landmark_pct": float(best_meta.get("max_landmark_pct", 0.0)),
            "best_clothes_pct": float(best_meta.get("result_clothes_pct", 0.0)),
            "tries": tries_clean,
        }
        with open(os.path.join(self.output_dir, "attempts.json"), "w") as af:
            json.dump(attempts_summary, af, indent=2)

    def _copy_to_show(self, composited: _np.ndarray) -> None:
        """Copy result to show/ directory. Override to customize."""
        pass

    # ─── Helper methods ─────────────────────────────────────────────────────

    async def _detect_result_clothes(self, composited: _np.ndarray) -> float:
        """Detect residual clothing on inpainted result."""
        try:
            _, result_buf = _cv2.imencode(".jpg", composited, [_cv2.IMWRITE_JPEG_QUALITY, 90])
            result_bytes = result_buf.tobytes()
            result_seg = await self.se10.segment(
                image_bytes=result_bytes, filename="result.jpg",
                classes=CLOTHES_CLASSES, box_threshold=0.06, text_threshold=0.04,
                mode="clothes", detector="ensemble",
            )
            if result_seg.get("detected") and result_seg.get("masks"):
                result_mask = _combine_masks(result_seg["masks"], self.orig_h, self.orig_w)
                if result_mask is not None:
                    return float((result_mask > 0).sum() / result_mask.size * 100)
            return 0.0
        except Exception as exc:
            logger.warning("Result clothes detection failed: %s", exc)
            return 0.0

    def _build_ip_adapter_prompts(self, openpose_b64: str | None, nsfw_cfg: NSFWConfig) -> list[dict]:
        """Build IP-Adapter prompts list for SE8 call."""
        ip_adapter_prompts = [
            {
                "cn_img": self.ip_ref_b64,
                "cn_stop": nsfw_cfg.ip_image_prompt_cn_stop,
                "cn_weight": nsfw_cfg.ip_image_prompt_cn_weight,
                "cn_type": "ImagePrompt",
            },
            {"cn_img": None, "cn_stop": nsfw_cfg.ip_image_prompt_cn_stop, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
            {"cn_img": None, "cn_stop": nsfw_cfg.ip_image_prompt_cn_stop, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
        ]
        if openpose_b64:
            ip_adapter_prompts.insert(1, {
                "cn_img": openpose_b64,
                "cn_stop": nsfw_cfg.ip_openpose_cn_stop,
                "cn_weight": nsfw_cfg.ip_openpose_cn_weight,
                "cn_type": "OpenPose",
            })
        return ip_adapter_prompts

    def _detect_pose_once(self):
        """Detect pose once before inpaint loop. Returns pose result or None."""
        from app.validators.pose_detector import detect_pose
        try:
            pose = detect_pose(self.orig_img, min_detection_confidence=0.5)
            if pose:
                logger.info("Job %s: original pose detected (%d landmarks)",
                            self.job_id, len(pose.landmarks))
            else:
                logger.warning("Job %s: no pose detected", self.job_id)
            return pose
        except Exception as exc:
            logger.warning("Job %s: pose detection failed: %s", self.job_id, exc)
            return None

    async def _validate_pose(
        self,
        attempt: int,
        composited: _np.ndarray,
        orig_pose=None,
    ) -> tuple[bool, float, float, float, float, float]:
        """Validate pose between original and composited.

        Returns: (pose_changed, head_avg, torso_avg, limbs_avg, hands_avg, max_landmark)
        """
        from app.validators.pose_detector import detect_pose, compare_poses

        pose_changed = True
        head_avg = 0.0
        torso_avg = 0.0
        limbs_avg = 0.0
        hands_avg = 0.0
        max_landmark = 0.0
        nsfw_cfg = self._nsfw_cfg

        try:
            # Get original pose
            if self.should_detect_pose_per_attempt():
                orig_pose = detect_pose(self.orig_img, min_detection_confidence=0.5)

            result_pose = detect_pose(composited, min_detection_confidence=0.5)
            if orig_pose and result_pose:
                comparison = compare_poses(
                    orig_pose, result_pose, strict=False,
                    head_threshold_pct=nsfw_cfg.head_threshold_pct,
                    torso_threshold_pct=nsfw_cfg.torso_threshold_pct,
                    limbs_threshold_pct=nsfw_cfg.limbs_threshold_pct,
                    hands_threshold_pct=nsfw_cfg.hands_threshold_pct,
                )
                pose_changed = comparison.pose_changed
                head_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "HEAD"]
                torso_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "TORSO"]
                limb_diffs = [d.distance_normalized for d in comparison.diffs if d.group == "LIMB"]
                hand_diffs = [d.distance_normalized for d in comparison.diffs if d.group in ("HAND_LEFT", "HAND_RIGHT")]
                head_avg = float(_np.mean(head_diffs)) if head_diffs else 0.0
                torso_avg = float(_np.mean(torso_diffs)) if torso_diffs else 0.0
                limbs_avg = float(_np.mean(limb_diffs)) if limb_diffs else 0.0
                hands_avg = float(_np.mean(hand_diffs)) if hand_diffs else 0.0
                max_landmark = float(max(
                    (d.distance_normalized for d in comparison.diffs), default=0.0))
        except Exception as exc:
            logger.warning("Job %s: attempt %d pose validation error: %s", self.job_id, attempt, exc)

        return pose_changed, head_avg, torso_avg, limbs_avg, hands_avg, max_landmark

    async def _do_face_restore(self, composited: _np.ndarray, try_dir: str) -> _np.ndarray | None:
        """Apply face restoration via SE8. Returns restored image or None."""
        face_restore_model = getattr(self.job.request, "face_restore_model", "CodeFormer")
        face_restore_fidelity = getattr(self.job.request, "face_restore_fidelity", 0.5)
        logger.info("Job %s: calling SE8 face restore (%s, fidelity=%.2f)",
                    self.job_id, face_restore_model, face_restore_fidelity)
        restored = await _restore_face(self.se8, composited, face_restore_model, face_restore_fidelity, logger)
        if restored is not None and restored.shape[:2] == (self.orig_h, self.orig_w):
            _cv2.imwrite(os.path.join(try_dir, "result_restored.png"), restored)
            return restored
        return None

    def _should_early_stop(self, attempt: int, composite_score: float, pose_changed: bool) -> bool:
        """Determine if we should stop early based on score and pose."""
        if attempt >= 2 and composite_score < SCORE_EARLY_STOP and not pose_changed:
            logger.info("Job %s: try %d composite=%.3f < %.1f with stable pose, stopping early",
                        self.job_id, attempt, composite_score, SCORE_EARLY_STOP)
            return True
        elif composite_score < SCORE_EARLY_STOP and pose_changed:
            logger.info("Job %s: composite=%.3f but pose_changed=true, continuing",
                        self.job_id, composite_score)
        elif attempt < 2 and composite_score < SCORE_EARLY_STOP:
            logger.info("Job %s: try %d composite=%.3f < %.1f but minimum 2 tries required, continuing",
                        self.job_id, attempt, composite_score, SCORE_EARLY_STOP)
        return False

    # ─── Abstract methods (subclass MUST implement) ─────────────────────────

    @abstractmethod
    def get_nsfw_config(self) -> NSFWConfig:
        """Return the NSFW config for this pipeline."""

    @abstractmethod
    async def build_masks(self) -> None:
        """Build inpaint mask + protection masks."""

    @abstractmethod
    async def build_ip_adapter_ref(self) -> None:
        """Build IP-Adapter reference image."""

    @abstractmethod
    def get_prompt_negative(self) -> tuple[str, str]:
        """Return (prompt, negative_prompt) for SE8 call."""

    # ─── Optional overrides ─────────────────────────────────────────────────

    def should_include_pose(self) -> bool:
        """Whether to include pose from SE10 detection. Default: True."""
        return True

    def should_detect_pose_per_attempt(self) -> bool:
        """True = detect pose each attempt (production). False = once (experimental)."""
        return True

    def get_openpose_image(self) -> str | None:
        """Return OpenPose ControlNet image (b64). Default: None."""
        return None
