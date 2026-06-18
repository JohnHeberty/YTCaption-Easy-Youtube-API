"""Constants for the Make Video IMG service."""

JOB_ID_PREFIX = "rbg_"
JOB_PREFIX = "rbg_job:"
JOB_TTL = 86400 * 2  # 2 days in seconds

ASPECT_RATIOS = {
    "9:16": {"width": 1080, "height": 1920},
    "16:9": {"width": 1920, "height": 1080},
    "1:1": {"width": 1080, "height": 1080},
}

ZOOM_STYLES = ["zoom_in", "zoom_out", "pan_left", "pan_right", "random"]

STAGE_NAMES = {
    "generating_audio": "Generating Audio",
    "generating_images": "Generating Images",
    "assembling_video": "Assembling Video",
}

CHATTERBOX_MAX_CHARS = 5000
