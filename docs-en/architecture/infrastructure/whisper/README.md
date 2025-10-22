# Whisper Module v2.0 - Parallel Transcription

Parallel transcription system with OpenAI Whisper.

---

## Overview

The **Parallel Transcription System v2.0** offers:
- **7-10x speedup** vs sequential transcription
- **Persistent worker pool** (no initialization overhead)
- **Smart audio chunking**
- **Memory-efficient** processing
- **GPU/CPU automatic fallback**

---

## Architecture

```
Audio File (60min)
    ↓
ChunkPreparationService
    ↓ (split into 10x 6min chunks)
PersistentWorkerPool (4 workers)
    ↓ (parallel processing)
[Worker 1] [Worker 2] [Worker 3] [Worker 4]
    ↓ (merge results)
Final Transcription
```

**Benchmark**:
- Sequential: 60min audio = 45min processing
- Parallel (4 workers): 60min audio = 6min processing
- **Speedup**: 7.5x

---

## Components

### ParallelWhisperService
- Orchestrates parallel transcription
- Splits audio into chunks
- Distributes to workers
- Merges results

### PersistentWorkerPool
- Pool of N workers (configurable)
- Workers remain loaded (model in memory)
- Zero overhead between transcriptions
- Thread-safe task queue

### ChunkPreparationService
- Smart chunking at silences
- Avoids cutting words
- 0.5s overlap between chunks
- FFmpeg for fast splitting

### ModelCache
- Cache for loaded Whisper models
- Lazy loading
- LRU eviction
- Reduces 10-15s loading time

### TranscriptionFactory
- Factory to create services
- Auto-detects GPU/CPU
- Configures optimizations

---

## Supported Models

| Model  | Size | VRAM | Speed | Accuracy |
|--------|------|------|-------|----------|
| tiny   | 39M  | ~1GB | Fast  | Basic    |
| base   | 74M  | ~1GB | Fast  | Good     |
| small  | 244M | ~2GB | Medium| Better   |
| medium | 769M | ~5GB | Slow  | Great    |
| large  | 1.5G | ~10GB| V.Slow| Best     |
| turbo  | 809M | ~6GB | Fast  | Great    |

**Recommended**: `base` (good speed + quality)

---

## Usage Example

```python
from src.infrastructure.whisper import ParallelWhisperService

# Create parallel service
service = ParallelWhisperService(
    model="base",
    num_workers=4,
    device="cuda"  # or "cpu"
)

# Transcribe
transcription = await service.transcribe(
    video_file,
    language="auto"
)

# Results
print(f"Segments: {len(transcription.segments)}")
print(f"Language: {transcription.language}")
print(f"Duration: {transcription.duration:.2f}s")
print(f"Time: {transcription.processing_time:.2f}s")
```

---

## Performance

**CPU (Intel i7)**:
- base model: ~1.5x realtime
- small model: ~0.8x realtime

**GPU (RTX 3090)**:
- base model: ~8x realtime  
- small model: ~5x realtime
- medium model: ~3x realtime

---

**Version**: 2.0.0

[⬅️ Back](../README.md)
