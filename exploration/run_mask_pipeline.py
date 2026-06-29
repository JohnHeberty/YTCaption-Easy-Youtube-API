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
                                        expand_w=0.4, expand_up=0.8, expand_down=neck_margin_below)
    else:
        cx, cy = px + pw // 2, py + max_head_h // 2
        m = np.zeros_like(person_binary)
        cv2.ellipse(m, (cx, cy), (pw // 2, max_head_h // 2), 0, 0, 360, 255, -1)
        head_mask = cv2.bitwise_and(m, person_binary)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_kernel_size, dilate_kernel_size))
    head_mask = cv2.dilate(head_mask, kernel, iterations=dilate_iterations)
    if len(faces) > 0:
        _, fy2, _, fh2 = max(faces, key=lambda f: f[2] * f[3])
        head_bottom = min(h, fy2 + fh2 + int(fh2 * neck_margin_below))
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

async def run_masks(image_path: str):
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
    body_mask = cv2.bitwise_and(person_binary, cv2.bitwise_not(head_mask))
    face_only = detect_face_only(orig_img, person_binary)
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
    save_mask(out_dir / "04_face_only.png", face_only)
    save_mask(out_dir / "04b_neck.png", neck)

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

    # ─── Stage 4: Exposed Skin ───
    print("\n[4/5] Exposed Skin Calculation...")
    clothes_clean = None
    if clothes_combined is not None:
        clothes_clean = cv2.bitwise_and(clothes_combined, cv2.bitwise_not(head_mask))
        save_mask(out_dir / "05b_clothes_no_hair.png", clothes_clean)

    if clothes_clean is not None:
        exposed_skin = cv2.bitwise_and(body_mask, cv2.bitwise_not(clothes_clean))
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

    # ─── Debug Grid ───
    print("\n[Grid] Building debug grid...")
    panels = [
        ("00_original", orig_img, "1. Original"),
        ("01_person", person_binary, "2. Person (SE10)"),
        ("02_head_mask", head_mask, f"3. Head ({head_pct:.1f}%)"),
        ("04_face_only", face_only, f"4. Face ({face_pct:.1f}%)"),
    ]
    if clothes_combined is not None:
        panels.append(("05_clothes_raw", clothes_combined, "5. Clothes Raw"))
    if clothes_clean is not None:
        panels.append(("05b_clothes_no_hair", clothes_clean, "6. Clothes -Hair"))
    panels.extend([
        ("04b_neck", neck, f"7. Neck ({neck_pct:.1f}%)"),
        ("06_exposed_skin", exposed_skin, f"8. Skin ({exposed_pct:.1f}%)"),
        ("07_inpaint_mask", inpaint_mask, f"9. Inpaint ({inpaint_pct:.1f}%)"),
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
    args = parser.parse_args()
    asyncio.run(run_masks(args.image))

if __name__ == "__main__":
    main()
