"""NSFW Experimental Pipeline — debug, single-pass, no retry.

This is a COMPLETELY INDEPENDENT file. Zero imports from pipeline.py.
All helper functions are duplicated here for isolation.
For testing/debugging only — does NOT affect production.
"""
from __future__ import annotations

import base64
import json
import os

from common.log_utils import get_logger
from common.datetime_utils import now_brazil

from app.core.config import settings
from app.core.models import ClothesRemovalJob, ClothesRemovalJobStatus
from app.infrastructure.http_client import SE10Client, SE8Client
from app.infrastructure.redis_store import ClothesRemovalJobStore
from app.services.head_detector import detect_head_mask

logger = get_logger(__name__)

# ─── Constants (PRIVATE — only this file) ───────────────────────────────────

DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)

# ─── Helpers (COPIED — zero sharing with pipeline.py) ───────────────────────

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


# ─── Main Entry Point ────────────────────────────────────────────────────────

async def run_nsfw_experimental(job: ClothesRemovalJob, store: ClothesRemovalJobStore) -> None:
    """EXPERIMENTAL NSFW pipeline — single pass, debug masks, no retry.

    Uses body_mask (person minus head) instead of clothing mask for larger inpaint area.
    Single SE8 call — no retry loop, no pose validation.
    Saves detailed debug masks for analysis.
    """
    import cv2 as _cv2
    import numpy as _np

    se10 = SE10Client()
    se8 = SE8Client()

    try:
        image_bytes = _decode_image(job.request.image)
        logger.info("Job %s: nsfw experimental started", job.job_id)

        orig_img = _cv2.imdecode(_np.frombuffer(image_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if orig_img is None:
            raise ValueError("Failed to decode")
        orig_h, orig_w = orig_img.shape[:2]

        job.update_stage("detecting", "processing", progress=10.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── Stage 1: SE10 Person Detection ───
        person_seg = await se10.segment(
            image_bytes=image_bytes, filename=f"{job.job_id}_person.jpg",
            classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person",
        )
        if not person_seg.get("detected") or not person_seg.get("masks"):
            job.status = ClothesRemovalJobStatus.COMPLETED
            job.error = "No person detected"
            job.progress = 100.0
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        best_idx = max(range(len(person_seg["objects"])), key=lambda i: person_seg["objects"][i].get("area_pct", 0))
        raw_p = _strip_data_uri(person_seg["masks"][best_idx])
        person_mask = _cv2.imdecode(
            _np.frombuffer(base64.b64decode(_fix_b64_padding(raw_p)), _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if person_mask is None:
            raise ValueError("Bad person mask")
        if person_mask.shape[:2] != (orig_h, orig_w):
            person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
        person_binary = (person_mask > 127).astype(_np.uint8) * 255

        # Fill ALL internal holes in the person mask
        _h, _w = person_binary.shape
        _flood = person_binary.copy()
        _flood_mask = _np.zeros((_h + 2, _w + 2), _np.uint8)
        _cv2.floodFill(_flood, _flood_mask, (0, 0), 255)
        _holes = _cv2.bitwise_not(_flood)
        person_binary = _cv2.bitwise_or(person_binary, _holes)

        job.update_stage("detecting", "processing", progress=25.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── Stage 2: Head/Body Separation ───
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
            neck_margin_below=0.4,
            dilate_kernel_size=25,
            dilate_iterations=3,
        )

        body_mask = _cv2.bitwise_and(person_binary, _cv2.bitwise_not(head_mask))

        # ─── Stage 3: SE10 Clothes Detection ───
        clothes_seg = await se10.segment(
            image_bytes=image_bytes,
            filename=f"{job.job_id}_clothes_ref.jpg",
            classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
            box_threshold=0.06, text_threshold=0.04,
            mode="clothes", detector="florence2",
        )

        clothes_combined = None
        if clothes_seg.get("detected") and clothes_seg.get("masks"):
            for mb in clothes_seg.get("masks", []):
                raw_c = _strip_data_uri(mb)
                c_bytes = base64.b64decode(_fix_b64_padding(raw_c))
                cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
                if cm is not None:
                    if cm.shape[:2] != (orig_h, orig_w):
                        cm = _cv2.resize(cm, (orig_w, orig_h))
                    cb = (cm > 127).astype(_np.uint8) * 255
                    clothes_combined = cb if clothes_combined is None else _cv2.bitwise_or(clothes_combined, cb)

        if clothes_combined is not None:
            exposed_skin = _cv2.bitwise_and(body_mask, _cv2.bitwise_not(clothes_combined))
        else:
            exposed_skin = body_mask

        # ─── Stage 4: Mask Preparation ───
        body_closed = body_mask.copy()

        contours_c, _ = _cv2.findContours(body_closed, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if contours_c:
            all_pts = _np.vstack(contours_c)
            _, _, cw, ch = _cv2.boundingRect(all_pts)
            dilation_px = max(3, int(min(cw, ch) * 0.035))
        else:
            dilation_px = 4
        expand_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (dilation_px, dilation_px))
        body_expanded = _cv2.dilate(body_closed, expand_kernel, iterations=2)
        open_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (3, 3))
        body_expanded = _cv2.morphologyEx(body_expanded, _cv2.MORPH_OPEN, open_kernel)
        body_expanded = (body_expanded > 127).astype(_np.uint8) * 255
        inpaint_mask = body_expanded

        close_k = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
        inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, close_k, iterations=2)
        v_close_k = _cv2.getStructuringElement(_cv2.MORPH_RECT, (1, 7))
        inpaint_mask = _cv2.morphologyEx(inpaint_mask, _cv2.MORPH_CLOSE, v_close_k)

        head_closed = head_mask.copy()
        hk = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
        head_closed = _cv2.morphologyEx(head_mask, _cv2.MORPH_CLOSE, hk, iterations=3)
        hf_mask = _np.zeros((head_closed.shape[0] + 2, head_closed.shape[1] + 2), _np.uint8)
        hcts, _ = _cv2.findContours(head_closed, _cv2.RETR_EXTERNAL, _cv2.CHAIN_APPROX_SIMPLE)
        if hcts:
            hM = _cv2.moments(max(hcts, key=_cv2.contourArea))
            if hM["m00"] > 0:
                hcx, hcy = int(hM["m10"] / hM["m00"]), int(hM["m01"] / hM["m00"])
                hfill = head_closed.copy()
                _cv2.floodFill(hfill, hf_mask, (hcx, hcy), 255)
                head_mask = _cv2.bitwise_or(head_closed, hfill)

        inpaint_mask = body_expanded
        head_adjusted = _cv2.bitwise_and(head_mask, _cv2.bitwise_not(inpaint_mask))

        clothes_pct = (body_closed > 0).sum() / body_closed.size * 100
        head_orig_pct = _cv2.countNonZero(head_mask) / head_mask.size * 100
        head_adj_pct = _cv2.countNonZero(head_adjusted) / head_adjusted.size * 100
        logger.info("Job %s: nsfw_exp body=%.1f%% head_orig=%.1f%% head_adj=%.1f%%",
                     job.job_id, clothes_pct, head_orig_pct, head_adj_pct)

        job.update_stage("inpainting", "processing", progress=35.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        _, mask_buf = _cv2.imencode(".png", inpaint_mask)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode("utf-8"), mime="image/png")

        nsfw_loras = [
            {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.3},
            {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
            {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
            {"enabled": True, "model_name": "None", "weight": 1.0},
        ]

        image_b64 = _to_data_uri(base64.b64encode(image_bytes).decode("utf-8"), mime="image/jpeg")

        nsfw_prompt = (
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

        # ─── Single SE8 Inpaint (NO retry, NO pose validation) ───
        logger.info("Job %s: nsfw_exp calling SE8 — strength=0.65 field=0.85", job.job_id)

        result1 = await se8.inpaint(
            image_b64=image_b64, mask_b64=mask_b64,
            prompt=nsfw_prompt,
            negative_prompt=DEFAULT_CLOTHES_NEGATIVE,
            inpaint_strength=0.65, inpaint_respective_field=0.85,
            inpaint_erode_or_dilate=-3, loras=nsfw_loras,
            base_model="juggernautXL_v8Rundiffusion.safetensors",
        )
        if not result1 or not result1.get("base64"):
            job.status = ClothesRemovalJobStatus.FAILED
            job.error = "SE8 empty"
            store.save_job(job.job_id, job.model_dump(mode="json"))
            return

        inpainted_bytes = base64.b64decode(result1["base64"])
        inpainted_img = _cv2.imdecode(
            _np.frombuffer(inpainted_bytes, _np.uint8), _cv2.IMREAD_COLOR)
        if inpainted_img is not None and inpainted_img.shape[:2] != (orig_h, orig_w):
            inpainted_img = _cv2.resize(inpainted_img, (orig_w, orig_h))

        job.update_stage("inpainting", "processing", progress=75.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        inpainted_img[head_adjusted > 0] = orig_img[head_adjusted > 0]

        composited = orig_img.copy()
        body_bin = inpaint_mask > 0
        composited[body_bin] = inpainted_img[body_bin]
        composited[head_adjusted > 0] = orig_img[head_adjusted > 0]

        body_float = inpaint_mask.astype(_np.float32) / 255.0
        body_smooth = _cv2.GaussianBlur(body_float, (7, 7), 0)
        composited = (composited.astype(_np.float32) * body_smooth[:, :, None] +
                      orig_img.astype(_np.float32) * (1.0 - body_smooth[:, :, None]))
        composited = _np.clip(composited, 0, 255).astype(_np.uint8)
        composited[head_adjusted > 0] = orig_img[head_adjusted > 0]
        logger.info("Job %s: nsfw_exp composite applied", job.job_id)

        job.update_stage("inpainting", "processing", progress=90.0)
        store.save_job(job.job_id, job.model_dump(mode="json"))

        # ─── Save debug masks (detailed for experimental) ───
        output_dir = os.path.join(settings.output_dir, job.job_id)
        os.makedirs(output_dir, exist_ok=True)

        try:
            def _save_mask(num: int, name: str, mask) -> None:
                tag = f"{num:02d}_{name}"
                _cv2.imwrite(os.path.join(output_dir, f"{tag}.png"), mask)

            _save_mask(0, "original", orig_img)
            _save_mask(1, "person", person_binary)
            _save_mask(2, "head_updated", head_adjusted)
            _save_mask(3, "body_mask", body_mask)
            _save_mask(4, "inpaint_mask", inpaint_mask)
            _save_mask(5, "result", composited)

            # Additional debug masks for experimental
            if clothes_combined is not None:
                _save_mask(6, "clothes", clothes_combined)
            _save_mask(7, "exposed_skin", exposed_skin)

            overlay = orig_img.copy()
            h_ov = overlay.copy(); h_ov[head_adjusted > 0] = [0, 0, 255]
            overlay = _cv2.addWeighted(overlay, 0.4, h_ov, 0.6, 0)
            b_ov = overlay.copy(); b_ov[body_bin] = [255, 0, 255]
            overlay = _cv2.addWeighted(overlay, 0.4, b_ov, 0.6, 0)
            i_ov = overlay.copy(); i_ov[inpaint_mask > 0] = [0, 255, 255]
            overlay = _cv2.addWeighted(overlay, 0.4, i_ov, 0.6, 0)

            head_diff = _cv2.bitwise_and(head_mask, _cv2.bitwise_not(head_adjusted))
            d_ov = overlay.copy(); d_ov[head_diff > 0] = [255, 255, 255]
            overlay = _cv2.addWeighted(overlay, 0.6, d_ov, 0.4, 0)

            _cv2.putText(overlay, "EXPERIMENTAL — RED=head MAGENTA=expanded YELLOW=inpaint",
                         (10, 30), _cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            _cv2.imwrite(os.path.join(output_dir, f"{job.job_id}_mask_overlay.png"), overlay)
        except Exception as e:
            import traceback
            logger.warning("Job %s: debug failed (%s)\n%s", job.job_id, e, traceback.format_exc())

        result_path = os.path.join(output_dir, f"{job.job_id}_result.png")
        _, fb = _cv2.imencode(".png", composited)
        with open(result_path, "wb") as f:
            f.write(fb.tobytes())

        # Save metadata for experimental run
        meta = {
            "mode": "experimental",
            "pose_validation": False,
            "retry_enabled": False,
            "params": {"strength": 0.65, "field": 0.85, "erode": -3, "seed": -1},
            "result_path": f"{job.job_id}_result.png",
        }
        with open(os.path.join(output_dir, "experimental_meta.json"), "w") as ef:
            json.dump(meta, ef, indent=2)

        job.result_path = result_path
        job.status = ClothesRemovalJobStatus.COMPLETED
        job.progress = 100.0
        job.objects_detected = 1
        job.update_stage("inpainting", "completed", progress=100.0)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))
        logger.info("Job %s: nsfw experimental completed — %s", job.job_id, result_path)

    except Exception as e:
        logger.error("Job %s nsfw experimental failed: %s", job.job_id, e, exc_info=True)
        job.status = ClothesRemovalJobStatus.FAILED
        job.error = str(e)
        job.updated_at = now_brazil()
        store.save_job(job.job_id, job.model_dump(mode="json"))

    finally:
        await se10.close()
        await se8.close()
