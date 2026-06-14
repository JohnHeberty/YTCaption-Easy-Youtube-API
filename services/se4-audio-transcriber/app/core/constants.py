"""Core constants for Audio Transcriber Service."""

# Timeouts
DEFAULT_JOB_TIMEOUT_SECONDS = 3600
CACHE_TTL_HOURS = 24
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600
CLEANUP_INTERVAL_MINUTES = 30
CLEANUP_INTERVAL_SECONDS = CLEANUP_INTERVAL_MINUTES * 60

# Rates / limits
DEFAULT_RATE_LIMIT_ENABLED = True
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 100
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

# Validation
JOB_ID_MAX_LENGTH = 64
JOB_ID_PATTERN = r'^[a-zA-Z0-9_-]{1,64}$'

# Celery / task
CELERY_TASK_TIMEOUT_SECONDS = 600
CELERY_TASK_MAX_RETRIES = 3
CELERY_TASK_RETRY_DELAY_SECONDS = 30

# Byte conversions
BYTES_PER_MB = 1_048_576

# Model size estimates (MB) per engine type — used for OOM detection & memory reporting
FASTER_WHISPER_MODEL_SIZES = {'tiny': 40, 'base': 75, 'small': 250, 'medium': 770, 'large': 1550}
OPENAI_WHISPER_MODEL_SIZES = {'tiny': 75, 'base': 150, 'small': 384, 'medium': 960, 'large': 2400}
WHISPERX_MODEL_SIZES = {'tiny': 100, 'base': 200, 'small': 475, 'medium': 1250, 'large': 3150}

# Retry defaults (fallback when settings are missing)
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_BACKOFF_BASE = 2.0

# File paths
DEFAULT_CACHE_DIR = './data/cache'
