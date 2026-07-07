"""Shared helper functions for SE11 Clothes Removal pipelines."""
from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as _np

logger = logging.getLogger(__name__)

# ─── YAML Config Loader ─────────────────────────────────────────────────────

_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


@dataclass(frozen=True)
class NSFWConfig:
    """Immutable NSFW pipeline configuration loaded from YAML."""
    prompt: str
    negative: str
    loras: list[dict]
    max_attempts: int = 5
    base_strength: float = 0.86
    inpaint_respective_field: float = 0.618
    ip_adapter_faceid_weight: float = 0.8
    base_model: str = "lustifySDXLNSFW_v20-inpainting.safetensors"


def _load_nsfw_config(profile: str) -> NSFWConfig:
    """Load NSFW config from YAML file with hardcoded fallback.

    Args:
        profile: Config profile name ("production" or "experimental").

    Returns:
        NSFWConfig with prompt, negative, and loras loaded from YAML.
    """
    yaml_path = _CONFIGS_DIR / f"nsfw_{profile}.yaml"
    if not yaml_path.exists():
        logger.warning("Config file not found: %s, using hardcoded defaults", yaml_path)
        return _HARDCODED_DEFAULTS.get(profile, _HARDCODED_DEFAULTS["production"])

    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to load %s: %s, using hardcoded defaults", yaml_path, exc)
        return _HARDCODED_DEFAULTS.get(profile, _HARDCODED_DEFAULTS["production"])

    nsfw = data.get("nsfw", {})
    inpaint = data.get("inpaint", {})
    loras_raw = data.get("loras", [])
    loras = [_make_lora(l["model"], l["weight"], l.get("enabled", True)) for l in loras_raw]
    defaults = _HARDCODED_DEFAULTS.get(profile, _HARDCODED_DEFAULTS["production"])

    return NSFWConfig(
        prompt=nsfw.get("prompt", defaults.prompt).strip(),
        negative=nsfw.get("negative", defaults.negative).strip(),
        loras=loras or defaults.loras,
        max_attempts=inpaint.get("max_attempts", defaults.max_attempts),
        base_strength=inpaint.get("base_strength", defaults.base_strength),
        inpaint_respective_field=inpaint.get("inpaint_respective_field", defaults.inpaint_respective_field),
        ip_adapter_faceid_weight=inpaint.get("ip_adapter_faceid_weight", defaults.ip_adapter_faceid_weight),
        base_model=inpaint.get("base_model", defaults.base_model),
    )


# ─── Shared Constants ────────────────────────────────────────────────────────

CLOTHES_CLASSES = (
    "spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, "
    "clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, "
    "coat, hoodie, t-shirt"
)

DEFAULT_CLOTHES_NEGATIVE = (
    "clothes, fabric, bra, straps, underwear, top, blouse, shirt, "
    "dress, skirt, pattern, floral, textile, garment, "
    "text, watermark, deformed, blurry, cartoon, anime, painting, CGI, "
    "extra limbs, disfigured, poorly drawn face, mutated hands, "
    "bad anatomy, deformed skin, wrinkled, scarred"
)


# ─── NSFW Prompt ─────────────────────────────────────────────────────────────

NSFW_PROMPT = (
    "NSFW, NSFW, NSFW, NSFW, NSFW, solo, bare skin, no clothing, naked body, "
    "detailed breast anatomy, realistic nipples, areola details, "
    "natural skin pores, skin texture, skin imperfections, "
    "realistic body proportions, maintaining exact same body posture, "
    "keeping original body position, not moving, not rotating, same stance, identical pose, "
    "skin tone matching the person's arms and face, consistent skin color throughout, "
    "seamless skin transition, matching skin tone with surrounding body, "
    "ultra realistic photograph, DSLR photo, natural skin subsurface scattering, "
    "studio lighting, soft shadows, film grain, 8k uhd, "
    "sharp focus on body, high resolution, professional photography, "
    "skin pores visible, micro details on skin, lifelike skin translucency"
)

NSFW_NEGATIVE = (
    "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, "
    "wrong anatomy, extra limbs, missing limbs, floating limbs, severed limbs, "
    "(mutated hands and fingers, extra fingers, missing fingers, webbed fingers:1.4), "
    "(bad hands, poorly drawn hands, fused fingers, too many fingers:1.3), "
    "(extra face, second face, face on body, face on chest, face below neck:1.8), "
    "(facial features on torso, eyes on chest, mouth on body:1.6), "
    "long neck, mutation, ugly, blurry, airbrushed, plastic skin, CGI, 3D, render, "
    "clothes, fabric, bra, straps, underwear, pattern, floral, textile, "
    "cartoon, anime, sketch, "
    "(changed pose, moved body, different position, rotated torso:1.5), "
    "(shifted weight, leaning, tilting, bending, twisting:1.4), "
    "(new angle, different posture:1.3), "
    "asymmetric nipples, mismatched skin tone, color banding"
)


# ─── LoRA Configurations ─────────────────────────────────────────────────────

def _make_lora(model: str, weight: float, enabled: bool = True) -> dict:
    """Create a LoRA entry dict."""
    return {"enabled": enabled, "model_name": model, "weight": weight}


# Hardcoded defaults — used when YAML config files are missing.
_HARDCODED_DEFAULTS: dict[str, NSFWConfig] = {
    "production": NSFWConfig(
        prompt=NSFW_PROMPT,
        negative=NSFW_NEGATIVE,
        loras=[
            _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.6),
            _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
            _make_lora("add-detail-xl.safetensors", 0.7),
            _make_lora("None", 1.0),
            _make_lora("None", 1.0),
        ],
        max_attempts=5,
        base_strength=0.86,
        inpaint_respective_field=0.618,
        ip_adapter_faceid_weight=0.8,
        base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
    ),
    "experimental": NSFWConfig(
        prompt=NSFW_PROMPT,
        negative=NSFW_NEGATIVE,
        loras=[
            _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.3),
            _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
            _make_lora("add-detail-xl.safetensors", 1.0),
            _make_lora("None", 1.0),
            _make_lora("None", 1.0),
        ],
        max_attempts=5,
        base_strength=0.86,
        inpaint_respective_field=0.55,
        ip_adapter_faceid_weight=0.8,
        base_model="lustifySDXLNSFW_v20-inpainting.safetensors",
    ),
}

# Clothes removal LoRAs — lighter NSFW effect for /jobs route (non-NSFW).
LORAS_CLOTHES = [
    _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.2),
    _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
    _make_lora("add-detail-xl.safetensors", 0.8),
    _make_lora("None", 1.0),
    _make_lora("None", 1.0),
]


def get_nsfw_config(profile: str) -> NSFWConfig:
    """Get NSFW config for given profile. Loads from YAML, falls back to hardcoded."""
    return _load_nsfw_config(profile)


# ─── Scoring Weights ─────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ScoringWeights:
    """Weights for composite scoring (lower score = better)."""
    skin: float = 0.40
    head: float = 0.20
    landmark: float = 0.30
    clothes: float = 0.10
    early_stop: float = 5.0


SCORING = ScoringWeights()


# ─── Base64 / Image Helpers ──────────────────────────────────────────────────

def decode_image(image_input: str) -> bytes:
    """Decode image from URL, data URI, or raw base64."""
    if image_input.startswith(("http://", "https://")):
        import httpx
        resp = httpx.get(image_input, timeout=30)
        resp.raise_for_status()
        return resp.content
    if "," in image_input and image_input.startswith("data:"):
        image_input = image_input.split(",", 1)[1]
    return base64.b64decode(fix_b64_padding(image_input))


def to_data_uri(b64_str: str, mime: str = "image/png") -> str:
    """Wrap base64 string as data URI."""
    if b64_str.startswith("data:"):
        return b64_str
    return f"data:{mime};base64,{b64_str}"


def strip_data_uri(data_uri: str) -> str:
    """Remove data URI prefix, return raw base64."""
    if "," in data_uri and data_uri.startswith("data:"):
        return data_uri.split(",", 1)[1]
    return data_uri


def fix_b64_padding(s: str) -> str:
    """Fix base64 padding if missing."""
    missing = len(s) % 4
    if missing:
        s += "=" * (4 - missing)
    return s


# ─── Mask Helpers ────────────────────────────────────────────────────────────

def combine_masks(masks: list[str], orig_h: int, orig_w: int):
    """Combine multiple base64 masks into a single binary mask."""
    import cv2 as _cv2
    import numpy as _np
    combined = None
    for mb in masks:
        raw = strip_data_uri(mb)
        c_bytes = base64.b64decode(fix_b64_padding(raw))
        cm = _cv2.imdecode(_np.frombuffer(c_bytes, _np.uint8), _cv2.IMREAD_GRAYSCALE)
        if cm is None:
            continue
        if cm.shape[:2] != (orig_h, orig_w):
            cm = _cv2.resize(cm, (orig_w, orig_h))
        cb = (cm > 127).astype(_np.uint8) * 255
        combined = cb if combined is None else _cv2.bitwise_or(combined, cb)
    return combined


# ─── Skin Detection ──────────────────────────────────────────────────────────

def detect_skin_hsv(img) -> float:
    """Detect skin exposure using HSV color range (local, fast, no SE10).

    Returns skin_pct (0.0-100.0) — percentage of image pixels classified as skin.
    HSV range tuned for diverse skin tones:
      H: 0-30 (warm hues)
      S: 15-170 (moderate saturation — excludes white/grey)
      V: 60-255 (excludes very dark shadows)
    """
    import cv2 as _cv2
    import numpy as _np
    hsv = _cv2.cvtColor(img, _cv2.COLOR_BGR2HSV)
    lower_skin = _np.array([0, 15, 60], dtype=_np.uint8)
    upper_skin = _np.array([30, 170, 255], dtype=_np.uint8)
    skin_mask = _cv2.inRange(hsv, lower_skin, upper_skin)
    kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (5, 5))
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_OPEN, kernel, iterations=1)
    skin_mask = _cv2.morphologyEx(skin_mask, _cv2.MORPH_CLOSE, kernel, iterations=2)
    return float((skin_mask > 0).sum() / skin_mask.size * 100)


# ─── Composite Scoring ──────────────────────────────────────────────────────

def compute_composite_score(
    skin_ratio: float,
    head_avg: float,
    clothes_pct: float,
    max_landmark: float,
) -> float:
    """Compute composite score from four metrics (lower = better).

    skin_ratio: result_skin_pct / original_skin_pct (>1.0 = more skin = GOOD)
                We use (1 - ratio) so that more skin → lower score → better.
    head_avg:   face landmark drift (lower = better)
    clothes_pct: residual clothing (lower = better)
    max_landmark: worst landmark drift (lower = better)
    """
    skin_score = 1.0 - skin_ratio
    head_clamped = min(head_avg, 100.0)
    clothes_clamped = min(clothes_pct, 100.0)
    landmark_clamped = min(max_landmark, 100.0)
    score = (
        SCORING.skin * skin_score +
        SCORING.head * head_clamped +
        SCORING.landmark * landmark_clamped +
        SCORING.clothes * clothes_clamped
    )
    return round(score, 3)


# ─── Person Detection with Fallbacks ─────────────────────────────────────────

async def detect_person_with_fallbacks(
    se10,
    image_bytes: bytes,
    job_id: str,
    orig_h: int,
    orig_w: int,
    include_pose: bool = True,
) -> tuple["_np.ndarray | None", dict | None, str | None]:
    """Detect person mask with 3 fallback strategies.

    Returns (person_binary, person_seg, pose_cn_b64) or (None, None, None) if no person.
    """
    import cv2 as _cv2
    import numpy as _np

    # Primary detection
    person_seg = await se10.segment(
        image_bytes=image_bytes, filename=f"{job_id}_person.jpg",
        classes="person, woman, man", box_threshold=0.20, text_threshold=0.15,
        mode="person", detector="ensemble", include_pose=include_pose,
    )
    pose_cn_b64 = person_seg.get("controlnet_image") if include_pose else None

    if not person_seg.get("detected") or not person_seg.get("masks"):
        return None, None, None

    best_idx = max(range(len(person_seg["objects"])),
                   key=lambda i: person_seg["objects"][i].get("area_pct", 0))
    raw_p = strip_data_uri(person_seg["masks"][best_idx])
    person_mask = _cv2.imdecode(
        _np.frombuffer(base64.b64decode(fix_b64_padding(raw_p)), _np.uint8),
        _cv2.IMREAD_GRAYSCALE)
    if person_mask is None:
        return None, None, None
    if person_mask.shape[:2] != (orig_h, orig_w):
        person_mask = _cv2.resize(person_mask, (orig_w, orig_h))
    person_binary = (person_mask > 127).astype(_np.uint8) * 255

    # Fill ALL internal holes — multi-step approach
    close_kernel = _cv2.getStructuringElement(_cv2.MORPH_ELLIPSE, (7, 7))
    person_binary = _cv2.morphologyEx(person_binary, _cv2.MORPH_CLOSE, close_kernel, iterations=3)

    # FloodFill from ALL 4 corners + midpoints to catch background pockets
    _h, _w = person_binary.shape
    _flood = person_binary.copy()
    _flood_mask = _np.zeros((_h + 2, _w + 2), _np.uint8)
    seeds = [(0, 0), (_w - 1, 0), (0, _h - 1), (_w - 1, _h - 1),
             (_w // 2, 0), (_w // 2, _h - 1), (0, _h // 2), (_w - 1, _h // 2)]
    for seed in seeds:
        sx, sy = seed
        if 0 <= sx < _w and 0 <= sy < _h and _flood[sy, sx] == 0:
            _cv2.floodFill(_flood, _flood_mask, (sx, sy), 255)
    _holes = _cv2.bitwise_not(_flood)
    person_binary = _cv2.bitwise_or(person_binary, _holes)

    person_coverage = (person_binary > 0).sum() / person_binary.size * 100

    # Fallback 1: Retry with lower thresholds
    if person_coverage < 10.0:
        logger.warning("Job %s: person coverage %.1f%% < 10%%, retrying with lower thresholds",
                       job_id, person_coverage)
        person_seg_retry = await se10.segment(
            image_bytes=image_bytes, filename=f"{job_id}_person_retry.jpg",
            classes="person, woman, man", box_threshold=0.10, text_threshold=0.08,
            mode="person", detector="ensemble", include_pose=include_pose,
        )
        if person_seg_retry.get("detected") and person_seg_retry.get("masks"):
            best_idx_r = max(range(len(person_seg_retry["objects"])),
                             key=lambda i: person_seg_retry["objects"][i].get("area_pct", 0))
            raw_pr = strip_data_uri(person_seg_retry["masks"][best_idx_r])
            person_mask_r = _cv2.imdecode(
                _np.frombuffer(base64.b64decode(fix_b64_padding(raw_pr)), _np.uint8),
                _cv2.IMREAD_GRAYSCALE)
            if person_mask_r is not None:
                if person_mask_r.shape[:2] != (orig_h, orig_w):
                    person_mask_r = _cv2.resize(person_mask_r, (orig_w, orig_h))
                person_binary_r = (person_mask_r > 127).astype(_np.uint8) * 255
                retry_coverage = (person_binary_r > 0).sum() / person_binary_r.size * 100
                if retry_coverage > person_coverage:
                    person_binary = person_binary_r
                    person_seg = person_seg_retry
                    if include_pose and person_seg_retry.get("controlnet_image"):
                        pose_cn_b64 = person_seg_retry["controlnet_image"]
                    person_coverage = retry_coverage

    # Fallback 2: GrabCut
    if person_coverage < 10.0:
        logger.warning("Job %s: still low coverage %.1f%%, trying GrabCut", job_id, person_coverage)
        person_binary = _grabcut_fallback(person_binary, orig_h, orig_w)
        person_coverage = (person_binary > 0).sum() / person_binary.size * 100

    # Fallback 3: Face-ellipse
    if person_coverage < 10.0:
        logger.warning("Job %s: still low coverage %.1f%%, trying face-ellipse", job_id, person_coverage)
        person_binary = _face_ellipse_fallback(orig_h, orig_w)
        person_coverage = (person_binary > 0).sum() / person_binary.size * 100

    return person_binary, person_seg, pose_cn_b64


def _grabcut_fallback(person_binary: "_np.ndarray", orig_h: int, orig_w: int) -> "_np.ndarray":
    """GrabCut fallback for person detection."""
    import cv2 as _cv2
    import numpy as _np

    try:
        from app.services.head_detector import _detect_faces
        faces = _detect_faces(_np.zeros((orig_h, orig_w, 3), _np.uint8))
    except Exception:
        faces = []

    if not faces:
        return person_binary

    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face
    gc_margin_x = int(fw * 3.0)
    gc_margin_top = int(fh * 4.0)
    gc_margin_bot = int(fh * 6.0)
    gc_x1 = max(0, fx - gc_margin_x)
    gc_y1 = max(0, fy - gc_margin_top)
    gc_x2 = min(orig_w, fx + fw + gc_margin_x)
    gc_y2 = min(orig_h, fy + fh + gc_margin_bot)
    gc_rect = (gc_x1, gc_y1, gc_x2 - gc_x1, gc_y2 - gc_y1)

    gc_mask = _np.zeros((orig_h, orig_w), _np.uint8)
    gc_mask[:] = _cv2.GC_PR_FGD
    border = 5
    gc_mask[:border, :] = _cv2.GC_PR_BGD
    gc_mask[-border:, :] = _cv2.GC_PR_BGD
    gc_mask[:, :border] = _cv2.GC_PR_BGD
    gc_mask[:, -border:] = _cv2.GC_PR_BGD

    bgd_model = _np.zeros((1, 65), _np.float64)
    fgd_model = _np.zeros((1, 65), _np.float64)
    try:
        _cv2.grabCut(_np.zeros((orig_h, orig_w, 3), _np.uint8), gc_mask, gc_rect,
                     bgd_model, fgd_model, 5, _cv2.GC_INIT_WITH_RECT)
        gc_fg = _np.where((gc_mask == _cv2.GC_FGD) | (gc_mask == _cv2.GC_PR_FGD), 255, 0).astype(_np.uint8)
        gc_coverage = (gc_fg > 0).sum() / gc_fg.size * 100
        if gc_coverage > (person_binary > 0).sum() / person_binary.size * 100:
            return gc_fg
    except Exception:
        pass
    return person_binary


def _face_ellipse_fallback(orig_h: int, orig_w: int) -> "_np.ndarray":
    """Face-ellipse fallback for person detection."""
    import cv2 as _cv2
    import numpy as _np

    try:
        from app.services.head_detector import _detect_faces
        faces = _detect_faces(_np.zeros((orig_h, orig_w, 3), _np.uint8))
    except Exception:
        faces = []

    if not faces:
        return _np.zeros((orig_h, orig_w), _np.uint8)

    face = max(faces, key=lambda f: f[2] * f[3])
    fx, fy, fw, fh = face
    body_w = int(fw * 4.0)
    body_h = int(fh * 8.0)
    body_cx = fx + fw // 2
    body_cy = fy + fh + body_h // 2
    body_x1 = max(0, body_cx - body_w // 2)
    body_y1 = max(0, fy - int(fh * 1.5))
    body_x2 = min(orig_w, body_cx + body_w // 2)
    body_y2 = min(orig_h, body_cy + body_h // 2)

    body_mask = _np.zeros((orig_h, orig_w), _np.uint8)
    ell_cx = (body_x1 + body_x2) // 2
    ell_cy = (body_y1 + body_y2) // 2
    ell_w = (body_x2 - body_x1) // 2
    ell_h = (body_y2 - body_y1) // 2
    _cv2.ellipse(body_mask, (ell_cx, ell_cy), (ell_w, ell_h), 0, 0, 360, 255, -1)
    return body_mask


# ─── SE8 Upscale Helper ──────────────────────────────────────────────────────

async def upscale_result(se8, img, logger_ref=None) -> "_np.ndarray | None":
    """Upscale image via SE8 4x-UltraSharp. Returns upscaled image or None."""
    import cv2 as _cv2
    import numpy as _np

    try:
        _, buf = _cv2.imencode(".png", img)
        b64 = to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")
        result = await se8.upscale(image_b64=b64, scale=2.0)
        if result and result.get("base64"):
            upscaled_b64 = result["base64"]
            if "," in upscaled_b64 and upscaled_b64.startswith("data:"):
                upscaled_b64 = upscaled_b64.split(",", 1)[1]
            upscaled_b64 = fix_b64_padding(upscaled_b64)
            upscaled_bytes = base64.b64decode(upscaled_b64)
            upscaled_img = _cv2.imdecode(_np.frombuffer(upscaled_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            if upscaled_img is not None:
                return upscaled_img
    except Exception as exc:
        if logger_ref:
            logger_ref.warning("Upscale failed: %s", exc)
    return None


# ─── SE8 Face Restore Helper ─────────────────────────────────────────────────

async def restore_face(se8, img, model: str = "CodeFormer", fidelity: float = 0.5,
                       logger_ref=None) -> "_np.ndarray | None":
    """Restore face via SE8. Returns restored image or None."""
    import cv2 as _cv2
    import numpy as _np

    try:
        _, buf = _cv2.imencode(".png", img)
        b64 = to_data_uri(base64.b64encode(buf).decode("utf-8"), mime="image/png")
        result = await se8.restore_face(image_b64=b64, model=model, fidelity=fidelity)
        if result and result.get("base64"):
            restored_b64 = result["base64"]
            if "," in restored_b64 and restored_b64.startswith("data:"):
                restored_b64 = restored_b64.split(",", 1)[1]
            restored_bytes = base64.b64decode(restored_b64)
            restored_img = _cv2.imdecode(_np.frombuffer(restored_bytes, _np.uint8), _cv2.IMREAD_COLOR)
            if restored_img is not None:
                return restored_img
    except Exception as exc:
        if logger_ref:
            logger_ref.warning("Face restore failed: %s", exc)
    return None
