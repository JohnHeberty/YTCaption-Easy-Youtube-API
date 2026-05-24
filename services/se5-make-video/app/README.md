# App Module Organization

## 📁 Structure

```
app/
├── __init__.py           # Main module exports
├── main.py               # FastAPI application
│
├── api/                  # External Service Clients
│   ├── __init__.py
│   └── api_client.py     # MicroservicesClient (YouTube, Downloader, Transcriber)
│
├── core/                 # Configuration & Models
│   ├── __init__.py
│   ├── config.py         # Settings and configuration
│   ├── constants.py      # ProcessingLimits, Timeouts, AspectRatios, etc.
│   └── models.py         # Job, JobStatus, JobResult, ShortInfo
│
├── domain/               # Domain-Driven Design
│   ├── __init__.py
│   ├── job_stage.py      # JobStage base class (Template Method)
│   ├── job_processor.py  # JobProcessor (Chain of Responsibility)
│   └── stages/           # Concrete stage implementations
│       ├── analyze_audio_stage.py
│       ├── fetch_shorts_stage.py
│       ├── download_shorts_stage.py
│       ├── select_shorts_stage.py
│       ├── assemble_video_stage.py
│       ├── generate_subtitles_stage.py
│       ├── final_composition_stage.py
│       └── trim_video_stage.py
│
├── infrastructure/       # Infrastructure Components
│   ├── __init__.py
│   ├── celery_config.py  # Celery app configuration
│   ├── celery_tasks.py   # Async task definitions
│   ├── redis_store.py    # RedisJobStore for job persistence
│   ├── file_logger.py    # File-based logging
│   ├── log_utils.py      # Logging utilities
│   ├── logging_config.py # Logging configuration
│   ├── metrics.py        # Prometheus metrics
│   └── telemetry.py      # OpenTelemetry tracing
│
├── services/             # Business Logic Services
│   ├── __init__.py
│   ├── video_builder.py  # VideoBuilder (FFmpeg operations)
│   ├── subtitle_generator.py      # SubtitleGenerator
│   ├── subtitle_postprocessor.py  # VAD post-processing
│   ├── shorts_manager.py          # ShortsCache management
│   ├── blacklist_factory.py       # Blacklist factory
│   └── sqlite_blacklist.py        # SQLite blacklist implementation
│
├── shared/               # Shared Components
│   ├── __init__.py
│   ├── events.py         # Event system (CloudEvents spec)
│   ├── exceptions.py     # Exception hierarchy (80+ ErrorCodes)
│   ├── validation.py     # Input validation (XSS, injection prevention)
│   └── domain_integration.py  # DomainJobProcessor integration
│
├── subtitle_processing/  # Subtitle Analysis
│   ├── __init__.py
│   ├── ass_generator.py         # ASS subtitle generation
│   ├── subtitle_detector.py     # Subtitle detection in video
│   ├── subtitle_classifier.py   # Subtitle classification
│   ├── subtitle_classifier_v2.py
│   └── temporal_tracker.py      # Temporal tracking
│
├── trsd_models/          # Text Region Detection
│   ├── __init__.py
│   └── text_region.py    # Text region models
│
├── utils/                # Helper Utilities
│   ├── __init__.py
│   ├── audio_utils.py    # Audio processing utilities
│   ├── vad_utils.py      # Voice Activity Detection utilities
│   ├── vad.py            # VAD implementation
│   └── timeout_utils.py  # Timeout handlers
│
└── video_processing/     # Video Analysis
    ├── __init__.py
    ├── frame_extractor.py  # Frame extraction from video
    ├── ocr_detector.py     # OCR text detection
    └── video_validator.py  # Video validation (OCR-based)
```

## 🎯 Module Purpose

### **api/**
External service integration. Clients for YouTube Search, Video Downloader, and Audio Transcriber microservices.

### **core/**
Foundation layer. Configuration, constants, and data models used across the application.

### **domain/**
Domain-Driven Design implementation. Business logic organized in stages with Template Method and Chain of Responsibility patterns.

### **infrastructure/**
Infrastructure concerns. Async processing (Celery), caching (Redis), logging, metrics, and telemetry.

### **services/**
Business services. Video building with FFmpeg, subtitle generation, shorts management, and blacklist handling.

### **shared/**
Cross-cutting concerns. Events, exceptions, validation, and domain integration used by multiple modules.

### **subtitle_processing/**
Subtitle analysis pipeline. Detection, classification, and ASS generation for video subtitles.

### **trsd_models/**
Text region detection models for OCR and subtitle detection.

### **utils/**
Helper utilities. Audio processing, VAD, and timeout management.

### **video_processing/**
Video analysis pipeline. Frame extraction, OCR detection, and validation.

## 📦 Import Guidelines

### From main.py or external modules:
```python
from app import (
    get_settings,
    celery_app,
    RedisJobStore,
    VideoBuilder,
    MakeVideoException,
)
```

### Within app/ modules:
```python
# Relative imports within same layer
from .video_builder import VideoBuilder

# Cross-layer imports
from app.core import ProcessingLimits
from app.infrastructure import RedisJobStore
from app.shared import ErrorCode, EnhancedMakeVideoException
```

## 🔄 Migration Guide

If you have old imports, update them:

```python
# OLD (flat structure)
from app.constants import ProcessingLimits
from app.celery_tasks import process_make_video
from app.exceptions import MakeVideoException

# NEW (organized structure)
from app.core import ProcessingLimits
from app.infrastructure import celery_app
from app.shared import MakeVideoException
```

## ✅ Benefits

1. **Clear Separation of Concerns** - Each module has a single, well-defined responsibility
2. **Easy to Navigate** - Logical grouping makes it easy to find code
3. **Scalable** - New features can be added to appropriate modules
4. **Testable** - Modules can be tested independently
5. **Maintainable** - Changes are localized to specific modules
6. **Self-Documenting** - Structure reflects architecture

## 🚀 Next Steps

After reorganization, run tests to ensure all imports are working correctly:

```bash
cd /root/YTCaption-Easy-Youtube-API/services/se5-make-video
python3 -m pytest tests/ -v
```

Check that main.py and celery workers start without import errors:

```bash
# Test FastAPI
python3 app/main.py

# Test Celery worker
celery -A app.infrastructure.celery_config worker --loglevel=info
```
