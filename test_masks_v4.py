#!/usr/bin/env python3
"""Mask Test V4 — Histogram Backprojection for clothing mask expansion.

Technique: use the detected clothing mask as "seed" to find more same-color
pixels (straps, edges) via histogram backprojection in HSV space.

No SE8, no inpainting — just mask visualization for validation.
"""
import sys, os, base64, asyncio, cv2, numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services/se11-clothes-removal"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services/se11-clothes-removal/app"))
from app.infrastructure.http_client import SE10Client


def _s(data_uri):
    return data_uri.split(",", 1)[1] if "," in data_uri else data_uri

def _p(s):
    s = s.strip()
    p = len(s) % 4
    return s + "=" * (4 - p) if p else s


def expand_mask_morphological(mask, person_mask=None):
    """Expand clothing mask using multi-angle morphological closing.

    Straps are thin lines connecting clothing body to shoulders.
    Closing with directional kernels bridges the gap without
    matching skin colors (no histogram, no false positives on face).

    V4.5: Pure morphology — no color confusion.
    """
    result = mask.copy()
    new_all = np.zeros_like(mask)

    # Large kernels to bridge the gap between body zone and head zone
    kernel_configs = [
        (1, 40),    # long vertical — bridge body→head zone gap
        (1, 25),    # medium vertical — catch shorter straps
        (1, 55),    # extra long — catch straps at shoulder height
        (7, 1),     # horizontal short — connect sideways
        (11, 1),    # horizontal medium
    ]

    for kw, kh in kernel_configs:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kw, kh))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        if person_mask is not None:
            closed = cv2.bitwise_and(closed, person_mask)

        new = cv2.bitwise_and(closed, cv2.bitwise_not(mask))
        new_all = cv2.bitwise_or(new_all, new)
        result = cv2.bitwise_or(result, closed)

    # Restrict to person
    if person_mask is not None:
        result = cv2.bitwise_and(result, person_mask)

    return result, new_all


async def main(image_path, output_dir):
    se10 = SE10Client()
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    orig = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = orig.shape[:2]
    os.makedirs(output_dir, exist_ok=True)
    print(f"Image: {w}x{h}")

    # === STEP 1: Person detection ===
    print("1. Detecting person...")
    person_seg = await se10.segment(
        image_bytes=image_bytes, filename="test.jpg",
        classes="person, woman, man", box_threshold=0.20, text_threshold=0.15, mode="person")
    best = max(range(len(person_seg["objects"])),
               key=lambda i: person_seg["objects"][i].get("area_pct", 0))
    pm = cv2.imdecode(
        np.frombuffer(base64.b64decode(_p(_s(person_seg["masks"][best]))), np.uint8),
        cv2.IMREAD_GRAYSCALE)
    if pm.shape[:2] != (h, w):
        pm = cv2.resize(pm, (w, h))
    person = (pm > 127).astype(np.uint8) * 255

    # === STEP 2: Clothing detection (Florence-2) ===
    print("2. Detecting clothes (Florence-2)...")
    clothes_seg = await se10.segment(
        image_bytes=image_bytes, filename="test_c.jpg",
        classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
        box_threshold=0.06, text_threshold=0.04, mode="clothes", detector="florence2")
    clothes_raw = None
    if clothes_seg.get("masks"):
        for mb in clothes_seg["masks"]:
            cm = cv2.imdecode(
                np.frombuffer(base64.b64decode(_p(_s(mb))), np.uint8), cv2.IMREAD_GRAYSCALE)
            if cm is not None:
                if cm.shape[:2] != (h, w):
                    cm = cv2.resize(cm, (w, h))
                cb = (cm > 127).astype(np.uint8) * 255
                clothes_raw = cb if clothes_raw is None else cv2.bitwise_or(clothes_raw, cb)
    if clothes_raw is None:
        clothes_raw = np.zeros_like(person)
    clothes_on_person = cv2.bitwise_and(person, clothes_raw)

    # === STEP 3: Expand clothing mask with histogram backprojection ===
    print("3. Expanding clothing mask with morphological closing...")
    clothes_expanded, new_pixels = expand_mask_morphological(clothes_on_person, person_mask=person)

    raw_pct = (clothes_on_person > 0).sum() / clothes_on_person.size * 100
    expanded_pct = (clothes_expanded > 0).sum() / clothes_expanded.size * 100
    new_pct = (new_pixels > 0).sum() / new_pixels.size * 100
    print(f"  Raw clothing:     {raw_pct:.1f}%")
    print(f"  Expanded clothing: {expanded_pct:.1f}%")
    print(f"  New pixels found:  {new_pct:.1f}%")

    # === STEP 4: Head zone + face_only ===
    cts, _ = cv2.findContours(person, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    px, py, pw, ph = cv2.boundingRect(max(cts, key=cv2.contourArea))
    head_h = int(ph * 0.40)
    head_zone = np.zeros_like(person)
    head_zone[py:py + head_h, px:px + pw] = 255
    head_zone = cv2.bitwise_and(head_zone, person)
    head_zone = cv2.dilate(head_zone, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)), iterations=2)
    head_zone = cv2.bitwise_and(head_zone, person)

    face_only = cv2.bitwise_and(head_zone, cv2.bitwise_not(clothes_expanded))
    body = cv2.bitwise_and(person, cv2.bitwise_not(head_zone))
    exposed_skin = cv2.bitwise_and(body, cv2.bitwise_not(clothes_expanded))
    straps_before = cv2.countNonZero(cv2.bitwise_and(head_zone, clothes_on_person))
    straps_in_head_raw = cv2.bitwise_and(head_zone, clothes_on_person)
    straps_in_head_expanded = cv2.bitwise_and(head_zone, clothes_expanded)
    straps_new = cv2.bitwise_and(straps_in_head_expanded, cv2.bitwise_not(straps_in_head_raw))

    # Save masks
    def save(name, mask):
        cv2.imwrite(os.path.join(output_dir, f"{name}.png"), mask)
        pct = (mask > 0).sum() / mask.size * 100
        print(f"  {name}: {pct:.1f}%")

    save("01_person", person)
    save("02_clothes_raw", clothes_on_person)
    save("03_clothes_expanded", clothes_expanded)
    save("04_new_pixels", new_pixels)
    save("05_head_zone", head_zone)
    save("06_face_only", face_only)
    save("07_straps_in_head_raw", straps_in_head_raw)
    save("08_straps_in_head_expanded", straps_in_head_expanded)
    save("09_straps_new", straps_new)

    # OVERLAY: Before expansion
    ov_before = orig.copy()
    ov_c = ov_before.copy(); ov_c[clothes_on_person > 0] = [255, 0, 255]
    ov_before = cv2.addWeighted(ov_before, 0.4, ov_c, 0.6, 0)
    ov_s = ov_before.copy(); ov_s[straps_in_head_raw > 0] = [0, 255, 255]
    ov_before = cv2.addWeighted(ov_before, 0.6, ov_s, 0.4, 0)
    cv2.putText(ov_before, "BEFORE: MAGENTA=clothes YELLOW=straps_in_head",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.imwrite(os.path.join(output_dir, "OVERLAY_before.png"), ov_before)

    # OVERLAY: After expansion
    ov_after = orig.copy()
    ov_e = ov_after.copy(); ov_e[clothes_expanded > 0] = [255, 0, 255]
    ov_after = cv2.addWeighted(ov_after, 0.4, ov_e, 0.6, 0)
    ov_n = ov_after.copy(); ov_n[new_pixels > 0] = [0, 255, 0]  # green = newly found
    ov_after = cv2.addWeighted(ov_after, 0.6, ov_n, 0.4, 0)
    ov_f = ov_after.copy(); ov_f[face_only > 0] = [0, 128, 255]  # orange = face protected
    ov_after = cv2.addWeighted(ov_after, 0.7, ov_f, 0.3, 0)
    cv2.putText(ov_after, f"AFTER: MAGENTA=expanded GREEN=new ORANGE=face ({new_pct:.1f}% new)",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.imwrite(os.path.join(output_dir, "OVERLAY_after.png"), ov_after)

    # OVERLAY: Side by side (cropped to person region)
    y1, y2 = max(0, py - 20), min(h, py + ph + 20)
    x1, x2 = max(0, px - 20), min(w, px + pw + 20)
    crop_before = ov_before[y1:y2, x1:x2].copy()
    crop_after = ov_after[y1:y2, x1:x2].copy()
    side_by_side = np.hstack([crop_before, crop_after])
    cv2.putText(side_by_side, "LEFT=before RIGHT=after", (10, side_by_side.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    cv2.imwrite(os.path.join(output_dir, "COMPARISON_side_by_side.png"), side_by_side)

    print(f"\nSaved to: {output_dir}")
    print(f"\n=== COMPARISON ===")
    print(f"BEFORE:  clothing={raw_pct:.1f}%, straps in head={cv2.countNonZero(straps_in_head_raw)/straps_in_head_raw.size*100:.1f}%")
    print(f"AFTER:   clothing={expanded_pct:.1f}%, straps in head={cv2.countNonZero(straps_in_head_expanded)/straps_in_head_expanded.size*100:.1f}%")
    print(f"NEW:     {new_pct:.1f}% pixels found, {cv2.countNonZero(straps_new)/straps_new.size*100:.1f}% straps recovered")

    await se10.close()


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "services/se11-clothes-removal/Test.png"
    out = sys.argv[2] if len(sys.argv) > 2 else "masks_v4"
    asyncio.run(main(img, out))
