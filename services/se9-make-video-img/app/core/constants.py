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

ZOOM_STYLES = ["zoom_in", "zoom_out", "random", "static"]

# All FFmpeg xfade transitions (FFmpeg 7.0, 58 transitions)
# https://ffmpeg.org/ffmpeg-filters.html#xfade
TRANSITIONS = [
    # Fades
    "fade", "fadeblack", "fadewhite", "fadefast", "fadeslow", "fadegrays",
    # Wipes
    "wipeleft", "wiperight", "wipeup", "wipedown",
    "wipetl", "wipetr", "wipebl", "wipebr",
    # Slides
    "slideleft", "slideright", "slideup", "slidedown",
    # Smooth
    "smoothleft", "smoothright", "smoothup", "smoothdown",
    # Circle
    "circleopen", "circleclose", "circlecrop",
    # Rect
    "rectcrop",
    # Distance
    "distance",
    # Radial / Zoom
    "radial", "zoomin",
    # Dissolve / Pixelize
    "dissolve", "pixelize",
    # Diagonal
    "diagtl", "diagtr", "diagbl", "diagbr",
    # Vertical / Horizontal open/close
    "vertopen", "vertclose", "horzopen", "horzclose",
    # Squeeze
    "squeezeh", "squeezev",
    # Cover
    "coverleft", "coverright", "coverup", "coverdown",
    # Reveal
    "revealleft", "revealright", "revealup", "revealdown",
    # Slice
    "hlslice", "hrslice", "vuslice", "vdslice",
    # Wind
    "hlwind", "hrwind", "vuwind", "vdwind",
    # Blur
    "hblur",
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
    # Portuguese
    "corte seco": None,
    "corte": None,
    "fade curto": "fadeblack",
    "fade": "fadefast",
    "dissolve": "dissolve",
    "crossfade": "dissolve",
    "radial": "radial",
    "zoom": "zoomin",
    "deslizar": "slideleft",
    "deslizar direita": "slideright",
    "deslizar cima": "slideup",
    "deslizar baixo": "slidedown",
    "wipe": "wipeleft",
    "wipe direita": "wiperight",
    "wipe cima": "wipeup",
    "wipe baixo": "wipedown",
    "suavizar": "smoothleft",
    "suavizar direita": "smoothright",
    "circulo": "circleopen",
    "circulo fechar": "circleclose",
    "pixelizar": "pixelize",
    "squeeze": "squeezeh",
    "squeeze vertical": "squeezev",
    "cobrir": "coverleft",
    "cobrir direita": "coverright",
    "cobrir cima": "coverup",
    "cobrir baixo": "coverdown",
    "revelar": "revealleft",
    "revelar direita": "revealright",
    # English
    "fade to black": "fadeblack",
    "fade to white": "fadewhite",
    "fast fade": "fadefast",
    "slow fade": "fadeslow",
    "wipe left": "wipeleft",
    "wipe right": "wiperight",
    "wipe up": "wipeup",
    "wipe down": "wipedown",
    "slide left": "slideleft",
    "slide right": "slideright",
    "slide up": "slideup",
    "slide down": "slidedown",
    "smooth left": "smoothleft",
    "smooth right": "smoothright",
    "smooth up": "smoothup",
    "smooth down": "smoothdown",
    "circle open": "circleopen",
    "circle close": "circleclose",
    "circle crop": "circlecrop",
    "rect crop": "rectcrop",
    "diagonal tl": "diagtl",
    "diagonal tr": "diagtr",
    "diagonal bl": "diagbl",
    "diagonal br": "diagbr",
    "vertical open": "vertopen",
    "vertical close": "vertclose",
    "horizontal open": "horzopen",
    "horizontal close": "horzclose",
    "squeeze horizontal": "squeezeh",
    "squeeze vertical": "squeezev",
    "cover left": "coverleft",
    "cover right": "coverright",
    "cover up": "coverup",
    "cover down": "coverdown",
    "reveal left": "revealleft",
    "reveal right": "revealright",
    "reveal up": "revealup",
    "reveal down": "revealdown",
}

# Platform presets — aspect ratio and caption settings per platform
PLATFORM_PRESETS = {
    "tiktok_reels_shorts": {
        "aspect_ratio": "9:16",
        "caption_position": "bottom",
        "caption_font_size": 48,
        "max_caption_length": 150,
        "description": "TikTok, Instagram Reels, YouTube Shorts — vertical 9:16",
    },
    "youtube": {
        "aspect_ratio": "16:9",
        "caption_position": "bottom",
        "caption_font_size": 42,
        "max_caption_length": 200,
        "description": "YouTube — horizontal 16:9",
    },
    "instagram_feed": {
        "aspect_ratio": "1:1",
        "caption_position": "bottom",
        "caption_font_size": 40,
        "max_caption_length": 125,
        "description": "Instagram Feed — square 1:1",
    },
    "instagram_stories": {
        "aspect_ratio": "9:16",
        "caption_position": "center",
        "caption_font_size": 52,
        "max_caption_length": 100,
        "description": "Instagram Stories — vertical 9:16, centered captions",
    },
}

DEFAULT_PLATFORM = "tiktok_reels_shorts"

DEFAULT_VOICE_ID = "builtin_feminino"

# Shared FFmpeg H.264 encoding args — used across segments, captions, concat, assembly
H264_ENCODING_ARGS = [
    "-c:v", "libx264",
    "-profile:v", "main",
    "-level", "4.0",
    "-g", "30",
    "-bf", "2",
    "-pix_fmt", "yuv420p",
]

# Ken Burns zoom limits
ZOOM_MIN = 1.0
ZOOM_MAX = 1.20

# Default zoom speed (used as fallback when not provided by config)
ZOOM_SPEED_DEFAULT = 0.004

# Crossfade transition constraints
CROSSFADE_RATIO_MAX = 0.15  # max crossfade as fraction of segment duration
CROSSFADE_MIN_DURATION = 0.05  # minimum crossfade duration in seconds
CROSSFADE_DURATION_DEFAULT = 0.5  # default crossfade duration when not from config

# Concat batch size (segments per batch for xfade to avoid OOM)
CONCAT_BATCH_SIZE = 8

# Redis connection pool settings
REDIS_MAX_CONNECTIONS = 10
REDIS_SOCKET_CONNECT_TIMEOUT = 5
REDIS_SOCKET_TIMEOUT = 5
REDIS_HEALTH_CHECK_INTERVAL = 30

# Title card default duration
TITLE_CARD_DURATION_DEFAULT = 0.5

# Image generation defaults
IMAGE_STEPS_DEFAULT = 30
