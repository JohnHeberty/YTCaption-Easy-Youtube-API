"""Constants for SE11 Clothes Removal service."""
from __future__ import annotations

# Job ID
JOB_ID_PREFIX = "cr_"

# Redis
REDIS_KEY_PREFIX = "cr_job:"
REDIS_LIST_KEY = "cr_jobs:list"
REDIS_JOB_TTL = 86400 * 2  # 2 days in seconds

# Job status
STATUS_QUEUED = "queued"
STATUS_DETECTING = "detecting"
STATUS_INPAINTING = "inpainting"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# Allowed image extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

# Max file size (MB)
MAX_FILE_SIZE_MB = 50

# Supported SE8 inpainting style
INPAINT_STYLE = "Fooocus Inpaint"
