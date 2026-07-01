"""NSFW Experimental Pipeline V2 — Invert Mask + Low Denoise + FaceID.

COMPLETELY INDEPENDENT from pipeline.py and pipeline_nsfw.py.
All helper functions are duplicated here for isolation.

Key improvements over V1:
  - invert_mask: inpaint only clothing regions, keep face/body/background
  - Low denoising strength (0.35) preserves structure
  - IP-Adapter FaceID preserves facial identity
  - Clothes-neutral IP-Adapter ref preserves pose/body
  - OpenPose ControlNet for structural conditioning
  - Optional face restore (CodeFormer/GFPGAN)
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
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore

logger = get_logger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────

DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)

NSFW_PROMPT = (
    "NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, "
    "detailed breast anatomy, realistic nipples, areola details, "
    "natural skin pores, skin texture, skin imperfections, "
    "realistic body proportions, maintaining exact same body posture, "
    "keeping original body position, not moving, not rotating, same stance, identical pose, "
    "skin tone matching the person's arms and face, consistent skin color throughout, "
    "seamless skin transition, matching skin tone with surrounding body, "
    "photorealistic, professional studio photography, soft lighting, "
    "sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd"
)

NSFW_LORAS = [
    {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.3},
    {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
    {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
    {"enabled": True, "model_name": "None", "weight": 1.0},
]

CLOTHES_CLASSES = (
    "spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, "
    "clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, "
    "coat, hoodie, t-shirt"
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _decode_image(image_input: str) -> bytes:
    if image_input.startswith(("http://", "https://")):
        import httpx
        resp = httpx.get(image_input, timeout=30)
        resp.raise_for_status()
        return resp.content
    if "," in image_input and image_input.startswith("data:"):
        image_input = image_input.split(",", 1)[1]
    return base64.b64decode(_fix_b64_padding(image_input))


def _to_data_uri(b64_str: str, mime: str = "image/png") -> str:
    if b64_str.startswith("data:"):
        return b64_str
    return f"data:{mime};base64,{b64_str}"


def _strip_data_uri(data_uri: str) -> str:
    if "," in data_uri and data_uri.startswith("data:"):
        return data_uri.split(",", 1)[1]
    return data_uri


def _fix_b64_padding(s: str) -> str:
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


def _combine_masks(masks: list[str], orig_h: int, orig_w: int) -> _np.ndarray | None:
    """Combine multiple base64 masks into a single binary mask."""
    combined = None
    for mb in masks:
        raw = _strip_data_uri(mb)
        c_bytes = base64.b64decode(_fix_b64_padding(raw))
        cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if cm is None:
            continue
        if cm.shape[:2] != (orig_h, orig_w):
            cm = _cv2.resize(cm, (orig_w, orig_h))
        cb = (cm > 127).astype(_np.uint8) * 255
        combined = cb if combined is None else _cv2.bitwise_or(combined, cb)
    return combined


def _build_clothes_neutral_ref(
    orig_img: _np.ndarray,
    clothes_mask: _np.ndarray,
    person_binary: _np.ndarray,
) -> _np.ndarray:
    """Build a clothes-neutral reference image for IP-Adapter.

    Replaces clothing region with average skin tone + subtle noise
    so CLIP encoder sees pose/body but NOT clothing texture.
    """
    h, w = orig_img.shape[:2]
    ref = orig_img.copy()

    # Find exposed skin pixels (person minus clothes)
    exposed = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(clothes_mask))
    exposed_pixels = ref[exposed > 0]
    if len(exposed_pixels) == 0:
        return ref

    # Average skin tone in BGR
    skin_bgr = _np.mean(exposed_pixels, axis=0).astype(_np.uint8)

    # Erode clothes mask 5px to avoid edge bleeding
    erode_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    clothes_eroded = _cv2.erode(clothes_mask, erode_k, iterations=1)

    # Fill clothing region with skin tone + subtle noise
    fill_mask = clothes_eroded > 127
    noise = _np.random.randint(-8, 9, ref[fill_mask].shape, dtype=_np.int16)
    filled = _np.clip(
        ref[fill_mask].astype(_np.int16) + noise,
        0, 255
    ).astype(_np.uint8)
    ref[fill_mask] = filled

    # Blur the filled region for natural transition
    blur_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
    blurred = _cv2.GaussianBlur(ref, (15, 15), 5.0)

    # Only apply blur to clothing region
    clothes_f = clothes_mask.astype(_np.float32) / 255.0
    ref = (ref.astype(_np.float32) * (1.0 - clothes_f[:, :, None]) +
           blurred.astype(_np.float32) * clothes_f[:, :, None])
    ref = _np.clip(ref, 0, 255).astype(_np.uint8)

    return ref


# ─── Main Entry Point ────────────────────────────────────────────────────────

async def run_nsfw_experimental_v2(
    job: ClothesRemovalJob,
    store: ClothesRemovalJobStore,
) -> None:
    """NSFW Experimental V2 — Invert Mask + Low Denoise + FaceID.

    FLUXO:
    1. SE10: Person detection
    2. SE10: Clothes detection (Florence-2)
    3. InsightFace: extract face embedding for FaceID
    4. Build invert mask (clothes region = white = inpaint)
    5. Build clothes-neutral IP-Adapter ref
    6. SE8: Inpaint with invert_mask + low denoise + FaceID + neutral ref
    7. Optional face restore via SE8
    8. Save debug masks + metadata
    9. Copy result to show/
    """
    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: nsfw_test V2 started", job.job_id)

        orig_img = _cv2.imdecode(
            _np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR
        )
        if orig_img is None:
            raise ValueError("Failed to decode image")
        orig_h, orig_w = orig_img.shape[:2]

        # Output directory
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        def _save_debug(num: int, name: str, img: _np.ndarray) -> None:
            try:
                path = os.path.join(output_dir, f"{num:02d}_{name}.png")
                _cv2.imwrite(path, img)
            except Exception as exc:
                logger.warning("Job %s: debug save %s failed: %s", job.job_id, name, exc)

        # ─── Stage 1: Person Detection ───────────────────────────────────
        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        person_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man",
            box_threshold=0.20,
            text_threshold=0.15,
            mode="person",
        )

        if not person_seg.get("detected") or not person_seg.get("masks"):
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        best_idx = max(
            range(len(person_seg["objects"])),
            key=lambda i: person_seg["objects"][i].get("area_pct", 0),
        )
        raw_p = _strip_data_uri(person_seg["masks"][best_idx])
        person_mask = _cv2.imdecode(
            _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_p)), _np.uint8),
            _cv2.IMREAD_GRAYSCALE,
        )
        if person_mask is None:
            raise ValueError("Bad person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
        person_binary = (person_mask > 127).astype(_np.uint8) * 255

        # Fill internal holes
        _h, _w = person_binary.shape
        _flood = person_binary.copy()
        _flood_mask = _np.zeros((_h + 2, _w + 2), _np.uint8)
        _cv2.floodFill(_flood, _flood_mask, (0, 0), 255)
        _holes = _cv2.bitwise_not(_flood)
        person_binary = _cv2.bitwise_or(person_binary, _holes)

        _save_debug(0, "original", orig_img)
        _save_debug(1, "person", person_binary)
        logger.info("Job %s: person detected (%.1f%% coverage)",
                     job.job_id, (person_binary > 0).sum() / person_binary.size * 100)

        # ─── Stage 2: Clothes Detection (Florence-2) ────────────────────
        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes.jpg",
            classes=CLOTHES_CLASSES,
            box_threshold=0.06,
            text_threshold=0.04,
            mode="clothes",
            detector="florence2",
        )

        clothes_combined = None
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            clothes_combined = _combine_masks(clothes_seg["masks"], orig_h, orig_w)

        if clothes_combined is None:
            # Fallback: use body mask as inpaint mask
            logger.warning("Job %s: no clothes detected, using body mask fallback", job.job_id)
            clothes_combined = person_binary.copy()

        clothes_pct = (clothes_combined > 0).sum() / clothes_combined.size * 100
        _save_debug(2, "clothes_raw", clothes_combined)
        logger.info("Job %s: clothes detected (%.1f%% coverage)", job.job_id, clothes_pct)

        # ─── Stage 3: InsightFace Embedding ─────────────────────────────
        job.update_stage("detecting", "processing", progress=30.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        faceid_embedding = None
        if getattr(job.request, "use_faceid", True):
            from app.services.faceid_extractor import extract_faceid_embedding
            faceid_embedding = extract_faceid_embedding(orig_img, person_binary)
            if faceid_embedding:
                logger.info("Job %s: FaceID embedding extracted (512-d)", job.job_id)
            else:
                logger.warning("Job %s: FaceID extraction failed, continuing without", job.job_id)

        # ─── Stage 4: Build Invert Mask ─────────────────────────────────
        job.update_stage("detecting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        inpaint_mode = getattr(job.request, "inpaint_mode", "invert_mask")

        if inpaint_mode == "invert_mask":
            # inpaint_mask = clothes region (white = regenerate)
            inpaint_mask = clothes_combined.copy()

            # Expand to cover edges
            dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
            inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=1)

            # Clean up small noise
            open_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
            inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_OPEN, open_k)

            # Close small gaps
            close_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
            inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_k, iterations=2)

            # Ensure only within person
            inpaint_mask = _cv2.bitwise_and(inpaint_mask, person_binary)

        elif inpaint_mode == "clothes_mask":
            inpaint_mask = clothes_combined.copy()
            dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (21, 21))
            inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=2)

        else:
            # body_mask (legacy)
            from app.services.head_detector import detect_head_mask
            contours, _ = _cv2.findContours(person_binary, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                raise ValueError("No contours")
            largest = max(contours, key=_cv2.contourArea)
            px, py, pw, ph = _cv2.boundingRect(largest)

            head_mask = detect_head_mask(
                orig_img=orig_img,
                person_binary=person_binary,
                person_bbox=(px, py, pw, ph),
                max_head_pct=0.40,
                neck_margin_below=0.15,
                dilate_kernel_size=15,
                dilate_iterations=2,
            )
            inpaint_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))
            dilate_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (15, 15))
            inpaint_mask = _cv2.dilate(inpaint_mask, dilate_k, iterations=2)

        inpaint_pct = (inpaint_mask > 0).sum() / inpaint_mask.size * 100
        _save_debug(3, f"inpaint_mask_{inpaint_mode}", inpaint_mask)
        logger.info("Job %s: inpaint mask mode=%s coverage=%.1f%%", job.job_id, inpaint_mode, inpaint_pct)

        # ─── Stage 5: Build Clothes-Neutral IP-Adapter Ref ──────────────
        job.update_stage("inpainting", "processing", progress=40.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        ref_img = _build_clothes_neutral_ref(orig_img, clothes_combined, person_binary)
        _save_debug(4, "neutral_ref", ref_img)

        _, ref_buf = _cv2.imencode(".png", ref_img)
        ref_b64 = _to_data_uri(base64.b64encode(ref_buf).decode("utf-8"), mime="image/png")

        _, mask_buf = _cv2.imencode(".png", inpaint_mask)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        # ─── Stage 6: SE8 Inpaint (Retry Loop) ─────────────────────────
        job.update_stage("inpainting", "processing", progress=50.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        base_strength = getattr(job.request, "test_inpaint_strength", 0.35) or 0.35
        faceid_weight = getattr(job.request, "faceid_weight", 0.8) or 0.8
        base_model = getattr(job.request, "base_model", "juggernautXL_v8Rundiffusion.safetensors")
        max_attempts = 3
        best_result = None
        best_score = float("inf")

        for attempt in range(1, max_attempts + 1):
            strength = base_strength + 0.05 * (attempt - 1)
            logger.info("Job %s: SE8 attempt %d/%d — strength=%.2f field=0.55 FaceID=%s",
                        job.job_id, attempt, max_attempts, strength,
                        "on" if faceid_embedding else "off")

            image_prompts = [
                # IP-Adapter 1: Clothes-neutral ref (pose/body)
                {"cn_img": ref_b64, "cn_stop": 0.5, "cn_weight": 0.8, "cn_type": "ImagePrompt"},
            ]

            t0 = time.time()
            result = await se8.inpaint(
                image_b64=image_b64,
                mask_b64=mask_b64,
                prompt=NSFW_PROMPT,
                negative_prompt=DEFAULT_CLOTHES_NEGATIVE,
                inpaint_strength=strength,
                inpaint_respective_field=0.55,
                inpaint_erode_or_dilate=0,
                loras=NSFW_LORAS,
                image_prompts=image_prompts,
                base_model=base_model,
                invert_mask=True,
                ip_adapter_faceid_embeds=faceid_embedding,
                ip_adapter_faceid_weight=faceid_weight,
            )
            elapsed = time.time() - t0

            if not result or not result.get("base64"):
                logger.warning("Job %s: attempt %d empty (%.1fs)", job.job_id, attempt, elapsed)
                if attempt < max_attempts:
                    import asyncio
                    await asyncio.sleep(5 * attempt)
                continue

            inpainted_bytes = base64.b64decode(result["base64"])
            inpainted_img = _cv2.imdecode(
                _np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR
            )
            if inpainted_img is None:
                logger.warning("Job %s: attempt %d bad decode", job.job_id, attempt)
                continue

            if inpainted_img.shape[:2] != (orig_h, orig_w):
                inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

            # Score: how much the result deviates from original in non-masked areas
            non_mask = (inpaint_mask < 127)
            if non_mask.sum() > 0:
                diff = _np.abs(orig_img.astype(_np.float32) - inpainted_img.astype(_np.float32))
                score = float(diff[non_mask].mean())
            else:
                score = 0.0

            _save_debug(50 + attempt, f"try_{attempt}_s{strength:.2f}_sc{score:.1f}", inpainted_img)
            logger.info("Job %s: attempt %d done score=%.1f (%.1fs)", job.job_id, attempt, score, elapsed)

            if score < best_score:
                best_score = score
                best_result = inpainted_img.copy()

            if score < 2.0:
                logger.info("Job %s: score %.1f < 2.0, stopping early", job.job_id, score)
                break

        if best_result is None:
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 returned empty results after all attempts"
            job.updated_at = now_brazil()
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        # ─── Stage 7: Composite ─────────────────────────────────────────
        job.update_stage("inpainting", "processing", progress=85.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        composited = best_result.copy()

        # Optional face restore
        face_restore_enabled = getattr(job.request, "face_restore", False)
        if face_restore_enabled:
            restore_model = getattr(job.request, "face_restore_model", "CodeFormer")
            restore_fidelity = getattr(job.request, "face_restore_fidelity", 0.5)
            logger.info("Job %s: applying face restore (%s, fidelity=%.2f)",
                        job.job_id, restore_model, restore_fidelity)
            try:
                _, comp_buf = _cv2.imencode(".png", composited)
                comp_b64 = _to_data_uri(base64.b64encode(comp_buf).decode("utf-8"), mime="image/png")
                restore_result = await se8.restore_face(
                    image_b64=comp_b64,
                    model=restore_model,
                    fidelity=restore_fidelity,
                )
                if restore_result and restore_result.get("base64"):
                    restored_bytes = base64.b64decode(restore_result["base64"])
                    restored_img = _cv2.imdecode(
                        _np.frombuffer(restored_bytes, _np.uint8), _cv2.IMREAD_COLOR
                    )
                    if restored_img is not None:
                        if restored_img.shape[:2] != (orig_h, orig_w):
                            restored_img = _cv2.resize(restored_img, (orig_w, orig_h))
                        composited = restored_img
                        _save_debug(60, "face_restored", composited)
                        logger.info("Job %s: face restore done (faces=%s)",
                                    job.job_id, restore_result.get("faces_detected", "?"))
            except Exception as exc:
                logger.warning("Job %s: face restore failed: %s", job.job_id, exc)

        # ─── Stage 8: Save Results ──────────────────────────────────────
        job.update_stage("inpainting", "processing", progress=95.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        _, fb = _cv2.imencode(".png", composited)
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        # Save debug overlay
        try:
            overlay = orig_img.copy()
            ov_mask = _cv2.cvtColor(inpaint_mask, _cv2.COLOR_GRAY2BGR)
            ov_mask[:, :, 0] = 0  # zero blue
            ov_mask[:, :, 2] = 0  # zero red
            overlay = _cv2.addWeighted(overlay, 0.5, ov_mask, 0.5, 0)
            _cv2.putText(
                overlay,
                f"V2 invert_mask={inpaint_mode} str={base_strength:.2f} FaceID={'on' if faceid_embedding else 'off'}",
                (10, 30), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
            )
            _cv2.imwrite(os.path.join(output_dir, f"{job.job_id}_debug_overlay.png"), overlay)
        except Exception as exc:
            logger.warning("Job %s: overlay save failed: %s", job.job_id, exc)

        # Metadata
        meta = {
            "mode": "nsfw_test_v2",
            "inpaint_mode": inpaint_mode,
            "strength": float(base_strength),
            "faceid": faceid_embedding is not None,
            "faceid_weight": float(faceid_weight),
            "face_restore": face_restore_enabled,
            "attempts": attempt,
            "best_score": float(best_score),
            "person_coverage": float(round((person_binary > 0).sum() / person_binary.size * 100, 1)),
            "clothes_coverage": float(round(clothes_pct, 1)),
            "inpaint_coverage": float(round(inpaint_pct, 1)),
        }
        with open(os.path.join(output_dir, "v2_meta.json"), "w") as ef:
            json.dump(meta, ef, indent=2)

        # Copy to show/
        try:
            show_dir = "/root/YTCaption-Easy-Youtube-API/show"
            os.makedirs(show_dir, exist_ok=True)
            _cv2.imwrite(os.path.join(show_dir, f"v2_{job.job_id}_result.png"), composited)
            logger.info("Job %s: result copied to show/", job.job_id)
        except Exception as exc:
            logger.warning("Job %s: show/ copy failed: %s", job.job_id, exc)

        # ─── Done ───────────────────────────────────────────────────────
        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = 1
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: nsfw_test V2 completed — %s (score=%.1f, attempts=%d)",
                     job.job_id, result_path, best_score, attempt)

    except Exception as e:
        logger.error("Job %s nsfw_test V2 failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
