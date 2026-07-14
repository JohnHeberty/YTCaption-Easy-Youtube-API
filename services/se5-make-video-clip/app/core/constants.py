"""
Constants Module - Centralized Constants

Elimina magic numbers e strings hardcoded.
Pattern: Constants as Configuration
"""

from __future__ import annotations

from enum import Enum


BYTES_PER_MB = 1024 * 1024


class ProcessingLimits:
    """Limites de processamento"""
    MIN_AUDIO_DURATION_SECONDS = 5
    MAX_AUDIO_DURATION_SECONDS = 3600
    MIN_SHORTS_COUNT = 5
    MAX_SHORTS_COUNT = 50
    MAX_SHORTS = 50  # Alias para MAX_SHORTS_COUNT
    MIN_SUBTITLE_DURATION_MS = 120
    MAX_SUBTITLE_GAP_MS = 120
    
    # Validação de vídeo
    MIN_VIDEO_RESOLUTION = 360
    MAX_VIDEO_RESOLUTION = 4096


class TimeoutConstants:
    """Timeouts (em segundos)"""
    API_REQUEST = 120
    VIDEO_DOWNLOAD = 300
    VIDEO_PROCESSING = 600
    OCR_DETECTION_PER_FRAME = 5
    TRANSCRIPTION_POLL = 10
    FFMPEG_OPERATION = 300
    
    # Celery task timeouts
    CELERY_SOFT_TIME_LIMIT = 1800  # 30 minutos
    CELERY_HARD_TIME_LIMIT = 2100  # 35 minutos


class CacheConstants:
    """Configurações de cache"""
    SHORTS_CACHE_TTL_DAYS = 30
    JOB_CACHE_TTL_HOURS = 24
    VALIDATION_CACHE_TTL_HOURS = 168  # 7 dias
    MAX_CACHE_SIZE_GB = 50
    
    # Redis keys prefix
    REDIS_JOB_PREFIX = "make_video:job:"
    REDIS_CHECKPOINT_PREFIX = "checkpoint:"
    REDIS_BLACKLIST_PREFIX = "blacklist:"
    REDIS_METRICS_PREFIX = "metrics:"


class ValidationThresholds:
    """Thresholds de validação - FORÇA BRUTA 100% FRAMES"""
    # 🚨 POLÍTICA DE ZERO TOLERÂNCIA: UMA LETRA = BAN IMEDIATO
    OCR_MIN_CONFIDENCE = 0.15  # ULTRA SENSÍVEL: detectar qualquer texto
    OCR_MAX_FRAMES = None  # REMOVIDO: processar 100% dos frames
    OCR_FRAMES_PER_SECOND = None  # REMOVIDO: processar TODOS os frames
    SUBTITLE_DETECTION_THRESHOLD = 0.0  # ZERO TOLERÂNCIA: 1 frame com texto = ban
    
    # TRSD thresholds
    TRSD_MIN_CONFIDENCE = 0.15  # ULTRA SENSÍVEL
    TRSD_MIN_ALPHA_RATIO = 0.60
    TRSD_TRACK_IOU_THRESHOLD = 0.30


class FFmpegPresets:
    """Presets de encoding FFmpeg"""
    # Presets de velocidade
    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"
    
    # CRF (Constant Rate Factor) - qualidade
    CRF_LOSSLESS = 0
    CRF_HIGH_QUALITY = 18
    CRF_BALANCED = 23
    CRF_LOW_QUALITY = 28
    CRF_VERY_LOW_QUALITY = 35
    
    # Codecs
    CODEC_H264 = "libx264"
    CODEC_H265 = "libx265"
    CODEC_VP9 = "libvpx-vp9"
    CODEC_AAC = "aac"
    CODEC_MP3 = "libmp3lame"


class AspectRatios(Enum):
    """Aspect ratios suportados"""
    VERTICAL = "9:16"      # TikTok, Reels, Shorts
    HORIZONTAL = "16:9"    # YouTube tradicional
    SQUARE = "1:1"         # Instagram feed
    PORTRAIT = "4:5"       # Instagram Portrait
    
    @classmethod
    def parse(cls, ratio_str: str) -> tuple[int, int]:
        """Converte string para tupla (width_ratio, height_ratio)"""
        parts = ratio_str.split(':')
        return (int(parts[0]), int(parts[1]))


class FileExtensions:
    """Extensões de arquivo suportadas"""
    # Áudio
    AUDIO_FORMATS = {'.mp3', '.wav', '.m4a', '.ogg', '.aac', '.flac'}
    
    # Vídeo
    VIDEO_FORMATS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
    
    # Legendas
    SUBTITLE_FORMATS = {'.srt', '.vtt', '.ass', '.ssa'}


class HttpStatusCodes:
    """HTTP Status Codes padronizados"""
    # Success
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    
    # Client Errors
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    PAYLOAD_TOO_LARGE = 413
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429
    
    # Server Errors
    INTERNAL_SERVER_ERROR = 500
    NOT_IMPLEMENTED = 501
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503
    GATEWAY_TIMEOUT = 504


class ErrorMessages:
    """Mensagens de erro padronizadas"""
    # Audio
    AUDIO_NOT_FOUND = "Audio file not found"
    AUDIO_TOO_SHORT = "Audio too short (minimum {min}s)"
    AUDIO_TOO_LONG = "Audio too long (maximum {max}s)"
    AUDIO_INVALID_FORMAT = "Invalid audio format. Supported: {formats}"
    
    # Video
    VIDEO_NOT_FOUND = "Video not found"
    VIDEO_DOWNLOAD_FAILED = "Failed to download video"
    VIDEO_HAS_SUBTITLES = "Video contains hardcoded subtitles"
    VIDEO_CORRUPTED = "Video file is corrupted"
    
    # Processing
    NO_SHORTS_FOUND = "No shorts found for query: {query}"
    INSUFFICIENT_SHORTS = "Insufficient shorts available after filtering"
    PROCESSING_TIMEOUT = "Processing timeout after {seconds}s"
    
    # External Services
    SERVICE_UNAVAILABLE = "{service} is unavailable"
    SERVICE_TIMEOUT = "{service} timeout after {seconds}s"
    
    # System
    DISK_FULL = "Insufficient disk space"
    OUT_OF_MEMORY = "Out of memory"
    REDIS_UNAVAILABLE = "Redis connection failed"


class LogMessages:
    """Mensagens de log padronizadas"""
    # Job lifecycle
    JOB_CREATED = "🎬 Job created: {job_id}"
    JOB_STARTED = "▶️  Job started: {job_id}"
    JOB_STAGE_COMPLETED = "✅ Stage completed: {stage} ({duration:.2f}s)"
    JOB_COMPLETED = "🎉 Job completed: {job_id} ({duration:.2f}s)"
    JOB_FAILED = "❌ Job failed: {job_id} - {error}"
    JOB_RECOVERED = "🔄 Job recovered: {job_id}"
    
    # Video processing
    VIDEO_DOWNLOADING = "⬇️  Downloading video: {video_id}"
    VIDEO_DOWNLOADED = "✅ Downloaded: {video_id} ({size_mb:.1f}MB)"
    VIDEO_VALIDATING = "🔍 Validating: {video_id}"
    VIDEO_APPROVED = "✅ Approved: {video_id}"
    VIDEO_REJECTED = "❌ Rejected: {video_id} - {reason}"
    VIDEO_BLACKLISTED = "🚫 Blacklisted: {video_id}"
    
    # System
    CACHE_HIT = "💾 Cache hit: {key}"
    CACHE_MISS = "🔍 Cache miss: {key}"
    CLEANUP_STARTED = "🗑️  Cleanup started"
    CLEANUP_COMPLETED = "✅ Cleanup completed: {files_deleted} files deleted"


class MetricNames:
    """Nomes de métricas Prometheus"""
    # Counters
    JOBS_TOTAL = "makevideo_jobs_total"
    JOBS_FAILED = "makevideo_jobs_failed"
    VIDEOS_DOWNLOADED = "makevideo_videos_downloaded"
    VIDEOS_REJECTED = "makevideo_videos_rejected"
    CACHE_HITS = "makevideo_cache_hits_total"
    CACHE_MISSES = "makevideo_cache_misses_total"
    
    # Histograms
    JOB_DURATION = "makevideo_job_duration_seconds"
    STAGE_DURATION = "makevideo_stage_duration_seconds"
    VIDEO_DOWNLOAD_DURATION = "makevideo_video_download_seconds"
    OCR_DETECTION_DURATION = "makevideo_ocr_detection_seconds"
    
    # Gauges
    ACTIVE_JOBS = "makevideo_active_jobs"
    ORPHANED_JOBS = "makevideo_orphaned_jobs"
    CACHE_SIZE_BYTES = "makevideo_cache_size_bytes"
    DISK_USAGE_PERCENT = "makevideo_disk_usage_percent"


class RegexPatterns:
    """Padrões regex comuns"""
    # Video ID (YouTube)
    YOUTUBE_VIDEO_ID = r'^[a-zA-Z0-9_-]{11}$'
    
    # Job ID (shortuuid)
    JOB_ID = r'^[a-zA-Z0-9]{22}$'
    
    # Aspect ratio
    ASPECT_RATIO = r'^\d+:\d+$'
    
    # Language code (ISO 639-1)
    LANGUAGE_CODE = r'^[a-z]{2}$'
    
    # Timestamp SRT (00:00:00,000)
    SRT_TIMESTAMP = r'^\d{2}:\d{2}:\d{2},\d{3}$'


# Aliases para facilitar importação
class Limits(ProcessingLimits):
    """Alias para ProcessingLimits"""
    pass


class Timeouts(TimeoutConstants):
    """Alias para TimeoutConstants"""
    pass


class Thresholds(ValidationThresholds):
    """Alias para ValidationThresholds"""
    pass


# ---------------------------------------------------------------------------
# FFmpeg Encoding Defaults
# ---------------------------------------------------------------------------
FFMPEG_GOP_SIZE = 30
FFMPEG_B_FRAMES = 2
AUDIO_BITRATE = "192k"
AUDIO_BITRATE_LOW = "128k"
DEFAULT_VIDEO_FPS = 30
DEFAULT_VIDEO_WIDTH = 1080
DEFAULT_VIDEO_HEIGHT = 1920
DEFAULT_CRF = 23
CRF_VALIDATION_CROP = 28
TITLE_FONT_SIZE = 48
TITLE_BORDER_WIDTH = 3
STEREO_CHANNELS = 2
DEFAULT_AUDIO_SAMPLE_RATE = 48000

# ---------------------------------------------------------------------------
# Duration / Timing Defaults
# ---------------------------------------------------------------------------
DEFAULT_TITLE_CARD_DURATION = 0.2
DEFAULT_TRANSITION_DURATION = 0.2
CONCAT_DURATION_TOLERANCE = 2.0
DURATION_CHANGE_THRESHOLD = 1.0
DEFAULT_AUDIO_DURATION = 300.0

# ---------------------------------------------------------------------------
# Redis / Storage
# ---------------------------------------------------------------------------
REDIS_MAX_CONNECTIONS = 50
REDIS_JOB_TTL_SECONDS = 86400
DEFAULT_LIST_LIMIT = 100
ORPHAN_AGE_MINUTES = 10
ORPHAN_SCAN_MAX_JOBS = 1000
LOCK_REDIS_MAX_CONNECTIONS = 10
DEFAULT_LOCK_TTL = 3600
SECONDS_PER_DAY = 86400

# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------
SQLITE_CONNECTION_TIMEOUT = 10.0
SQLITE_BUSY_TIMEOUT_MS = 10000
SQLITE_BLACKLIST_CONNECTION_TIMEOUT = 5.0
SQLITE_BLACKLIST_BUSY_TIMEOUT_MS = 5000

# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------
CIRCUIT_BREAKER_DEFAULT_THRESHOLD = 5
CIRCUIT_BREAKER_DOWNLOAD_THRESHOLD = 10
CIRCUIT_BREAKER_TRANSCRIPTION_THRESHOLD = 3
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 60

# ---------------------------------------------------------------------------
# Celery Configuration
# ---------------------------------------------------------------------------
DEFAULT_CELERY_CONCURRENCY = 4
DEFAULT_PREFETCH_MULTIPLIER = 1
DEFAULT_CELERY_TIME_LIMIT = 3600
SOFT_LIMIT_RATIO = 0.92
MAX_TASKS_PER_CHILD = 10
RESULT_EXPIRY_SECONDS = 86400
DEFAULT_RETRY_DELAY = 60
BROKER_VISIBILITY_TIMEOUT = 3600
CLEANUP_SCHEDULE_SECONDS = 3600.0
SHORTS_CLEANUP_SCHEDULE_SECONDS = 86400.0
ORPHAN_RECOVERY_SCHEDULE_SECONDS = 120.0
TASK_EXPIRY_SECONDS = 60

# ---------------------------------------------------------------------------
# Status Update / Job Lifecycle
# ---------------------------------------------------------------------------
STATUS_UPDATE_MAX_RETRIES = 3
STATUS_UPDATE_RETRY_DELAY = 1
COMPLETED_JOB_EXPIRY_HOURS = 24
JOB_LOG_BACKUP_COUNT = 2

# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
REDIS_PING_TIMEOUT = 2.0
REDIS_SET_TIMEOUT = 1.0
REDIS_GET_TIMEOUT = 1.0
HEALTH_CHECK_TEST_KEY_TTL = 5
SERVICE_HEALTH_CHECK_TIMEOUT = 3.0
DISK_SPACE_CRITICAL_GB = 1.0
DISK_SPACE_WARNING_GB = 5.0
CELERY_INSPECT_TIMEOUT = 2.0

# ---------------------------------------------------------------------------
# Stage Timeouts
# ---------------------------------------------------------------------------
STAGE_TIMEOUT_QUEUED = 10
STAGE_TIMEOUT_PROCESSING = 300
STAGE_TIMEOUT_DEFAULT = 300
AUDIO_TIMEOUT_MULTIPLIER = 30
TIMEOUT_BACKOFF_BASE = 1.5
MAX_STAGE_TIMEOUT = 1800

# ---------------------------------------------------------------------------
# Subprocess / FFmpeg Timeouts
# ---------------------------------------------------------------------------
TIMEOUT_TITLE_CARD = 60
TIMEOUT_SUBTITLE_BURN = 900
TIMEOUT_CODEC_CONVERSION = 120
TIMEOUT_FRAME_EXTRACTION = 60
TIMEOUT_AUDIO_CONVERSION = 30

# ---------------------------------------------------------------------------
# Download / Task Limits
# ---------------------------------------------------------------------------
DOWNLOAD_TASK_TIME_LIMIT = 7200
DOWNLOAD_TASK_SOFT_TIME_LIMIT = 6600
STALE_VALIDATION_AGE_MINUTES = 30
DEFAULT_MAX_SHORTS = 50
DOWNLOAD_BATCH_SIZE = 5

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
DEFAULT_CLEANUP_INTERVAL_MINUTES = 10
ORPHAN_RETENTION_HOURS = 24
TEMP_RETENTION_HOURS = 6
CLEANUP_ERROR_RETRY_SECONDS = 60

# ---------------------------------------------------------------------------
# API Client Polling
# ---------------------------------------------------------------------------
SEARCH_POLL_INTERVAL = 2
SEARCH_MAX_POLLS = 150
DOWNLOAD_POLL_INTERVAL = 3
DOWNLOAD_MAX_POLLS = 40
DOWNLOAD_LOG_INTERVAL = 7
TRANSCRIPTION_CREATE_RETRIES = 4
TRANSCRIPTION_BACKOFF_BASE = 2
TRANSCRIPTION_BACKOFF_MAX = 20
TRANSCRIPTION_POLL_INTERVAL = 3
TRANSCRIPTION_MAX_POLLS = 10
HTTP_SEARCH_TIMEOUT = 120.0
HTTP_SEARCH_WAIT_TIMEOUT = 90.0
HTTP_DOWNLOAD_TIMEOUT = 120.0
HTTP_FILE_DOWNLOAD_TIMEOUT = 60.0

# ---------------------------------------------------------------------------
# Video Validation / OCR Weights
# ---------------------------------------------------------------------------
VISUAL_SCORE_MAX = 100.0
CONFIDENCE_WEIGHT_OCR = 0.6
CONFIDENCE_WEIGHT_VISUAL = 0.4
VALIDATION_CACHE_TTL_SECONDS = 604800
PRESET_CODEC_CONVERSION = "ultrafast"
DEFAULT_DOWNSCALE_WIDTH = 640
FPS_COMPATIBILITY_TOLERANCE = 0.1

# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
QUERY_MIN_LENGTH = 3
QUERY_MAX_LENGTH = 200
MIN_FILE_CONTENT_BYTES = 12
MIN_SHORTS_COUNT_VALIDATOR = 10
MAX_SHORTS_COUNT_VALIDATOR = 500
