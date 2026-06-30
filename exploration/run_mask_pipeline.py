#!/usr/bin/env python3
"""Research script — generate and save ALL mask regions from SE11 pipeline.

NO inpainting. NO SE8 calls. Just masks + debug grid.
For visual inspection and parameter tuning.

Usage:
    python3 exploration/run_mask_pipeline.py
    python3 exploration/run_mask_pipeline.py --image exploration/OK.jpg
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import time
from pathlib import Path

import cv2
import numpy as np

# ─── Config ───────────────────────────────────────────────────────────────────

SE10_URL = os.getenv("SE10_URL", "http://localhost:8010")
SE10_KEY = os.getenv("SE10_API_KEY", "se10-test-key-2026")
SE8_URL = os.getenv("SE8_URL", "http://localhost:8008")
SE8_KEY = os.getenv("SE8_API_KEY", "se8-test-key-2026")

# ─── Helpers ──────────────────────────────────────────────────────────────────

def fix_b64(s: str) -> str:
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s

def strip_data_uri(uri: str) -> str:
    if "," in uri and uri.startswith("data:"):
        return uri.split(",", 1)[1]
    return uri

def save_mask(path: Path, mask: np.ndarray):
    cv2.imwrite(str(path), mask)

def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def _to_data_uri(b64_str: str, mime: str = "image/png") -> str:
    if b64_str.startswith("data:"):
        return b64_str
    return f"data:{mime};base64,{b64_str}"

# ─── SE10 API ────────────────────────────────────────────────────────────────

async def se10_segment(image_bytes: bytes, filename: str, classes: str,
                       box_threshold: float, text_threshold: float,
                       mode: str, detector: str = "groundingdino") -> dict:
    import httpx
    async with httpx.AsyncClient(base_url=SE10_URL, headers={"X-API-Key": SE10_KEY}, timeout=60) as client:
        resp = await client.post(
            "/v1/segment",
            files={"file": (filename, image_bytes, "image/jpeg")},
            data={
                "classes": classes,
                "box_threshold": str(box_threshold),
                "text_threshold": str(text_threshold),
                "mode": mode,
                "detector": detector,
            },
        )
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise Exception(f"SE10 failed: {result.get('message')}")
        return result.get("result", {})

def decode_mask(mask_b64_uri: str, target_h: int, target_w: int) -> np.ndarray:
    raw = strip_data_uri(mask_b64_uri)
    raw = fix_b64(raw)
    mask_bytes = base64.b64decode(raw)
    mask = cv2.imdecode(np.frombuffer(mask_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if mask is None:
        raise ValueError("Failed to decode mask")
    if mask.shape[:2] != (target_h, target_w):
        mask = cv2.resize(mask, (target_w, target_h))
    return (mask > 127).astype(np.uint8) * 255

async def _se8_inpaint(image_b64, mask_b64, prompt, negative, strength, field, ip_prompts):
    import httpx
    loras = [
        {"enabled": True, "model_name": "NsfwPovAllInOneLoraSdxl-000009.safetensors", "weight": 0.6},
        {"enabled": True, "model_name": "sd_xl_offset_example-lora_1.0.safetensors", "weight": 0.1},
        {"enabled": True, "model_name": "add-detail-xl.safetensors", "weight": 0.7},
        {"enabled": True, "model_name": "None", "weight": 1.0},
        {"enabled": True, "model_name": "None", "weight": 1.0},
    ]
    payload = {
        "prompt": prompt, "negative_prompt": negative,
        "style_selections": [], "performance_selection": "Quality",
        "aspect_ratios_selection": "1024*1024", "image_number": 1,
        "image_seed": -1, "sharpness": 2.0, "guidance_scale": 7.0,
        "base_model_name": "juggernautXL_v8Rundiffusion.safetensors",
        "loras": loras,
        "input_image": image_b64, "input_mask": mask_b64,
        "inpaint_additional_prompt": prompt,
        "async_process": False, "require_base64": False,
        "advanced_params": {
            "inpaint_engine": "v2.6", "inpaint_strength": strength,
            "inpaint_respective_field": field,
            "inpaint_disable_initial_latent": False,
            "inpaint_erode_or_dilate": 0, "overwrite_step": 40,
            "overwrite_switch": 1.0, "adaptive_cfg": 7.0,
            "sampler_name": "dpmpp_2m_sde_gpu", "scheduler_name": "karras",
        },
        "image_prompts": ip_prompts,
    }
    async with httpx.AsyncClient(base_url=SE8_URL, headers={"X-API-Key": SE8_KEY}, timeout=300) as client:
        for attempt in range(3):
            resp = await client.post("/v1/generation/image-inpaint-outpaint", json=payload)
            resp.raise_for_status()
            result = resp.json()
            item = result
            while isinstance(item, list) and len(item) > 0:
                item = item[0]
            if isinstance(item, dict) and item.get("finish_reason") == "SUCCESS":
                _extract_se8(item); return item
            if isinstance(item, list) and len(item) == 0:
                await asyncio.sleep(5 * (attempt + 1)); continue
            if isinstance(item, dict):
                _extract_se8(item); return item
    raise Exception("SE8 failed after 3 attempts")

def _extract_se8(item):
    if item.get("base64"):
        return
    url_val = item.get("url", "")
    if not url_val:
        return
    if not url_val.startswith("data:"):
        import httpx as _httpx
        file_url = url_val if url_val.startswith("http") else f"{SE8_URL}{url_val}"
        try:
            dl = _httpx.get(file_url, timeout=30, headers={"X-API-Key": SE8_KEY})
            dl.raise_for_status()
            item["base64"] = base64.b64encode(dl.content).decode("utf-8")
        except Exception:
            pass
    else:
        data_idx = url_val.find("data:image")
        if data_idx >= 0:
            comma_idx = url_val.find(",", data_idx)
            if comma_idx >= 0:
                b64 = url_val[comma_idx + 1:].rstrip("=")
                missing = len(b64) % 4
                if missing:
                    b64 += "=" * (4 - missing)
                item["base64"] = b64

# ─── Face Detection ───────────────────────────────────────────────────────────

def _get_cascade():
    if not hasattr(_get_cascade, "_c"):
        _get_cascade._c = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    return _get_cascade._c

def detect_faces(orig_img) -> list:
    c = _get_cascade()
    if c is None or orig_img is None:
        return []
    try:
        gray = cv2.cvtColor(orig_img, cv2.COLOR_BGR2GRAY)
        faces = c.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
        return list(faces) if len(faces) > 0 else []
    except Exception:
        return []

def _ellipse_from_face(fx, fy, fw, fh, h, w, person_binary,
                       expand_w=0.4, expand_up=0.8, expand_down=0.3):
    cx = fx + fw // 2
    cy = fy + fh // 2
    e_w = int(fw * (1 + expand_w * 2))
    e_h_top = int(fh * expand_up)
    e_h_bot = int(fh * expand_down)
    e_h = e_h_top + e_h_bot
    e_cy = fy + fh // 2 - e_h_top + e_h // 2
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.ellipse(mask, (cx, e_cy), (e_w // 2, e_h // 2), 0, 0, 360, 255, -1)
    return cv2.bitwise_and(mask, person_binary)

def detect_head_mask(orig_img, person_binary, person_bbox,
                     max_head_pct=0.50, neck_margin_below=1.2,
                     dilate_kernel_size=15, dilate_iterations=2):
    h, w = person_binary.shape[:2]
    px, py, pw, ph = person_bbox
    max_head_h = int(ph * max_head_pct)
    faces = detect_faces(orig_img)
    head_mask = np.zeros_like(person_binary)
    if len(faces) > 0:
        fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        head_mask = _ellipse_from_face(fx, fy, fw, fh, h, w, person_binary,
                                        expand_w=0.5, expand_up=1.5, expand_down=1.8)
    else:
        cx, cy = px + pw // 2, py + max_head_h // 2
        m = np.zeros_like(person_binary)
        cv2.ellipse(m, (cx, cy), (pw // 2, max_head_h // 2), 0, 0, 360, 255, -1)
        head_mask = cv2.bitwise_and(m, person_binary)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_kernel_size, dilate_kernel_size))
    head_mask = cv2.dilate(head_mask, kernel, iterations=dilate_iterations)
    if len(faces) > 0:
        _, fy2, _, fh2 = max(faces, key=lambda f: f[2] * f[3])
        head_bottom = min(h, fy2 + fh2 + int(fh2 * 1.8))
    else:
        head_bottom = py + max_head_h
    head_mask[head_bottom:, :] = 0
    return cv2.bitwise_and(head_mask, person_binary)

def detect_face_only(orig_img, person_binary, margin_above=0.50,
                     margin_below=0.70, margin_sides=0.40):
    h, w = person_binary.shape[:2]
    face_mask = np.zeros_like(person_binary)
    faces = detect_faces(orig_img)
    if len(faces) == 0:
        return face_mask
    fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
    cx = fx + fw // 2
    cy = fy + fh // 2
    e_w = int(fw * (1 + margin_sides * 2))
    e_h_top = int(fh * margin_above)
    e_h_bot = int(fh * margin_below)
    e_h = e_h_top + e_h_bot
    e_cy = fy + fh // 2 - e_h_top + e_h // 2
    cv2.ellipse(face_mask, (cx, e_cy), (e_w // 2, e_h // 2), 0, 0, 360, 255, -1)
    return cv2.bitwise_and(face_mask, person_binary)

def detect_neck_mask(person_binary, head_mask):
    h, w = person_binary.shape[:2]
    neck_mask = np.zeros_like(person_binary)
    head_rows = np.any(head_mask > 0, axis=1)
    if not np.any(head_rows):
        return neck_mask
    head_bottom = np.max(np.where(head_rows))
    shoulder_start = head_bottom
    prev_width = 0
    for row in range(head_bottom, min(h, head_bottom + int(h * 0.15))):
        row_pixels = np.sum(person_binary[row, :] > 0)
        if row_pixels > prev_width * 1.3 and prev_width > 0:
            shoulder_start = row
            break
        prev_width = max(prev_width, row_pixels)
    if shoulder_start > head_bottom:
        region = np.zeros_like(person_binary)
        region[head_bottom:shoulder_start, :] = 255
        neck_mask = cv2.bitwise_and(region, person_binary)
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        neck_mask = cv2.dilate(neck_mask, k, iterations=1)
        neck_mask = cv2.bitwise_and(neck_mask, person_binary)
    return neck_mask

# ─── Debug Grid ───────────────────────────────────────────────────────────────

def reinhard_color_transfer(target, source, mask):
    """Transfer color statistics from source to target using LAB color space (Reinhard)."""
    source_lab = cv2.cvtColor(source, cv2.COLOR_BGR2LAB).astype(np.float32)
    target_lab = cv2.cvtColor(target, cv2.COLOR_BGR2LAB).astype(np.float32)
    m = mask > 0
    if np.sum(m) < 100:
        return target
    src_pixels = source_lab[m]
    tgt_pixels = target_lab[m]
    src_mean, src_std = src_pixels.mean(axis=0), src_pixels.std(axis=0) + 1e-6
    tgt_mean, tgt_std = tgt_pixels.mean(axis=0), tgt_pixels.std(axis=0) + 1e-6
    full_lab = target_lab.copy()
    for ch in range(3):
        full_lab[:, :, ch] = (full_lab[:, :, ch] - tgt_mean[ch]) * (src_std[ch] / tgt_std[ch]) + src_mean[ch]
    full_lab = np.clip(full_lab, 0, 255).astype(np.uint8)
    return cv2.cvtColor(full_lab, cv2.COLOR_LAB2BGR)

def build_debug_grid(panels: list, cell_w=400, cell_h=600, cols=3, font_scale=0.55, padding=4):
    n = len(panels)
    rows_count = (n + cols - 1) // cols
    mask_colors = [
        (0, 0, 200), (0, 180, 0), (200, 100, 0), (0, 200, 200),
        (200, 0, 200), (0, 160, 255), (255, 100, 0), (100, 200, 50), (50, 50, 200),
    ]
    canvas_w = cols * (cell_w + padding) + padding
    canvas_h = rows_count * (cell_h + padding) + padding
    canvas = np.full((canvas_h, canvas_w, 3), 40, dtype=np.uint8)
    label_h = 28
    for idx, (fname, img, label) in enumerate(panels):
        r = idx // cols
        c = idx % cols
        x0 = padding + c * (cell_w + padding)
        y0 = padding + r * (cell_h + padding)
        if img.ndim == 2 or (img.ndim == 3 and img.shape[2] == 1):
            gray = img if img.ndim == 2 else img[:, :, 0]
            color = mask_colors[idx % len(mask_colors)]
            display = np.zeros((gray.shape[0], gray.shape[1], 3), dtype=np.uint8)
            display[gray > 127] = color
        elif img.shape[2] == 4:
            display = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        else:
            display = img.copy()
        h_img, w_img = display.shape[:2]
        scale = min(cell_w / w_img, (cell_h - label_h) / h_img)
        new_w, new_h = int(w_img * scale), int(h_img * scale)
        resized = cv2.resize(display, (new_w, new_h), interpolation=cv2.INTER_AREA)
        y_off = y0 + label_h + max(0, (cell_h - label_h - new_h) // 2)
        x_off = x0 + max(0, (cell_w - new_w) // 2)
        y_end = min(y_off + new_h, canvas_h)
        x_end = min(x_off + new_w, canvas_w)
        canvas[y_off:y_end, x_off:x_end] = resized[:y_end - y_off, :x_end - x_off]
        cv2.rectangle(canvas, (x0, y0), (x0 + cell_w, y0 + label_h), (30, 30, 30), -1)
        cv2.putText(canvas, label, (x0 + 6, y0 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.rectangle(canvas, (x0, y0), (x0 + cell_w, y0 + label_h + cell_h), (80, 80, 80), 1)
    return canvas

# ─── Main: Generate Masks Only ───────────────────────────────────────────────

async def run_masks(image_path: str, skip_inpaint: bool = False):
    image_path = Path(image_path)
    stem = image_path.stem
    out_dir = Path(__file__).parent / "data" / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'='*60}")
    print(f"  SE11 Mask Research — {stem}")
    print(f"  Output: {out_dir}")
    print(f"{'='*60}")

    orig_img = cv2.imread(str(image_path))
    if orig_img is None:
        print(f"ERROR: Cannot read {image_path}")
        return
    orig_h, orig_w = orig_img.shape[:2]
    print(f"\nImage: {orig_w}x{orig_h}")
    save_mask(out_dir / "00_original.png", orig_img)
    t0 = time.time()

    # ─── Stage 1: Person Detection ───
    print("\n[1/5] Person Detection (SE10)...")
    image_bytes = open(image_path, "rb").read()
    person_seg = await se10_segment(
        image_bytes, f"{stem}_person.jpg",
        classes="person, woman, man",
        box_threshold=0.20, text_threshold=0.15, mode="person",
    )
    t1 = time.time()
    print(f"  {t1-t0:.1f}s | detected={person_seg.get('detected')} | objects={len(person_seg.get('objects', []))}")
    for i, obj in enumerate(person_seg.get("objects", [])):
        print(f"    [{i}] area={obj.get('area_pct',0):.1f}%")

    if not person_seg.get("detected") or not person_seg.get("masks"):
        print("  No person detected!")
        save_json(out_dir / "metadata.json", {"error": "no person detected"})
        return

    best_idx = max(range(len(person_seg["objects"])),
                   key=lambda i: person_seg["objects"][i].get("area_pct", 0))
    person_mask = decode_mask(person_seg["masks"][best_idx], orig_h, orig_w)
    save_mask(out_dir / "01_person_raw.png", person_mask)

    # Fill holes
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    filled = cv2.morphologyEx(person_mask, cv2.MORPH_CLOSE, close_k, iterations=3)
    _h, _w = filled.shape
    _flood = filled.copy()
    _fm = np.zeros((_h + 2, _w + 2), np.uint8)
    for sx, sy in [(0,0),(_w-1,0),(0,_h-1),(_w-1,_h-1),(_w//2,0),(_w//2,_h-1),(0,_h//2),(_w-1,_h//2)]:
        if 0 <= sx < _w and 0 <= sy < _h and _flood[sy, sx] == 0:
            cv2.floodFill(_flood, _fm, (sx, sy), 255)
    person_binary = cv2.bitwise_or(filled, cv2.bitwise_not(_flood))
    print(f"  Holes filled: {np.count_nonzero(cv2.bitwise_not(_flood))}px")
    save_mask(out_dir / "01b_person_filled.png", person_binary)
    save_json(out_dir / "se10_person.json", person_seg.get("objects", []))

    # ─── Stage 2: Head / Body / Face ───
    print("\n[2/5] Head / Body / Face Separation...")
    contours, _ = cv2.findContours(person_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    px, py, pw, ph = cv2.boundingRect(max(contours, key=cv2.contourArea))

    head_mask = detect_head_mask(orig_img, person_binary, (px, py, pw, ph))
    face_only = detect_face_only(orig_img, person_binary)

    save_mask(out_dir / "02_head_raw.png", head_mask)
    save_mask(out_dir / "04_face_only.png", face_only)

    # ─── Stage 3: Clothes Detection ───
    print("\n[3/5] Clothes Detection (Florence-2)...")
    clothes_seg = await se10_segment(
        image_bytes, f"{stem}_clothes.jpg",
        classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
        box_threshold=0.06, text_threshold=0.04,
        mode="clothes", detector="florence2",
    )
    t2 = time.time()
    print(f"  {t2-t1:.1f}s | detected={clothes_seg.get('detected')} | objects={len(clothes_seg.get('objects', []))}")
    for i, obj in enumerate(clothes_seg.get("objects", [])):
        print(f"    [{i}] area={obj.get('area_pct',0):.1f}%")

    clothes_combined = None
    if clothes_seg.get("detected") and clothes_seg.get("masks"):
        for mb in clothes_seg["masks"]:
            cm = decode_mask(mb, orig_h, orig_w)
            clothes_combined = cm if clothes_combined is None else cv2.bitwise_or(clothes_combined, cm)
        save_mask(out_dir / "05_clothes_raw.png", clothes_combined)
    save_json(out_dir / "se10_clothes.json", clothes_seg.get("objects", []))

    # ─── CRITICAL: Head mask = face + hair + neck (NO clothing) ───
    # Step 1: Subtract clothes from raw head
    if clothes_combined is not None:
        head_sub = cv2.bitwise_and(head_mask, cv2.bitwise_not(clothes_combined))
    else:
        head_sub = head_mask.copy()
    head_sub = cv2.bitwise_and(head_sub, person_binary)

    # Step 2: Distance transform to inflate mask back (fills small concavities)
    dist = cv2.distanceTransform(head_sub, cv2.DIST_L2, 5)
    _, head_inflated = cv2.threshold(dist, 8, 255, cv2.THRESH_BINARY)
    head_inflated = head_inflated.astype(np.uint8)

    # Step 3: Combine — keep original center, allow inflated edges
    head_base = cv2.bitwise_or(head_sub, head_inflated)
    head_base = cv2.bitwise_and(head_base, person_binary)

    # Step 4: Close remaining holes
    close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    head_base = cv2.morphologyEx(head_base, cv2.MORPH_CLOSE, close_k, iterations=2)

    # Step 5: Gaussian blur for smooth organic edges
    head_f = head_base.astype(np.float32) / 255.0
    head_f = cv2.GaussianBlur(head_f, (15, 15), 5.0)
    head_mask = (head_f > 0.5).astype(np.uint8) * 255

    # Step 6: Final clip to person silhouette
    head_mask = cv2.bitwise_and(head_mask, person_binary)

    # Step 7: Remove small noise components
    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(head_mask, connectivity=8)
    min_area = head_mask.size * 0.005
    for i in range(1, n_labels):
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            head_mask[labels == i] = 0

    print(f"  Head mask: inflated, smoothed, clean")

    body_mask = cv2.bitwise_and(person_binary, cv2.bitwise_not(head_mask))
    neck = detect_neck_mask(person_binary, head_mask)

    head_pct = cv2.countNonZero(head_mask) / head_mask.size * 100
    body_pct = cv2.countNonZero(body_mask) / body_mask.size * 100
    face_pct = cv2.countNonZero(face_only) / face_only.size * 100
    neck_pct = cv2.countNonZero(neck) / neck.size * 100
    print(f"  Head: {head_pct:.1f}% | Body: {body_pct:.1f}% | Face: {face_pct:.1f}% | Neck: {neck_pct:.1f}%")

    faces = detect_faces(orig_img)
    for i, (fx, fy, fw, fh) in enumerate(faces):
        print(f"  face[{i}]: ({fx},{fy}) {fw}x{fh}")

    save_mask(out_dir / "02_head_mask.png", head_mask)
    save_mask(out_dir / "03_body_mask.png", body_mask)
    save_mask(out_dir / "04b_neck.png", neck)

    # ─── Stage 4: Exposed Skin ───
    print("\n[4/5] Exposed Skin Calculation...")
    if clothes_combined is not None:
        exposed_skin = cv2.bitwise_and(body_mask, cv2.bitwise_not(clothes_combined))
    else:
        exposed_skin = body_mask.copy()
    exposed_skin = cv2.bitwise_or(exposed_skin, neck)
    exposed_pct = cv2.countNonZero(exposed_skin) / exposed_skin.size * 100
    print(f"  Exposed skin: {exposed_pct:.1f}%")
    save_mask(out_dir / "06_exposed_skin.png", exposed_skin)

    # ─── Stage 5: Inpaint Mask ───
    print("\n[5/5] Inpaint Mask Preparation...")
    dpx = max(10, int(min(orig_w, orig_h) * 0.02))
    inpaint_mask = body_mask.copy()
    ek = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dpx, dpx))
    inpaint_mask = cv2.dilate(inpaint_mask, ek, iterations=2)
    person_exp = cv2.dilate(person_binary, ek, iterations=3)
    inpaint_mask = cv2.bitwise_and(inpaint_mask, person_exp)
    ck = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    inpaint_mask = cv2.morphologyEx(inpaint_mask, cv2.MORPH_CLOSE, ck, iterations=2)
    inpaint_pct = cv2.countNonZero(inpaint_mask) / inpaint_mask.size * 100
    print(f"  Inpaint mask: {inpaint_pct:.1f}%")
    save_mask(out_dir / "07_inpaint_mask.png", inpaint_mask)

    # ─── Stage 6: IP-Adapter Reference (face-masked) ───
    if not skip_inpaint:
        print("\n[6/7] IP-Adapter Reference...")
        # Use original image as reference (NOT face-masked) for pose preservation
        # The head_mask protects face during composite — no need to mask here
        ip_ref = orig_img.copy()
        save_mask(out_dir / "08_ip_reference.png", ip_ref)

    # ─── Stage 7: SE8 Inpainting (3 tries) ───
    if not skip_inpaint:
        print("\n[7/7] SE8 Inpainting...")
        nsfw_prompt = (
            "NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, "
            "detailed breast anatomy, realistic nipples, areola details, "
            "natural skin pores, skin texture, skin imperfections, "
            "realistic body proportions, maintaining exact same body posture, "
            "skin tone matching the person's arms and face, consistent skin color throughout, "
            "photorealistic, professional studio photography, soft lighting, "
            "sharp focus, raw photo, highly detailed, hyperrealistic, 8k uhd"
        )
        nsfw_negative = (
            "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, "
            "wrong anatomy, extra limbs, missing limbs, floating limbs, "
            "(mutated hands and fingers, extra fingers, missing fingers:1.4), "
            "(extra face, second face, face on body, face on chest:1.8), "
            "long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, "
            "clothes, fabric, bra, straps, underwear, pattern, floral, textile, "
            "cartoon, anime, sketch, "
            "(changed pose, moved body, different position:1.5), "
            "asymmetric nipples, mismatched skin tone, color banding"
        )

        # Pre-scale: ensure short side >= 1024 to avoid SE8 ESRGAN upscaler crash
        min_dim = min(orig_w, orig_h)
        if min_dim < 1024:
            scale = 1024 / min_dim
            new_w, new_h = int(orig_w * scale), int(orig_h * scale)
            inpaint_for_se8 = cv2.resize(inpaint_mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
            orig_for_se8 = cv2.resize(orig_img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
            ip_ref_for_se8 = cv2.resize(ip_ref, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            inpaint_for_se8 = inpaint_mask
            orig_for_se8 = orig_img
            ip_ref_for_se8 = ip_ref

        image_b64 = _to_data_uri(base64.b64encode(
            cv2.imencode(".jpg", orig_for_se8, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tobytes()
        ).decode(), mime="image/jpeg")
        _, mask_buf = cv2.imencode(".png", inpaint_for_se8)
        mask_b64 = _to_data_uri(base64.b64encode(mask_buf).decode(), mime="image/png")
        _, ip_buf = cv2.imencode(".jpg", ip_ref_for_se8, [cv2.IMWRITE_JPEG_QUALITY, 90])
        ip_b64 = _to_data_uri(base64.b64encode(ip_buf).decode(), mime="image/jpeg")

        ip_prompts = [
            {"cn_img": ip_b64, "cn_stop": 0.5, "cn_weight": 0.6, "cn_type": "ImagePrompt"},
            {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
            {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
            {"cn_img": None, "cn_stop": 0.5, "cn_weight": 0.0, "cn_type": "ImagePrompt"},
        ]

        configs = [
            {"label": "try_1", "strength": 0.85, "field": 0.618, "seed": -1},
            {"label": "try_2", "strength": 0.90, "field": 0.618, "seed": 42},
            {"label": "try_3", "strength": 1.00, "field": 0.618, "seed": 99},
        ]

        for cfg in configs:
            label = cfg["label"]
            print(f"  {label}: strength={cfg['strength']} field={cfg['field']} seed={cfg['seed']}")
            try:
                t_try = time.time()
                result = await _se8_inpaint(image_b64, mask_b64, nsfw_prompt, nsfw_negative,
                                            cfg["strength"], cfg["field"], ip_prompts)
                elapsed = time.time() - t_try
                if result.get("base64"):
                    result_bytes = base64.b64decode(result["base64"])
                    result_img = cv2.imdecode(np.frombuffer(result_bytes, np.uint8), cv2.IMREAD_COLOR)
                    if result_img is not None:
                        if result_img.shape[:2] != (orig_h, orig_w):
                            result_img = cv2.resize(result_img, (orig_w, orig_h))
                        # Feathered composite: smooth blend at head/body boundary
                        head_f = head_mask.astype(np.float32) / 255.0
                        head_f = cv2.GaussianBlur(head_f, (21, 21), 7.0)
                        head_f = np.clip(head_f * 1.5, 0, 1)  # strengthen center
                        composited = (result_img.astype(np.float32) * (1 - head_f[:, :, None]) +
                                      orig_img.astype(np.float32) * head_f[:, :, None])
                        composited = np.clip(composited, 0, 255).astype(np.uint8)
                        # Skin-only color transfer
                        _skin_hsv = cv2.inRange(cv2.cvtColor(orig_img, cv2.COLOR_BGR2HSV),
                                                 np.array([0, 15, 60]), np.array([30, 170, 255]))
                        _skin_ref = cv2.bitwise_and(_skin_hsv, person_binary)
                        _skin_ref = cv2.bitwise_and(_skin_ref, cv2.bitwise_not(head_mask))
                        _skin_mask = (_skin_ref > 0).astype(np.uint8) * 255
                        if cv2.countNonZero(_skin_mask) > 100:
                            composited = reinhard_color_transfer(composited, orig_img, _skin_mask)
                            composited = (composited.astype(np.float32) * (1 - head_f[:, :, None]) +
                                          orig_img.astype(np.float32) * head_f[:, :, None])
                            composited = np.clip(composited, 0, 255).astype(np.uint8)
                        try_dir = out_dir / label
                        try_dir.mkdir(exist_ok=True)
                        save_mask(try_dir / "result.png", composited)
                        save_mask(try_dir / "inpaint_mask.png", inpaint_mask)
                        save_mask(try_dir / "head_mask.png", head_mask)
                        save_json(try_dir / "metadata.json", {"params": cfg, "time_s": round(elapsed, 1)})
                        print(f"    Saved: {try_dir}/result.png ({elapsed:.1f}s)")
                    else:
                        print(f"    WARN: cv2 decode failed")
                else:
                    print(f"    WARN: no base64 in result")
            except Exception as e:
                print(f"    ERROR: {type(e).__name__}: {e}")
                if "CUDA" in str(e):
                    print("    Waiting 15s for CUDA recovery...")
                    await asyncio.sleep(15)

    # ─── Debug Grid ───
    print("\n[Grid] Building debug grid...")
    panels = [
        ("00_original", orig_img, "1. Original"),
        ("01_person", person_binary, "2. Person (SE10)"),
        ("02_head_raw", head_mask, f"3. Head ({head_pct:.1f}%)"),
        ("04_face_only", face_only, f"4. Face ({face_pct:.1f}%)"),
    ]
    if clothes_combined is not None:
        panels.append(("05_clothes_raw", clothes_combined, "5. Clothes Raw"))
    panels.extend([
        ("04b_neck", neck, f"6. Neck ({neck_pct:.1f}%)"),
        ("06_exposed_skin", exposed_skin, f"7. Skin ({exposed_pct:.1f}%)"),
        ("07_inpaint_mask", inpaint_mask, f"8. Inpaint ({inpaint_pct:.1f}%)"),
        ("03_body_mask", body_mask, f"9. Body (head-sub)"),
    ])
    grid = build_debug_grid(panels, cols=3)
    cv2.imwrite(str(out_dir / "debug_grid.png"), grid)

    # ─── Summary ───
    total = time.time() - t0
    summary = {
        "image": str(image_path),
        "dimensions": {"w": orig_w, "h": orig_h},
        "timing": {"person_s": round(t1-t0,1), "clothes_s": round(t2-t1,1), "total_s": round(total,1)},
        "masks": {
            "head_pct": round(head_pct,2), "body_pct": round(body_pct,2),
            "face_pct": round(face_pct,2), "neck_pct": round(neck_pct,2),
            "exposed_skin_pct": round(exposed_pct,2), "inpaint_pct": round(inpaint_pct,2),
        },
        "person_objects": len(person_seg.get("objects",[])),
        "clothes_objects": len(clothes_seg.get("objects",[])),
        "faces_detected": len(faces),
    }
    save_json(out_dir / "metadata.json", summary)

    print(f"\n{'='*60}")
    print(f"  DONE — {total:.1f}s | {out_dir}/")
    print(f"{'='*60}")
    for f in sorted(out_dir.rglob("*")):
        if f.is_file():
            print(f"    {f.name} ({f.stat().st_size/1024:.0f}KB)")

def main():
    parser = argparse.ArgumentParser(description="SE11 Mask Research")
    parser.add_argument("--image", default=str(Path(__file__).parent / "OK.jpg"))
    parser.add_argument("--skip-inpaint", action="store_true", help="Skip SE8 inpainting (masks only)")
    args = parser.parse_args()
    asyncio.run(run_masks(args.image, skip_inpaint=args.skip_inpaint))

if __name__ == "__main__":
    main()
