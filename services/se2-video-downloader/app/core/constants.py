"""Core constants for Video Downloader Service.

This module centralizes all magic numbers and configuration constants
to improve maintainability and readability.
"""

# =============================================================================
# File Size Limits
# =============================================================================

# Maximum file size in MB (10GB)
MAX_FILE_SIZE_MB = 10240
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Minimum disk space required for downloads (1GB)
MIN_DISK_SPACE_GB = 1.0
MIN_DISK_SPACE_BYTES = int(MIN_DISK_SPACE_GB * 1024 ** 3)


# =============================================================================
# Timeouts and Intervals
# =============================================================================

# Default job timeout (30 minutes)
DEFAULT_JOB_TIMEOUT_SECONDS = 1800

# Cache TTL (24 hours)
CACHE_TTL_HOURS = 24
CACHE_TTL_SECONDS = CACHE_TTL_HOURS * 3600

# Cleanup interval (30 minutes)
CLEANUP_INTERVAL_MINUTES = 30
CLEANUP_INTERVAL_SECONDS = CLEANUP_INTERVAL_MINUTES * 60

# Orphaned job detection threshold (30 minutes)
ORPHANED_JOB_THRESHOLD_MINUTES = 30


# =============================================================================
# Retry Configuration
# =============================================================================

# Download retry settings
MAX_USER_AGENTS = 3
MAX_ATTEMPTS_PER_UA = 3
MAX_TOTAL_ATTEMPTS = MAX_USER_AGENTS * MAX_ATTEMPTS_PER_UA

# Retry delays (exponential backoff with max 60 seconds)
MAX_BACKOFF_SECONDS = 60.0

# User agent quarantine settings
DEFAULT_UA_QUARANTINE_HOURS = 48
DEFAULT_UA_MAX_ERRORS = 3


# =============================================================================
# Redis Configuration
# =============================================================================

# Default Redis connection settings
DEFAULT_REDIS_MAX_CONNECTIONS = 50
DEFAULT_REDIS_CIRCUIT_BREAKER_MAX_FAILURES = 5
DEFAULT_REDIS_CIRCUIT_BREAKER_TIMEOUT = 60


# =============================================================================
# Rate Limiting
# =============================================================================

# Default rate limit settings
DEFAULT_RATE_LIMIT_ENABLED = True
DEFAULT_RATE_LIMIT_MAX_REQUESTS = 100
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60


# =============================================================================
# Quality Options
# =============================================================================

# yt-dlp format selectors for different quality options
QUALITY_FORMATS = {
    # Best quality: Prefer MP4 progressive over HLS/DASH
    'best': 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b',
    # Worst quality
    'worst': 'wv*[ext=mp4]+wa[ext=m4a]/w[ext=mp4]/wv*+wa/w',
    # Specific resolutions
    '720p': 'bv*[height<=720][ext=mp4]+ba[ext=m4a]/b[height<=720][ext=mp4]/bv*[height<=720]+ba/b[height<=720]',
    '480p': 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/bv*[height<=480]+ba/b[height<=480]',
    '360p': 'bv*[height<=360][ext=mp4]+ba[ext=m4a]/b[height<=360][ext=mp4]/bv*[height<=360]+ba/b[height<=360]',
    # Audio only: Prefer Opus for best compression
    'audio': 'bestaudio[acodec=opus]/bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio',
}

DEFAULT_QUALITY = 'best'


# =============================================================================
# yt-dlp Options
# =============================================================================

# Fragment download settings
FRAGMENT_RETRIES = 10
EXTRACTOR_RETRIES = 3
FILE_ACCESS_RETRIES = 3
CONCURRENT_FRAGMENT_DOWNLOADS = 1

# Progress calculation
PROGRESS_INITIAL = 5.0
PROGRESS_MAX_PRE_DOWNLOAD = 25.0
PROGRESS_POST_DOWNLOAD = 30.0
PROGRESS_MAX_INCOMPLETE = 99.0
PROGRESS_COMPLETE = 100.0


# =============================================================================
# Health Check Settings
# =============================================================================

# Celery worker check timeout
CELERY_INSPECT_TIMEOUT = 3.0


# =============================================================================
# File Paths
# =============================================================================

# Default directory names
DEFAULT_CACHE_DIR = './data/cache'
DEFAULT_DOWNLOADS_DIR = './data/downloads'
DEFAULT_TEMP_DIR = './data/temp'
DEFAULT_LOGS_DIR = './data/logs'

# User agents file
USER_AGENTS_FILENAME = 'user-agents.txt'


# =============================================================================
# HTTP Status Codes
# =============================================================================

# Custom status codes for specific conditions
HTTP_STATUS_TOO_EARLY = 425  # Download not ready yet
HTTP_STATUS_GONE = 410  # Job expired


# =============================================================================
# Validation Constants
# =============================================================================

# Job ID validation
JOB_ID_MAX_LENGTH = 64
JOB_ID_PATTERN = r'^[a-zA-Z0-9_-]{1,64}$'

# URL validation
MAX_URL_LENGTH = 2000

# Filename validation
MAX_FILENAME_LENGTH = 200
INVALID_FILENAME_CHARS = '<>:"/\\|?*\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f'
