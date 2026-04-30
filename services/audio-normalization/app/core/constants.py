"""
Constantes do serviço de normalização de áudio.

Todas as constantes centralizadas para facilitar manutenção e testes.
"""
from pathlib import Path
from typing import Set


class AudioConstants:
    """Constantes relacionadas a processamento de áudio."""

    # Formatos de vídeo suportados
    VIDEO_EXTENSIONS: Set[str] = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.m4v'}

    # Formatos de áudio suportados
    AUDIO_EXTENSIONS: Set[str] = {
        '.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac', '.wma', '.opus', '.webm'
    }

    # Todos os formatos aceitos
    SUPPORTED_EXTENSIONS: Set[str] = VIDEO_EXTENSIONS | AUDIO_EXTENSIONS

    # Codecs padrão
    DEFAULT_AUDIO_CODEC: str = "libopus"
    DEFAULT_AUDIO_BITRATE: str = "128k"
    DEFAULT_SAMPLE_RATE: int = 44100
    DEFAULT_CHANNELS: int = 2

    # Parâmetros de processamento
    DEFAULT_HIGHPASS_CUTOFF_HZ: int = 80
    DEFAULT_HIGHPASS_ORDER: int = 5
    DEFAULT_NOISE_REDUCTION_SAMPLE_RATE: int = 22050
    DEFAULT_VOCAL_ISOLATION_SAMPLE_RATE: int = 44100


class JobConstants:
    """Constantes relacionadas a jobs."""

    # Status
    STATUS_QUEUED: str = "queued"
    STATUS_PROCESSING: str = "processing"
    STATUS_COMPLETED: str = "completed"
    STATUS_FAILED: str = "failed"

    # Timeouts e TTL
    DEFAULT_CACHE_TTL_HOURS: int = 24
    DEFAULT_JOB_TIMEOUT_MINUTES: int = 30
    DEFAULT_ORPHAN_TIMEOUT_MINUTES: int = 15
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS: int = 30

    # Progresso
    PROGRESS_INITIAL: float = 0.0
    PROGRESS_VALIDATION_COMPLETE: float = 5.0
    PROGRESS_PROCESSING_START: float = 10.0
    PROGRESS_PROCESSING_COMPLETE: float = 90.0
    PROGRESS_COMPLETED: float = 100.0

    # Regex para validação de job_id
    JOB_ID_PATTERN: str = r'^[a-zA-Z0-9_-]{1,255}$'
    JOB_ID_MAX_LENGTH: int = 255


class FileConstants:
    """Constantes relacionadas a arquivos."""

    # Diretórios padrão
    DEFAULT_UPLOAD_DIR: Path = Path("./uploads")
    DEFAULT_PROCESSED_DIR: Path = Path("./processed")
    DEFAULT_TEMP_DIR: Path = Path("./temp")
    DEFAULT_LOG_DIR: Path = Path("./logs")

    # Tamanhos
    DEFAULT_MAX_FILE_SIZE_MB: int = 2048
    DEFAULT_MAX_DURATION_MINUTES: int = 120

    # Extensões de saída
    OUTPUT_EXTENSION: str = ".webm"
    TEMP_CHUNK_EXTENSION: str = ".wav"


class ValidationConstants:
    """Constantes para validação de entrada."""

    # Valores booleanos aceitos
    TRUE_VALUES: Set[str] = {'true', '1', 'yes', 'on'}
    FALSE_VALUES: Set[str] = {'false', '0', 'no', 'off', ''}
    BOOLEAN_VALUES: Set[str] = TRUE_VALUES | FALSE_VALUES

    # Limites
    MAX_FILENAME_LENGTH: int = 255
    MAX_CONTENT_LENGTH_MB: int = 2048


# Instâncias exportadas
AUDIO_CONSTANTS = AudioConstants()
JOB_CONSTANTS = JobConstants()
FILE_CONSTANTS = FileConstants()
VALIDATION_CONSTANTS = ValidationConstants()
