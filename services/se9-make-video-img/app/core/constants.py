"""Constants for the Make Video IMG service."""
from __future__ import annotations

JOB_ID_PREFIX = "rbg_"
JOB_PREFIX = "rbg_job:"
JOB_TTL = 86400 * 2  # 2 days in seconds

ASPECT_RATIOS = {
    "9:16": {"width": 1080, "height": 1920},
    "16:9": {"width": 1920, "height": 1080},
    "1:1": {"width": 1080, "height": 1080},
}

ZOOM_STYLES = ["zoom_in", "zoom_out", "random"]

# Best-looking xfade transitions (FFmpeg 7.0)
TRANSITIONS = [
    "circleopen", "circleclose",
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "slideleft", "slideright", "slideup", "slidedown",
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    "dissolve", "pixelize",
    "diagtl", "diagtr", "diagbl", "diagbr",
    "radial", "zoomin",
    "fadefast", "fadeslow",
    "coverleft", "coverright", "coverup", "coverdown",
    "revealleft", "revealright",
    "squeezeh", "squeezev",
]

STAGE_NAMES = {
    "generating_audio": "Generating Audio",
    "generating_images": "Generating Images",
    "assembling_video": "Assembling Video",
}

CHATTERBOX_MAX_CHARS = 5000

IMAGE_ASPECT_RATIOS = {
    "9:16": (1024, 1792),
    "16:9": (1792, 1024),
    "1:1": (1024, 1024),
}

# Camera movement → Ken Burns zoom style mapping
# JSON camera_movement values → SE9 zoom_style values
CAMERA_MOVEMENT_MAP = {
    "static": "static",
    "slow_push_in": "zoom_in",
    "slow_pull_out": "zoom_out",
    "random": "random",
}

# Transition name mapping: upstream JSON → FFmpeg xfade names
# "corte seco" = hard cut (no transition = None)
TRANSITION_MAP = {
    "corte seco": None,
    "fade curto": "fadeblack",
    "fade": "fadefast",
    "dissolve": "dissolve",
    "crossfade": "dissolve",
}
