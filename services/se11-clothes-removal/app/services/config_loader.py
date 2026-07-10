"""YAML configuration loader for NSFW and Clothes pipelines."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIGS_DIR = Path(__file__).resolve().parent.parent.parent / "configs"


@dataclass(frozen=True)
class NSFWConfig:
    """Immutable NSFW pipeline configuration loaded from YAML."""
    prompt: str
    negative: str
    loras: list[dict]
    max_attempts: int = 5
    base_strength: float = 0.86
    strength_step: float = 0.03
    strength_ceiling: float = 0.92
    inter_attempt_delay: int = 10
    inter_attempt_multiplier: bool = False
    inpaint_respective_field: float = 0.618
    ip_adapter_faceid_weight: float = 0.8
    base_model: str = "lustifySDXLNSFW_v20-inpainting.safetensors"
    head_threshold_pct: float = 1.5
    torso_threshold_pct: float = 8.0
    limbs_threshold_pct: float = 5.0
    hands_threshold_pct: float = 5.0
    ip_image_prompt_cn_stop: float = 0.5
    ip_image_prompt_cn_weight: float = 0.8
    ip_openpose_cn_stop: float = 0.7
    ip_openpose_cn_weight: float = 0.3
    hd_max_head_pct: float = 0.50
    hd_neck_margin_below: float = 0.3
    hd_dilate_kernel_size: int = 25
    hd_dilate_iterations: int = 3
    hd_expand_up: float = 2.5
    hd_expand_w: float = 0.5
    fp_margin_above: float = 0.50
    fp_margin_below: float = 0.70
    fp_margin_sides: float = 0.40
    fp_dilation_pct: float = 0.03
    fp_feather_bottom_px: int = 25
    scoring_skin_weight: float = 0.40
    scoring_head_weight: float = 0.20
    scoring_landmark_weight: float = 0.30
    scoring_clothes_weight: float = 0.10
    scoring_early_stop: float = 5.0
    se8_performance_selection: str = "Quality"
    se8_sharpness: float = 2.0
    se8_guidance_scale: float = 7.0
    se8_inpaint_engine: str = "v2.6"
    se8_overwrite_step: int = 50
    se8_overwrite_switch: float = 1.0
    se8_adaptive_cfg: float = 7.0
    se8_sampler_name: str = "dpmpp_2m_sde_gpu"
    se8_scheduler_name: str = "karras"
    se8_refiner_switch: float = 0.5
    se8_retry_max_attempts: int = 3
    se8_retry_base_wait: int = 5
    enhance_performance_selection: str = "Speed"
    enhance_guidance_scale: float = 4.0
    enhance_aspect_ratios_selection: str = "1152*896"
    progressive_passes_clothes: list[dict] = field(default_factory=list)
    progressive_passes_person: list[dict] = field(default_factory=list)
    clothes_classes: str = "spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt"
    best_clothing_classes: str = "spaghetti strap, camisole, top, blouse"
    sd_hsv_lower: list[int] = field(default_factory=lambda: [0, 15, 60])
    sd_hsv_upper: list[int] = field(default_factory=lambda: [30, 170, 255])
    sd_morph_kernel_size: int = 5
    sd_open_iterations: int = 1
    sd_close_iterations: int = 2
    im_person_box_threshold: float = 0.20
    im_person_text_threshold: float = 0.15
    im_clothes_text_threshold: float = 0.05
    im_min_area_pct: float = 0.1
    im_min_confidence: float = 0.10
    im_max_objects: int = 3
    im_bottom_edge_pct: float = 0.95
    im_bottom_edge_min_area: float = 1.0
    im_dilate_kernel_size: int = 21
    im_dilate_iterations: int = 2
    im_erode_kernel_size: int = 15
    im_erode_iterations: int = 2
    im_face_region_pct: float = 0.30
    im_face_coverage_threshold: float = 5.0
    im_min_torso_coverage: float = 1.0
    im_low_coverage_threshold: float = 5.0
    im_strength_person: float = 0.70
    im_strength_clothes: float = 0.70
    im_respective_field: float = 0.618
    im_erode_or_dilate_progressive: int = -10
    im_erode_dilate_thresholds: list[dict] = field(default_factory=lambda: [
        {"min_pct": 50.0, "value": -5},
        {"min_pct": 30.0, "value": -8},
        {"min_pct": 15.0, "value": -10},
        {"min_pct": 5.0, "value": -15},
        {"min_pct": 0.0, "value": -20},
    ])
    im_mask_cap_threshold_pct: float = 15.0
    im_mask_cap_max_erode: int = -30
    im_mask_cap_erode_scale: int = 3
    im_mask_cap_min_erode_kernel: int = 15
    cg_close_kernel_size: int = 100
    cg_close_iterations: int = 1

    def se8_advanced_params(self) -> dict:
        """Return SE8 advanced_params dict for http_client.inpaint()."""
        return {
            "inpaint_engine": self.se8_inpaint_engine,
            "inpaint_strength": 0.0,
            "inpaint_respective_field": 0.0,
            "inpaint_disable_initial_latent": False,
            "inpaint_erode_or_dilate": 0,
            "overwrite_step": self.se8_overwrite_step,
            "overwrite_switch": self.se8_overwrite_switch,
            "adaptive_cfg": self.se8_adaptive_cfg,
            "sampler_name": self.se8_sampler_name,
            "scheduler_name": self.se8_scheduler_name,
        }


@dataclass(frozen=True)
class ClothesConfig:
    """Immutable clothes removal pipeline configuration loaded from YAML."""
    clothes_prompt: str
    person_prompt: str
    clothes_negative: str
    loras: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class ScoringWeights:
    """Weights for composite scoring (lower score = better)."""
    skin: float = 0.40
    head: float = 0.20
    landmark: float = 0.30
    clothes: float = 0.10
    early_stop: float = 5.0


DEFAULT_BASE_MODEL = "lustifySDXLNSFW_v20-inpainting.safetensors"

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


def _make_lora(model: str, weight: float, enabled: bool = True) -> dict:
    """Create a LoRA entry dict."""
    return {"enabled": enabled, "model_name": model, "weight": weight}


_CLOTHES_DEFAULTS: dict[str, ClothesConfig] = {
    "production": ClothesConfig(
        clothes_prompt=(
            "NSFW, NSFW, NSFW, NSFW, NSFW, "
            "bare skin, smooth skin surface, realistic skin texture, "
            "detailed breast anatomy, realistic nipples, natural skin pores, "
            "seamless skin transition, consistent skin tone with surrounding body, "
            "photorealistic, professional photography, studio lighting, "
            "high resolution, sharp focus on skin detail, 8k uhd, "
            "hyperrealistic, detailed skin rendering, natural body proportions"
        ),
        person_prompt=(
            "natural skin texture matching surrounding skin tone, seamless blend, "
            "preserve original body shape and features, realistic skin, soft lighting"
        ),
        clothes_negative=DEFAULT_CLOTHES_NEGATIVE,
        loras=[
            _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.2),
            _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
            _make_lora("add-detail-xl.safetensors", 0.8),
            _make_lora("None", 1.0),
            _make_lora("None", 1.0),
        ],
    ),
}
_CLOTHES_DEFAULTS["experimental"] = _CLOTHES_DEFAULTS["production"]


_HARDCODED_DEFAULTS: dict[str, NSFWConfig] = {
    "production": NSFWConfig(
        prompt=NSFW_PROMPT, negative=NSFW_NEGATIVE,
        loras=[
            _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.6),
            _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
            _make_lora("add-detail-xl.safetensors", 0.7),
            _make_lora("None", 1.0), _make_lora("None", 1.0),
        ],
        max_attempts=5, base_strength=0.86, strength_step=0.03,
        inter_attempt_delay=10, inter_attempt_multiplier=False,
        inpaint_respective_field=0.618, ip_adapter_faceid_weight=0.8,
        base_model=DEFAULT_BASE_MODEL,
        head_threshold_pct=1.5, torso_threshold_pct=8.0,
        limbs_threshold_pct=5.0, hands_threshold_pct=5.0,
        ip_image_prompt_cn_stop=0.5, ip_image_prompt_cn_weight=0.8,
        ip_openpose_cn_stop=0.7, ip_openpose_cn_weight=0.3,
        hd_max_head_pct=0.50, hd_neck_margin_below=0.3,
        hd_dilate_kernel_size=25, hd_dilate_iterations=3,
        hd_expand_up=2.5, hd_expand_w=0.5,
        fp_margin_above=0.50, fp_margin_below=0.70, fp_margin_sides=0.40,
        fp_dilation_pct=0.02, fp_feather_bottom_px=25,
        scoring_skin_weight=0.40, scoring_head_weight=0.20,
        scoring_landmark_weight=0.30, scoring_clothes_weight=0.10,
        scoring_early_stop=5.0,
        sd_hsv_lower=[0, 15, 60], sd_hsv_upper=[30, 170, 255],
        sd_morph_kernel_size=5, sd_open_iterations=1, sd_close_iterations=2,
        se8_performance_selection="Quality", se8_sharpness=2.0,
        se8_guidance_scale=7.0, se8_inpaint_engine="v2.6",
        se8_overwrite_step=50, se8_overwrite_switch=1.0,
        se8_adaptive_cfg=7.0, se8_sampler_name="dpmpp_2m_sde_gpu",
        se8_scheduler_name="karras", se8_refiner_switch=0.5,
        se8_retry_max_attempts=3, se8_retry_base_wait=5,
        enhance_performance_selection="Speed", enhance_guidance_scale=4.0,
        enhance_aspect_ratios_selection="1152*896",
        progressive_passes_clothes=[
            {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.65, "detector": "segformer", "name": "straps", "se_mode": "clothes"},
            {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.60, "detector": "segformer", "name": "top", "se_mode": "clothes"},
            {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.55, "detector": "segformer", "name": "full", "se_mode": "clothes"},
            {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.50, "detector": "segformer", "name": "cleanup", "se_mode": "clothes"},
        ],
        progressive_passes_person=[
            {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.70, "detector": "segformer", "name": "straps", "se_mode": "clothes"},
            {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.65, "detector": "segformer", "name": "top", "se_mode": "clothes"},
            {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.60, "detector": "segformer", "name": "full", "se_mode": "clothes"},
            {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.55, "detector": "segformer", "name": "cleanup", "se_mode": "clothes"},
        ],
        clothes_classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
        best_clothing_classes="spaghetti strap, camisole, top, blouse",
    ),
    "experimental": NSFWConfig(
        prompt=NSFW_PROMPT, negative=NSFW_NEGATIVE,
        loras=[
            _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.3),
            _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
            _make_lora("add-detail-xl.safetensors", 1.0),
            _make_lora("None", 1.0), _make_lora("None", 1.0),
        ],
        max_attempts=5, base_strength=0.86, strength_step=0.03,
        inter_attempt_delay=3, inter_attempt_multiplier=True,
        inpaint_respective_field=0.55, ip_adapter_faceid_weight=0.8,
        base_model=DEFAULT_BASE_MODEL,
        head_threshold_pct=3.0, torso_threshold_pct=8.0,
        limbs_threshold_pct=30.0, hands_threshold_pct=30.0,
        ip_image_prompt_cn_stop=0.5, ip_image_prompt_cn_weight=0.8,
        ip_openpose_cn_stop=0.6, ip_openpose_cn_weight=0.3,
        hd_max_head_pct=0.50, hd_neck_margin_below=0.3,
        hd_dilate_kernel_size=25, hd_dilate_iterations=3,
        hd_expand_up=2.5, hd_expand_w=0.5,
        fp_margin_above=0.50, fp_margin_below=0.70, fp_margin_sides=0.40,
        fp_dilation_pct=0.02, fp_feather_bottom_px=25,
        scoring_skin_weight=0.40, scoring_head_weight=0.20,
        scoring_landmark_weight=0.30, scoring_clothes_weight=0.10,
        scoring_early_stop=5.0,
        sd_hsv_lower=[0, 15, 60], sd_hsv_upper=[30, 170, 255],
        sd_morph_kernel_size=5, sd_open_iterations=1, sd_close_iterations=2,
        se8_performance_selection="Quality", se8_sharpness=2.0,
        se8_guidance_scale=7.0, se8_inpaint_engine="v2.6",
        se8_overwrite_step=50, se8_overwrite_switch=1.0,
        se8_adaptive_cfg=7.0, se8_sampler_name="dpmpp_2m_sde_gpu",
        se8_scheduler_name="karras", se8_refiner_switch=0.5,
        se8_retry_max_attempts=3, se8_retry_base_wait=5,
        enhance_performance_selection="Speed", enhance_guidance_scale=4.0,
        enhance_aspect_ratios_selection="1152*896",
        progressive_passes_clothes=[
            {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.65, "detector": "segformer", "name": "straps", "se_mode": "clothes"},
            {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.60, "detector": "segformer", "name": "top", "se_mode": "clothes"},
            {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.55, "detector": "segformer", "name": "full", "se_mode": "clothes"},
            {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.50, "detector": "segformer", "name": "cleanup", "se_mode": "clothes"},
        ],
        progressive_passes_person=[
            {"classes": "spaghetti strap, camisole", "box_threshold": 0.06, "text_threshold": 0.04, "inpaint_strength": 0.70, "detector": "segformer", "name": "straps", "se_mode": "clothes"},
            {"classes": "top, blouse, shirt", "box_threshold": 0.08, "text_threshold": 0.05, "inpaint_strength": 0.65, "detector": "segformer", "name": "top", "se_mode": "clothes"},
            {"classes": "dress, clothing, garment", "box_threshold": 0.10, "text_threshold": 0.07, "inpaint_strength": 0.60, "detector": "segformer", "name": "full", "se_mode": "clothes"},
            {"classes": "fabric, textile, outfit", "box_threshold": 0.12, "text_threshold": 0.09, "inpaint_strength": 0.55, "detector": "segformer", "name": "cleanup", "se_mode": "clothes"},
        ],
        clothes_classes="spaghetti strap, camisole, top, blouse, shirt, dress, bra, underwear, clothing, garment, skirt, pants, shorts, jeans, sweater, jacket, coat, hoodie, t-shirt",
        best_clothing_classes="spaghetti strap, camisole, top, blouse",
    ),
}

LORAS_CLOTHES = [
    _make_lora("NsfwPovAllInOneLoraSdxl-000009.safetensors", 0.2),
    _make_lora("sd_xl_offset_example-lora_1.0.safetensors", 0.1),
    _make_lora("add-detail-xl.safetensors", 0.8),
    _make_lora("None", 1.0),
    _make_lora("None", 1.0),
]


def _load_nsfw_config(profile: str) -> NSFWConfig:
    """Load NSFW config from YAML file with hardcoded fallback."""
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
    pose = data.get("pose_thresholds", {})
    ip = data.get("ip_adapter", {})
    hd = data.get("head_detection", {})
    fp = data.get("face_protection", {})
    sc = data.get("scoring", {})
    se8 = data.get("se8_params", {})
    se8r = data.get("se8_retry", {})
    enh = data.get("enhance", {})
    loras_raw = data.get("loras", [])
    loras = [_make_lora(l["model"], l["weight"], l.get("enabled", True)) for l in loras_raw]
    pp = data.get("progressive_passes", {})
    sd = data.get("skin_detection", {})
    im = data.get("inline_mode", {})
    im_pd = im.get("person_detection", {})
    im_cd = im.get("clothes_detection", {})
    im_of = im.get("object_filter", {})
    im_mp = im.get("mask_params", {})
    im_ip = im.get("inpaint", {})
    im_ed = im.get("erode_dilate_thresholds", [])
    im_mc = im.get("mask_cap", {})
    cg = data.get("clothing_gap", {})
    defaults = _HARDCODED_DEFAULTS.get(profile, _HARDCODED_DEFAULTS["production"])

    return NSFWConfig(
        prompt=nsfw.get("prompt", defaults.prompt).strip(),
        negative=nsfw.get("negative", defaults.negative).strip(),
        loras=loras or defaults.loras,
        max_attempts=inpaint.get("max_attempts", defaults.max_attempts),
        base_strength=inpaint.get("base_strength", defaults.base_strength),
        strength_step=inpaint.get("strength_step", defaults.strength_step),
        strength_ceiling=inpaint.get("strength_ceiling", defaults.strength_ceiling),
        inter_attempt_delay=inpaint.get("inter_attempt_delay", defaults.inter_attempt_delay),
        inter_attempt_multiplier=inpaint.get("inter_attempt_multiplier", defaults.inter_attempt_multiplier),
        inpaint_respective_field=inpaint.get("inpaint_respective_field", defaults.inpaint_respective_field),
        ip_adapter_faceid_weight=inpaint.get("ip_adapter_faceid_weight", defaults.ip_adapter_faceid_weight),
        base_model=inpaint.get("base_model", defaults.base_model),
        head_threshold_pct=pose.get("head_threshold_pct", defaults.head_threshold_pct),
        torso_threshold_pct=pose.get("torso_threshold_pct", defaults.torso_threshold_pct),
        limbs_threshold_pct=pose.get("limbs_threshold_pct", defaults.limbs_threshold_pct),
        hands_threshold_pct=pose.get("hands_threshold_pct", defaults.hands_threshold_pct),
        ip_image_prompt_cn_stop=ip.get("image_prompt_cn_stop", defaults.ip_image_prompt_cn_stop),
        ip_image_prompt_cn_weight=ip.get("image_prompt_cn_weight", defaults.ip_image_prompt_cn_weight),
        ip_openpose_cn_stop=ip.get("openpose_cn_stop", defaults.ip_openpose_cn_stop),
        ip_openpose_cn_weight=ip.get("openpose_cn_weight", defaults.ip_openpose_cn_weight),
        hd_max_head_pct=hd.get("max_head_pct", defaults.hd_max_head_pct),
        hd_neck_margin_below=hd.get("neck_margin_below", defaults.hd_neck_margin_below),
        hd_dilate_kernel_size=hd.get("dilate_kernel_size", defaults.hd_dilate_kernel_size),
        hd_dilate_iterations=hd.get("dilate_iterations", defaults.hd_dilate_iterations),
        hd_expand_up=hd.get("expand_up", defaults.hd_expand_up),
        hd_expand_w=hd.get("expand_w", defaults.hd_expand_w),
        fp_margin_above=fp.get("margin_above", defaults.fp_margin_above),
        fp_margin_below=fp.get("margin_below", defaults.fp_margin_below),
        fp_margin_sides=fp.get("margin_sides", defaults.fp_margin_sides),
        fp_dilation_pct=fp.get("dilation_pct", defaults.fp_dilation_pct),
        fp_feather_bottom_px=fp.get("feather_bottom_px", defaults.fp_feather_bottom_px),
        scoring_skin_weight=sc.get("skin_weight", defaults.scoring_skin_weight),
        scoring_head_weight=sc.get("head_weight", defaults.scoring_head_weight),
        scoring_landmark_weight=sc.get("landmark_weight", defaults.scoring_landmark_weight),
        scoring_clothes_weight=sc.get("clothes_weight", defaults.scoring_clothes_weight),
        scoring_early_stop=sc.get("early_stop", defaults.scoring_early_stop),
        se8_performance_selection=se8.get("performance_selection", defaults.se8_performance_selection),
        se8_sharpness=se8.get("sharpness", defaults.se8_sharpness),
        se8_guidance_scale=se8.get("guidance_scale", defaults.se8_guidance_scale),
        se8_inpaint_engine=se8.get("inpaint_engine", defaults.se8_inpaint_engine),
        se8_overwrite_step=se8.get("overwrite_step", defaults.se8_overwrite_step),
        se8_overwrite_switch=se8.get("overwrite_switch", defaults.se8_overwrite_switch),
        se8_adaptive_cfg=se8.get("adaptive_cfg", defaults.se8_adaptive_cfg),
        se8_sampler_name=se8.get("sampler_name", defaults.se8_sampler_name),
        se8_scheduler_name=se8.get("scheduler_name", defaults.se8_scheduler_name),
        se8_refiner_switch=se8.get("refiner_switch", defaults.se8_refiner_switch),
        se8_retry_max_attempts=se8r.get("max_attempts", defaults.se8_retry_max_attempts),
        se8_retry_base_wait=se8r.get("base_wait", defaults.se8_retry_base_wait),
        enhance_performance_selection=enh.get("performance_selection", defaults.enhance_performance_selection),
        enhance_guidance_scale=enh.get("guidance_scale", defaults.enhance_guidance_scale),
        enhance_aspect_ratios_selection=enh.get("aspect_ratios_selection", defaults.enhance_aspect_ratios_selection),
        progressive_passes_clothes=pp.get("clothes", defaults.progressive_passes_clothes),
        progressive_passes_person=pp.get("person", defaults.progressive_passes_person),
        clothes_classes=data.get("clothes_classes", defaults.clothes_classes),
        best_clothing_classes=data.get("best_clothing_classes", defaults.best_clothing_classes),
        sd_hsv_lower=sd.get("hsv_lower", defaults.sd_hsv_lower),
        sd_hsv_upper=sd.get("hsv_upper", defaults.sd_hsv_upper),
        sd_morph_kernel_size=sd.get("morph_kernel_size", defaults.sd_morph_kernel_size),
        sd_open_iterations=sd.get("open_iterations", defaults.sd_open_iterations),
        sd_close_iterations=sd.get("close_iterations", defaults.sd_close_iterations),
        im_person_box_threshold=im_pd.get("box_threshold", defaults.im_person_box_threshold),
        im_person_text_threshold=im_pd.get("text_threshold", defaults.im_person_text_threshold),
        im_clothes_text_threshold=im_cd.get("text_threshold", defaults.im_clothes_text_threshold),
        im_min_area_pct=im_of.get("min_area_pct", defaults.im_min_area_pct),
        im_min_confidence=im_of.get("min_confidence", defaults.im_min_confidence),
        im_max_objects=im_of.get("max_objects", defaults.im_max_objects),
        im_bottom_edge_pct=im_of.get("bottom_edge_pct", defaults.im_bottom_edge_pct),
        im_bottom_edge_min_area=im_of.get("bottom_edge_min_area", defaults.im_bottom_edge_min_area),
        im_dilate_kernel_size=im_mp.get("dilate_kernel_size", defaults.im_dilate_kernel_size),
        im_dilate_iterations=im_mp.get("dilate_iterations", defaults.im_dilate_iterations),
        im_erode_kernel_size=im_mp.get("erode_kernel_size", defaults.im_erode_kernel_size),
        im_erode_iterations=im_mp.get("erode_iterations", defaults.im_erode_iterations),
        im_face_region_pct=im_mp.get("face_region_pct", defaults.im_face_region_pct),
        im_face_coverage_threshold=im_mp.get("face_coverage_threshold", defaults.im_face_coverage_threshold),
        im_min_torso_coverage=im_mp.get("min_torso_coverage", defaults.im_min_torso_coverage),
        im_low_coverage_threshold=im_mp.get("low_coverage_threshold", defaults.im_low_coverage_threshold),
        im_strength_person=im_ip.get("strength_person", defaults.im_strength_person),
        im_strength_clothes=im_ip.get("strength_clothes", defaults.im_strength_clothes),
        im_respective_field=im_ip.get("respective_field", defaults.im_respective_field),
        im_erode_or_dilate_progressive=im_ip.get("erode_or_dilate_progressive", defaults.im_erode_or_dilate_progressive),
        im_erode_dilate_thresholds=im_ed if im_ed else defaults.im_erode_dilate_thresholds,
        im_mask_cap_threshold_pct=im_mc.get("threshold_pct", defaults.im_mask_cap_threshold_pct),
        im_mask_cap_max_erode=im_mc.get("max_erode", defaults.im_mask_cap_max_erode),
        im_mask_cap_erode_scale=im_mc.get("erode_scale", defaults.im_mask_cap_erode_scale),
        im_mask_cap_min_erode_kernel=im_mc.get("min_erode_kernel", defaults.im_mask_cap_min_erode_kernel),
        cg_close_kernel_size=cg.get("close_kernel_size", defaults.cg_close_kernel_size),
        cg_close_iterations=cg.get("close_iterations", defaults.cg_close_iterations),
    )


def _load_clothes_config(profile: str) -> ClothesConfig:
    """Load clothes config from YAML file with hardcoded fallback."""
    yaml_path = _CONFIGS_DIR / f"nsfw_{profile}.yaml"
    if not yaml_path.exists():
        logger.warning("Clothes config file not found: %s, using hardcoded defaults", yaml_path)
        return _CLOTHES_DEFAULTS.get(profile, _CLOTHES_DEFAULTS["production"])

    try:
        import yaml
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning("Failed to load %s: %s, using hardcoded defaults", yaml_path, exc)
        return _CLOTHES_DEFAULTS.get(profile, _CLOTHES_DEFAULTS["production"])

    clothes = data.get("clothes", {})
    defaults = _CLOTHES_DEFAULTS.get(profile, _CLOTHES_DEFAULTS["production"])

    loras_raw = clothes.get("loras", [])
    loras = [_make_lora(l["model"], l["weight"], l.get("enabled", True)) for l in loras_raw] if loras_raw else defaults.loras

    return ClothesConfig(
        clothes_prompt=clothes.get("clothes_prompt", defaults.clothes_prompt).strip(),
        person_prompt=clothes.get("person_prompt", defaults.person_prompt).strip(),
        clothes_negative=clothes.get("clothes_negative", defaults.clothes_negative).strip(),
        loras=loras,
    )


def get_nsfw_config(profile: str) -> NSFWConfig:
    """Get NSFW config for given profile. Loads from YAML, falls back to hardcoded."""
    return _load_nsfw_config(profile)


def get_clothes_config(profile: str = "production") -> ClothesConfig:
    """Get clothes removal pipeline configuration."""
    return _load_clothes_config(profile)


def _build_scoring_from_config(cfg: NSFWConfig) -> ScoringWeights:
    """Build ScoringWeights from NSFWConfig."""
    return ScoringWeights(
        skin=cfg.scoring_skin_weight,
        head=cfg.scoring_head_weight,
        landmark=cfg.scoring_landmark_weight,
        clothes=cfg.scoring_clothes_weight,
        early_stop=cfg.scoring_early_stop,
    )


# Load defaults at module level
_nsfw_cfg_for_classes = get_nsfw_config("production")
CLOTHES_CLASSES = _nsfw_cfg_for_classes.clothes_classes
SCORING = _build_scoring_from_config(get_nsfw_config("production"))
