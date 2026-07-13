"""Multi-Person Pipeline — process multiple persons sequentially.

When the image contains more than one person, this pipeline:
1. Detects ALL persons via SE10
2. For each person, runs the full single-person pipeline (masks, inpainting, scoring)
3. Composites all results into a single output image

Uses the existing NSFWProductionPipeline per-person, with the person's
binary mask as the starting point.
"""
from __future__ import annotations

import base64
import json
import os
from typing import TYPE_CHECKING

import cv2 as _cv2
import numpy as _np

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.services.person_data import PersonData, create_persons_from_se10
from app.services.detection_fallbacks import detect_all_persons
from app.services.head_detector import (
    detect_head_mask, detect_face_only, detect_face_oval_mask,
    detect_faces_all, match_faces_to_persons,
)
from app.services.faceid_extractor import extract_faceid_embedding, extract_all_faceid_embeddings
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
)
from app.services.ip_adapter_utils import build_clothes_neutral_ref
from app.services.debug_utils import (
    save_debug_image, build_debug_grid, save_mask_overlay,
    save_detection_metadata, save_garment_masks,
)

if TYPE_CHECKING:
    from app.services.config_loader import NSFWConfig

logger = get_logger(__name__)


class MultiPersonPipeline:
    """Pipeline for processing images with multiple persons.

    For each detected person, runs a full single-person pipeline
    (masks → inpaint → score → select best), then composites all
    person results into the original image.
    """

    def __init__(self, job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
        self.job = job
        self.store = store
        self.job_id: str = job.job_id
        self.output_dir: str = ""

        # Image state
        self.orig_img: _np.ndarray | None = None
        self.orig_h: int = 0
        self.orig_w: int = 0
        self.image_bytes: bytes = b""

        # Multi-person state
        self.persons: list[PersonData] = []
        self.person_seg: dict = {}
        self.clothes_seg: dict = {}

        # Results per person
        self._person_results: dict[int, _np.ndarray] = {}  # person_id → result image
        self._person_scores: dict[int, float] = {}
        self._person_metadata: dict[int, dict] = {}

        # Final composited result
        self._final_composited: _np.ndarray | None = None

    async def run(self) -> None:
        """Main entry point — orchestrates the multi-person pipeline."""
        se10 = SE10Client()
        se8 = SE8Client()
        try:
            self._nsfw_cfg = get_nsfw_config("production")
            await self._decode_image()
            await self._detect_all_persons(se10)
            await self._detect_clothes(se10)
            await self._match_faces_and_poses()

            if len(self.persons) == 0:
                self.job.status = ClothesRemovalJobStatus.COMPLETED
                self.job.error = "No person detected"
                self.job.progress = 100.0
                self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
                return
            elif len(self.persons) == 1:
                logger.info("Job %s: single person detected, using standard pipeline", self.job_id)
                await self._process_single_person(se10, se8)
            else:
                logger.info("Job %s: %d persons detected, using multi-person pipeline",
                            self.job_id, len(self.persons))
                await self._process_all_persons(se10, se8)
                await self._composite_results()

            await self._finalize(se8)
        except Exception as e:
            logger.error("Job %s multi-person failed: %s", self.job_id, e, exc_info=True)
            self.job.status = ClothesRemovalJobStatus.FAILED
            self.job.error = str(e)
            self.job.updated_at = now_brazil()
            self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
        finally:
            await se10.close()
            await se8.close()

    # ─── Pipeline steps ──────────────────────────────────────────────────

    async def _decode_image(self) -> None:
        """Decode image from job request."""
        self.image_bytes = _decode_image(self.job.request.image)
        self.orig_img = _cv2.imdecode(
            _np.frombuffer(self.image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if self.orig_img is None:
            raise ValueError("Failed to decode image")
        self.orig_h, self.orig_w = self.orig_img.shape[:2]
        self.output_dir = os.path.join(settings.output_dir, self.job_id)
        os.makedirs(self.output_dir, exist_ok=True)
        save_debug_image(self.output_dir, 0, "original", self.orig_img)
        logger.info("Job %s: image decoded (%dx%d, %d bytes)",
                     self.job_id, self.orig_w, self.orig_h, len(self.image_bytes))

    async def _detect_all_persons(self, se10: SE10Client) -> None:
        """Detect ALL persons in the image."""
        self.job.update_stage("detecting", "processing", progress=10.0)
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))

        self.persons, self.person_seg, self._pose_cn_b64 = await detect_all_persons(
            se10, self.image_bytes, self.job_id, self.orig_h, self.orig_w,
            min_area_pct=5.0, include_pose=True,
        )

        logger.info("Job %s: detected %d person(s)", self.job_id, len(self.persons))
        for p in self.persons:
            save_debug_image(self.output_dir, 10 + p.person_id,
                             f"person_{p.person_id}", p.binary_mask)

    async def _detect_clothes(self, se10: SE10Client) -> None:
        """Detect clothes for the whole image."""
        self.job.update_stage("detecting", "processing", progress=20.0)
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))

        self.clothes_seg = await se10.segment(
            image_bytes=self.image_bytes,
            filename=f"{self.job_id}_clothes.jpg",
            classes=CLOTHES_CLASSES,
            box_threshold=0.12, text_threshold=0.08,
            mode="clothes", detector="ensemble",
        )

        # Assign clothes masks to persons by spatial overlap
        if self.clothes_seg.get("detected") and self.clothes_seg.get("masks"):
            for person in self.persons:
                person_clothes = _np.zeros((self.orig_h, self.orig_w), dtype=_np.uint8)
                for mb in self.clothes_seg["masks"]:
                    raw_c = _strip_data_uri(mb)
                    c_bytes = base64.b64decode(_fix_b64_padding(raw_c))
                    cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                    if cm is None:
                        continue
                    if cm.shape[:2] != (self.orig_h, self.orig_w):
                        cm = _cv2.resize(cm, (self.orig_w, self.orig_h))
                    cb = (cm > 127).astype(_np.uint8) * 255
                    # Check overlap with person mask
                    overlap = _cv2.bitwise_and(cb, person.binary_mask)
                    if _cv2.countNonZero(overlap) > 0:
                        person_clothes = _cv2.bitwise_or(person_clothes, cb)
                person.clothes_mask = person_clothes

        logger.info("Job %s: clothes detected and assigned to persons", self.job_id)

    async def _match_faces_and_poses(self) -> None:
        """Match faces and poses to each person."""
        # Detect all faces
        faces = detect_faces_all(self.orig_img, max_num_faces=10)

        if faces:
            face_match = match_faces_to_persons(faces, self.persons)
            for person in self.persons:
                if person.person_id in face_match:
                    fi = face_match[person.person_id]
                    fx, fy, fw, fh = faces[fi]
                    person.face_bbox = (fx, fy, fw, fh)

                    # Create face mask for this person
                    face_mask = _np.zeros((self.orig_h, self.orig_w), dtype=_np.uint8)
                    # Expand face bbox slightly
                    margin = int(max(fw, fh) * 0.2)
                    x1 = max(0, fx - margin)
                    y1 = max(0, fy - margin)
                    x2 = min(self.orig_w, fx + fw + margin)
                    y2 = min(self.orig_h, fy + fh + margin)
                    face_mask[y1:y2, x1:x2] = 255
                    face_mask = _cv2.bitwise_and(face_mask, person.binary_mask)
                    person.face_mask = face_mask

        # Extract FaceID embeddings for all persons
        if self.persons:
            all_embeddings = extract_all_faceid_embeddings(self.orig_img, self.persons)
            for person in self.persons:
                if person.person_id in all_embeddings:
                    person.faceid_embedding = all_embeddings[person.person_id]

        logger.info("Job %s: faces matched to %d/%d persons",
                     self.job_id,
                     sum(1 for p in self.persons if p.face_mask is not None),
                     len(self.persons))

    async def _process_single_person(self, se10: SE10Client, se8: SE8Client) -> None:
        """Process a single person using the standard production pipeline."""
        from app.services.pipeline_nsfw import NSFWProductionPipeline

        # Create a single-person job with the detected person
        pipeline = NSFWProductionPipeline(self.job, self.store)
        # Override the person detection to use our already-detected person
        pipeline.person_binary = self.persons[0].binary_mask
        pipeline.person_seg = self.person_seg
        pipeline.faceid_embedding = self.persons[0].faceid_embedding
        pipeline.orig_img = self.orig_img
        pipeline.orig_h = self.orig_h
        pipeline.orig_w = self.orig_w
        pipeline.image_bytes = self.image_bytes
        pipeline.output_dir = self.output_dir
        pipeline._nsfw_cfg = self._nsfw_cfg
        pipeline._pose_cn_b64 = getattr(self, "_pose_cn_b64", None)

        await pipeline._detect_clothes()
        await pipeline.build_masks()
        await pipeline.build_ip_adapter_ref()
        pipeline._prepare_se8_inputs()
        await pipeline._run_inpaint_loop()
        await pipeline._finalize()

        # Copy result
        if pipeline._best_composited is not None:
            self._final_composited = pipeline._best_composited

    async def _process_all_persons(self, se10: SE10Client, se8: SE8Client) -> None:
        """Process each person individually using the production pipeline."""
        from app.services.pipeline_nsfw import NSFWProductionPipeline

        for person in self.persons:
            logger.info("Job %s: processing person %d (%.1f%% area, bbox=%s)",
                        self.job_id, person.person_id, person.area_pct, person.bbox)

            try:
                # Create a pipeline instance for this person
                pipeline = NSFWProductionPipeline(self.job, self.store)
                pipeline.person_binary = person.binary_mask
                pipeline.person_seg = self.person_seg
                pipeline.faceid_embedding = person.faceid_embedding
                pipeline.orig_img = self.orig_img
                pipeline.orig_h = self.orig_h
                pipeline.orig_w = self.orig_w
                pipeline.image_bytes = self.image_bytes
                pipeline.output_dir = os.path.join(self.output_dir, f"person_{person.person_id}")
                os.makedirs(pipeline.output_dir, exist_ok=True)
                pipeline._nsfw_cfg = self._nsfw_cfg
                pipeline._pose_cn_b64 = getattr(self, "_pose_cn_b64", None)

                # Run pipeline for this person
                await pipeline._detect_clothes()
                await pipeline.build_masks()
                await pipeline.build_ip_adapter_ref()
                pipeline._prepare_se8_inputs()
                await pipeline._run_inpaint_loop()

                if pipeline._best_composited is not None:
                    self._person_results[person.person_id] = pipeline._best_composited
                    self._person_scores[person.person_id] = pipeline._best_score
                    self._person_metadata[person.person_id] = {
                        "best_try": pipeline._best_try,
                        "best_score": pipeline._best_score,
                        "area_pct": person.area_pct,
                    }
                    save_debug_image(
                        self.output_dir, 80 + person.person_id,
                        f"person_{person.person_id}_result",
                        pipeline._best_composited)
                else:
                    logger.warning("Job %s: person %d pipeline produced no result",
                                   self.job_id, person.person_id)
            except Exception as exc:
                logger.error("Job %s: person %d failed: %s",
                             self.job_id, person.person_id, exc, exc_info=True)

    async def _composite_results(self) -> None:
        """Composite all person results into the original image."""
        if not self._person_results:
            logger.warning("Job %s: no person results to composite", self.job_id)
            return

        composited = self.orig_img.copy()

        # Sort by area descending (largest person first)
        sorted_persons = sorted(
            self._person_results.items(),
            key=lambda kv: self._person_metadata.get(kv[0], {}).get("area_pct", 0),
            reverse=True,
        )

        for person_id, result_img in sorted_persons:
            person = next((p for p in self.persons if p.person_id == person_id), None)
            if person is None:
                continue

            # Use the person's binary mask to blend the result
            mask_3ch = _cv2.cvtColor(person.binary_mask, _cv2.COLOR_GRAY2BGR)
            mask_float = mask_3ch.astype(_np.float32) / 255.0

            # Feather the mask edges for smooth blending
            feather_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
            mask_float = _cv2.GaussianBlur(mask_float, (21, 21), 0)

            # Blend: where mask is 1, use result; where 0, use original
            composited = (result_img * mask_float + composited * (1.0 - mask_float)).astype(_np.uint8)

        self._final_composited = composited
        save_debug_image(self.output_dir, 90, "composited_multi", composited)

    async def _finalize(self, se8: SE8Client) -> None:
        """Save result and update job status."""
        if self._final_composited is None:
            logger.warning("Job %s: no valid result, marking FAILED", self.job_id)
            self.job.status = ClothesRemovalJobStatus.FAILED
            self.job.error = "All attempts failed"
            self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
            return

        composited = self._final_composited

        # Upscale
        upscale_enabled = getattr(self.job.request, "upscale", True)
        if upscale_enabled:
            upscaled = await _upscale_result(se8, composited, logger)
            if upscaled is not None:
                composited = upscaled

        # Save result
        _, fb = _cv2.imencode(".png", composited)
        result_path = os.path.join(self.output_dir, f"{self.job_id}_result.png")
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        # Save metadata
        self._save_metadata()

        # Update job
        self.job.result_path = result_path
        self.job.status = ClothesRemovalJobStatus.COMPLETED
        self.job.progress = 100.0
        self.job.objects_detected = len(self.persons)
        self.job.update_stage("inpainting", "completed", progress=100.0)
        self.job.updated_at = now_brazil()
        self.store.save_job(self.job_id, self.job.model_dump(mode="json"))
        logger.info("Job %s: multi-person completed — %d persons processed — %s",
                     self.job_id, len(self._person_results), result_path)

    def _save_metadata(self) -> None:
        """Save multi-person processing metadata."""
        meta = {
            "mode": "multi_person",
            "persons_detected": len(self.persons),
            "persons_processed": len(self._person_results),
            "persons": [
                {
                    "person_id": pid,
                    "area_pct": round(self._person_metadata.get(pid, {}).get("area_pct", 0), 1),
                    "best_score": round(self._person_scores.get(pid, 999.0), 3),
                    "best_try": self._person_metadata.get(pid, {}).get("best_try", ""),
                }
                for pid in self._person_results
            ],
        }
        with open(os.path.join(self.output_dir, "multi_person_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)


async def run_multi_person(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """Entry point for multi-person pipeline."""
    pipeline = MultiPersonPipeline(job, store)
    await pipeline.run()
