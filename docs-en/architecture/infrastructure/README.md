# Infrastructure Layer

Infrastructure layer - Concrete service implementations.

---

## Overview

The **Infrastructure Layer** implements interfaces defined in the domain:
- **Storage**: Temporary file management
- **Cache**: LRU cache for transcriptions
- **Validators**: Audio/video validation
- **Utils**: Utilities (FFmpeg optimizer)
- **YouTube**: Resilient video download (v3.0)
- **Whisper**: Parallel transcription (v2.0)

---

## Main Modules

### Storage (`infrastructure/storage/`)
- **LocalStorageService**: Local storage with automatic cleanup
- **FileCleanupManager**: Context managers, periodic cleanup, configurable TTL

### Cache (`infrastructure/cache/`)
- **TranscriptionCache**: LRU cache with file hash, 24h TTL, 40-60% GPU load reduction

### Validators (`infrastructure/validators/`)
- **AudioValidator**: FFprobe validation, corruption detection, time estimation

### Utils (`infrastructure/utils/`)
- **FFmpegOptimizer**: Hardware acceleration (CUDA/NVENC), optimized flags, 2-3x speedup

### YouTube (`infrastructure/youtube/`)
- **YouTubeDownloader** (v3.0): 7 download strategies, rate limiting, proxy support, Tor
- **TranscriptService**: Native YouTube subtitle extraction

### Whisper (`infrastructure/whisper/`)
- **WhisperTranscriptionService**: Sequential transcription with Whisper
- **ParallelWhisperService** (v2.0): Persistent worker pool, parallel processing, 7-10x speedup
- **ModelCache**: Cache for loaded Whisper models
- **ChunkPreparationService**: Smart audio chunking

---

## Features

**Storage**:
- Temporary directories with unique timestamp
- Automatic cleanup of old files (>24h)
- Thread-safe with asyncio

**Cache**:
- MD5/SHA256 file hash
- LRU eviction when cache full
- TTL expiration
- Thread-safe

**Validator**:
- FFprobe for fast metadata
- Supports 10+ audio codecs
- Processing time estimation
- Corruption detection

**FFmpeg Optimizer**:
- Automatic hardware detection (CUDA, VAAPI, VideoToolbox)
- Adaptive optimization flags
- 2-3x faster conversion

---

## Usage Example

```python
from src.infrastructure.storage import LocalStorageService
from src.infrastructure.cache import TranscriptionCache
from src.infrastructure.validators import AudioValidator

# Storage
storage = LocalStorageService(base_temp_dir="./temp")
temp_dir = await storage.create_temp_directory()
removed = await storage.cleanup_old_files(max_age_hours=24)

# Cache
cache = TranscriptionCache(max_size=100, ttl_hours=24)
file_hash = cache.compute_file_hash(Path("video.mp4"))
cached = cache.get(file_hash, model_name="base", language="en")

# Validator
validator = AudioValidator()
metadata = validator.validate_file(Path("video.mp4"))
if metadata.is_valid:
    min_time, max_time = validator.estimate_processing_time(
        metadata, model_name="base", device="cuda"
    )
```

---

**Version**: 3.0.0

[⬅️ Back](../README.md)
