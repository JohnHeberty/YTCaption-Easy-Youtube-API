#!/usr/bin/env python3
"""Mask Priority Test V3 — correct approach.

Pipeline order (matches user's request):
1. Remove background → person_mask
2. Detect ALL clothing → clothes_mask (body + head zone)
3. Face = head zone AND NOT clothes (just face, not straps)
4. Inpaint = ALL clothing on person (body + straps in head zone)
5. Protect = face (head MINUS clothing)

No SE8, no inpainting — just masks for visual validation.
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


async def main(image_path, output_dir):
    se10 = SE10Client()
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    orig = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = orig.shape[:2]
    os.makedirs(output_dir, exist_ok=True)
    print(f"Image: {w}x{h}")

    # === STEP 1: Remove background → person ===
    print("1. Detecting person (remove background)...")
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

    # === STEP 2: Detect ALL clothing ===
    print("2. Detecting ALL clothing...")
    clothes_seg = await se10.segment(
        image_bytes=image_bytes, filename="test_c.jpg",
        classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment",
        box_threshold=0.06, text_threshold=0.04, mode="clothes", detector="florence2")
    clothes = None
    if clothes_seg.get("masks"):
        for mb in clothes_seg["masks"]:
            cm = cv2.imdecode(
                np.frombuffer(base64.b64decode(_p(_s(mb))), np.uint8), cv2.IMREAD_GRAYSCALE)
            if cm is not None:
                if cm.shape[:2] != (h, w):
                    cm = cv2.resize(cm, (w, h))
                cb = (cm > 127).astype(np.uint8) * 255
                clothes = cb if clothes is None else cv2.bitwise_or(clothes, cb)
    if clothes is None:
        clothes = np.zeros_like(person)

    # Restrict clothes to person (remove background from clothes)
    clothes_on_person = cv2.bitwise_and(person, clothes)

    # === STEP 3: Head zone (reference) ===
    cts, _ = cv2.findContours(person, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    px, py, pw, ph = cv2.boundingRect(max(cts, key=cv2.contourArea))
    head_h = int(ph * 0.40)

    # === STEP 4: Face = head zone MINUS clothing ===
    head_zone = np.zeros_like(person)
    head_zone[py:py + head_h, px:px + pw] = 255
    head_zone = cv2.bitwise_and(head_zone, person)
    head_zone = cv2.dilate(head_zone, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)), iterations=2)
    head_zone = cv2.bitwise_and(head_zone, person)

    # Face = head zone with clothing removed (just face skin, not straps)
    face = cv2.bitwise_and(head_zone, cv2.bitwise_not(clothes_on_person))

    # === STEP 5: Inpaint = ALL clothing on person ===
    inpaint = clothes_on_person.copy()

    # === STEP 6: Body = person - head (for reference) ===
    body = cv2.bitwise_and(person, cv2.bitwise_not(head_zone))

    # === STEP 7: What was being missed ===
    straps_in_head = cv2.bitwise_and(head_zone, clothes_on_person)
    straps_not_in_body = cv2.bitwise_and(straps_in_head, cv2.bitwise_not(body))

    # Exposed skin = body with clothing removed
    exposed_skin = cv2.bitwise_and(body, cv2.bitwise_not(clothes_on_person))

    def save(name, mask):
        cv2.imwrite(os.path.join(output_dir, f"{name}.png"), mask)
        pct = (mask > 0).sum() / mask.size * 100
        print(f"  {name}: {pct:.1f}%")

    save("01_person", person)
    save("02_clothes_on_person", clothes_on_person)
    save("03_head_zone_40pct", head_zone)
    save("04_face_only", face)
    save("05_body", body)
    save("06_exposed_skin", exposed_skin)
    save("07_INPAINT_MASK", inpaint)
    save("08_straps_in_head", straps_in_head)
    save("09_straps_not_in_body", straps_not_in_body)

    # === OVERLAY: Final proposed masks ===
    overlay = orig.copy()

    # Green = face (protected)
    ov_f = overlay.copy()
    ov_f[face > 0] = [0, 255, 0]
    overlay = cv2.addWeighted(overlay, 0.4, ov_f, 0.6, 0)

    # Magenta = inpaint (ALL clothing)
    ov_c = overlay.copy()
    ov_c[inpaint > 0] = [255, 0, 255]
    overlay = cv2.addWeighted(overlay, 0.5, ov_c, 0.5, 0)

    # Yellow = straps in head zone (the fix)
    ov_s = overlay.copy()
    ov_s[straps_not_in_body > 0] = [0, 255, 255]
    overlay = cv2.addWeighted(overlay, 0.6, ov_s, 0.4, 0)

    cv2.putText(overlay, "V3: GREEN=face MAGENTA=all_clothes YELLOW=straps_fixed",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
    cv2.imwrite(os.path.join(output_dir, "OVERLAY_v3.png"), overlay)

    # === OVERLAY: Comparison with current ===
    ov_current = orig.copy()
    exposed_skin_old = cv2.bitwise_and(body, cv2.bitwise_not(clothes_on_person))
    clothing_old = cv2.bitwise_and(body, cv2.bitwise_not(exposed_skin_old))

    ov_h = ov_current.copy(); ov_h[head_zone > 0] = [0, 0, 255]
    ov_current = cv2.addWeighted(ov_current, 0.4, ov_h, 0.6, 0)
    ov_cl = ov_current.copy(); ov_cl[clothing_old > 0] = [255, 0, 255]
    ov_current = cv2.addWeighted(ov_current, 0.5, ov_cl, 0.5, 0)
    cv2.putText(ov_current, "CURRENT: RED=head40 MAGENTA=clothing(body ONLY)",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.imwrite(os.path.join(output_dir, "OVERLAY_current.png"), ov_current)

    print(f"\nSaved to: {output_dir}")
    print(f"\n=== COMPARISON ===")
    print(f"CURRENT: clothing={clothing_old.sum()/clothing_old.size*100:.1f}% (body only, straps excluded)")
    print(f"V3:      inpaint={inpaint.sum()/inpaint.size*100:.1f}% (ALL clothing, straps included)")
    print(f"V3:      face={face.sum()/face.size*100:.1f}% (face only, not full head)")
    print(f"Straps now included: {straps_not_in_body.sum()/straps_not_in_body.size*100:.1f}%")

    await se10.close()


if __name__ == "__main__":
    img = sys.argv[1] if len(sys.argv) > 1 else "services/se11-clothes-removal/Test.png"
    out = sys.argv[2] if len(sys.argv) > 2 else "masks_v3"
    asyncio.run(main(img, out))
