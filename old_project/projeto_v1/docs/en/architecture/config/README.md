# Config Layer - Settings Module

Centralized configuration management using **Pydantic Settings** with environment variables validation.

---

## Overview

The `Settings` module is the **single source of truth** for all application configuration. It follows the **Single Responsibility Principle** (SOLID) by managing only configuration concerns.

**Location**: `src/config/settings.py`

**Key Features**:
- ✅ Type-safe configuration with Pydantic validation
- ✅ Environment variables with `.env` file support
- ✅ Default values for all settings
- ✅ Custom validators for critical settings
- ✅ Immutable global settings instance

---

## Architecture Position

```
┌─────────────────────────────────────────┐
│         PRESENTATION LAYER              │
│      (FastAPI Controllers)              │
└──────────────┬──────────────────────────┘
               │ uses settings
┌──────────────▼──────────────────────────┐
│         APPLICATION LAYER               │
│          (Use Cases)                    │
└──────────────┬──────────────────────────┘
               │ uses settings
┌──────────────▼──────────────────────────┐
│      INFRASTRUCTURE LAYER               │
│  (Whisper, YouTube, Storage)            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         ⚙️ CONFIG LAYER ⚙️              │
│      (Settings - This Module)           │
│    Single Source of Configuration       │
└─────────────────────────────────────────┘
```

All layers depend on the Config Layer for configuration values.

---

## Settings Class

### Application Settings

```python
from src.config.settings import settings

# Application metadata
settings.app_name           # "Whisper Transcription API"
settings.app_version        # "1.0.0"
settings.app_environment    # "production" | "development"

# Server configuration
settings.host               # "0.0.0.0"
settings.port               # 8000
```

### Whisper Configuration

```python
# Model settings
settings.whisper_model      # "tiny" | "base" | "small" | "medium" | "large" | "turbo"
settings.whisper_device     # "cpu" | "cuda"
settings.whisper_language   # "auto" | ISO 639-1 code

# Parallel transcription (v2.0)
settings.enable_parallel_transcription  # False (default)
settings.parallel_workers               # 4
settings.parallel_chunk_duration        # 120 seconds
```

**Validator**: `validate_whisper_model()` ensures model is valid.

### Audio Processing

```python
# Advanced audio normalization (v2.2)
settings.enable_audio_volume_normalization  # False (default)
settings.enable_audio_noise_reduction       # False (default)
```

**Use Case**: Enable for poor quality audio (outdoor recordings, low volume).

### YouTube Downloader

```python
# Download settings
settings.youtube_format                # "worstaudio" (optimal for transcription)
settings.max_video_size_mb            # 1500 MB
settings.max_video_duration_seconds   # 10800 (3 hours)
settings.download_timeout             # 900 seconds (15 min)
```

### Storage Management

```python
# Temporary file settings
settings.temp_dir                     # "./temp"
settings.cleanup_on_startup           # True
settings.cleanup_after_processing     # True
settings.max_temp_age_hours          # 24

# Periodic cleanup (v2.0)
settings.enable_periodic_cleanup      # True
settings.cleanup_interval_minutes     # 30
```

### API Configuration

```python
# Request handling
settings.max_concurrent_requests      # 3
settings.request_timeout             # 3600 seconds (1 hour)

# CORS
settings.enable_cors                 # True
settings.cors_origins                # "*" or "domain1.com,domain2.com"
```

**Method**: `get_cors_origins()` parses CORS string into list.

### Logging

```python
# Log configuration
settings.log_level        # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
settings.log_format       # "json" | "text"
settings.log_file         # "./logs/app.log"
```

**Validator**: `validate_log_level()` ensures valid log level.

### Cache System (v2.0)

```python
# Transcription cache
settings.enable_transcription_cache   # True
settings.cache_max_size              # 100 entries
settings.cache_ttl_hours             # 24

# Model cache
settings.whisper_model_cache_timeout_minutes  # 30
```

### Performance

```python
# Worker configuration
settings.workers                      # 1 (Uvicorn workers)

# FFmpeg optimization
settings.enable_ffmpeg_hw_accel      # True (GPU acceleration)
```

---

## Validators

### 1. Whisper Model Validator

```python
@validator("whisper_model")
def validate_whisper_model(cls, v: str) -> str:
    """Validates Whisper model name."""
    valid_models = ["tiny", "base", "small", "medium", "large", "turbo"]
    if v not in valid_models:
        raise ValueError(f"Model must be one of {valid_models}")
    return v
```

**Purpose**: Prevents invalid model names at startup.

### 2. Log Level Validator

```python
@validator("log_level")
def validate_log_level(cls, v: str) -> str:
    """Validates log level."""
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    v = v.upper()
    if v not in valid_levels:
        raise ValueError(f"Log level must be one of {valid_levels}")
    return v
```

**Purpose**: Ensures valid logging configuration.

---

## CORS Configuration

### Method: `get_cors_origins()`

```python
def get_cors_origins(self) -> List[str]:
    """Returns list of allowed CORS origins."""
    if self.cors_origins == "*":
        return ["*"]
    return [origin.strip() for origin in self.cors_origins.split(",")]
```

**Usage**:

```python
# Allow all origins
CORS_ORIGINS="*"
settings.get_cors_origins()  # ["*"]

# Specific domains
CORS_ORIGINS="https://app.com,https://admin.app.com"
settings.get_cors_origins()  # ["https://app.com", "https://admin.app.com"]
```

---

## Pydantic Configuration

```python
model_config = SettingsConfigDict(
    env_file=".env",              # Load from .env file
    env_file_encoding="utf-8",    # UTF-8 encoding
    case_sensitive=False,         # Case-insensitive env vars
    extra="ignore",               # Ignore unknown env vars
    protected_namespaces=()       # Allow 'model_' prefix
)
```

**Key Behavior**:
- Reads from `.env` file if present
- Environment variables override defaults
- Unknown variables are ignored (no errors)
- `model_` prefix allowed (for Pydantic compatibility)

---

## Usage Examples

### Basic Usage

```python
from src.config.settings import settings

# Access settings
model = settings.whisper_model
device = settings.whisper_device

print(f"Using model: {model} on {device}")
```

### Dependency Injection (FastAPI)

```python
from fastapi import Depends
from src.config.settings import Settings, settings

def get_settings() -> Settings:
    """FastAPI dependency for settings."""
    return settings

@app.get("/config")
async def get_config(settings: Settings = Depends(get_settings)):
    return {
        "model": settings.whisper_model,
        "device": settings.whisper_device
    }
```

### Environment Variables

```bash
# .env file
WHISPER_MODEL=base
WHISPER_DEVICE=cuda
ENABLE_PARALLEL_TRANSCRIPTION=true
PARALLEL_WORKERS=8
```

---

## Configuration Groups

| Group | Variables | Purpose |
|-------|-----------|---------|
| **Application** | 3 | App metadata |
| **Server** | 2 | Host/port |
| **Whisper** | 6 | Model, parallel transcription |
| **Audio** | 2 | Normalization, noise reduction |
| **YouTube** | 4 | Download limits, timeout |
| **Storage** | 6 | Temp files, cleanup |
| **API** | 4 | Concurrent requests, CORS |
| **Logging** | 3 | Level, format, file |
| **Cache** | 4 | Transcription & model cache |
| **Performance** | 2 | Workers, FFmpeg accel |
| **Total** | **36** | All configuration options |

---

## Best Practices

### ✅ DO

```python
# Import the singleton instance
from src.config.settings import settings

# Access settings
timeout = settings.request_timeout
```

### ❌ DON'T

```python
# Don't create new Settings instances
from src.config.settings import Settings
my_settings = Settings()  # Wrong! Use singleton
```

### Environment-Specific Configuration

```bash
# Development
APP_ENVIRONMENT=development
LOG_LEVEL=DEBUG
ENABLE_TRANSCRIPTION_CACHE=false

# Production
APP_ENVIRONMENT=production
LOG_LEVEL=INFO
ENABLE_TRANSCRIPTION_CACHE=true
```

---

## Related Documentation

- **User Guide**: [Configuration Guide](../../user-guide/03-configuration.md) - All environment variables explained
- **Infrastructure**: [Storage](../infrastructure/storage/) - Uses temp_dir, cleanup settings
- **Infrastructure**: [Whisper](../infrastructure/whisper/) - Uses model, device, parallel settings
- **Infrastructure**: [YouTube](../infrastructure/youtube/) - Uses download settings
- **Presentation**: [API Main](../presentation/README.md) - Uses CORS, server settings

---

## Version History

| Version | Changes |
|---------|---------|
| **v1.0** | Initial settings (20 variables) |
| **v2.0** | Added cache, periodic cleanup, FFmpeg accel (10 new variables) |
| **v2.1** | Circuit breaker integration |
| **v2.2** | Audio normalization settings (2 new variables) |
| **v3.0** | YouTube Resilience settings |

**Current**: 36 configuration variables

---

[← Back](../README.md)

**Version**: 3.0.0
