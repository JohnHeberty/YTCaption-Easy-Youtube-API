"""
Make-Video Service - Main Application Module

Microserviço orquestrador para criação de vídeos dinâmicos
usando YouTube Shorts + Áudio customizado + Legendas.

📁 Organized Structure:
├── api/               - External service clients (youtube, downloader, transcriber)
├── core/              - Configuration, constants, and data models
├── domain/            - Domain-Driven Design (Stages, JobProcessor, DDD patterns)
├── infrastructure/    - Celery, Redis, logging, metrics, telemetry
├── services/          - Business logic (video building, subtitles, shorts management)
├── shared/            - Events, exceptions, validation, domain integration
├── subtitle_processing/ - Subtitle detection, classification, ASS generation
├── trsd_models/       - Text region detection models
├── utils/             - Helper utilities (audio, VAD, timeouts)
├── video_processing/  - Frame extraction, OCR detection, video validation
└── main.py            - FastAPI application entry point

Version: 2.0.0 (Refactored with modular architecture)
"""
from __future__ import annotations

__version__ = "2.0.0"

# Core imports - Essential configuration and models
from .core import (
    get_settings,
    ProcessingLimits,
    TimeoutConstants,
    ValidationThresholds,
    AspectRatios,
    Job,
    JobStatus,
    JobResult,
)

# Infrastructure - Async processing and observability
from .infrastructure import (
    celery_app,
    RedisJobStore,
    FileLogger,
)

# API - External service clients
from .api import MicroservicesClient

# Services - Business logic
from .services import (
    VideoBuilder,
    SubtitleGenerator,
    ShortsCache,
    get_blacklist,
)

# Shared - Cross-cutting concerns
# Note: DomainJobProcessor not imported to avoid circular dependency
# Import directly: from app.shared.domain_integration import DomainJobProcessor
from .shared import (
    Event,
    EventType,
    EventPublisher,
    ErrorCode,
    EnhancedMakeVideoException,
    MakeVideoException,
    QueryValidator,
)

# Domain - DDD patterns
from .domain import (
    JobStage,
    JobProcessor,
    StageContext,
)

__all__ = [
    # Version
    '__version__',
    # Core
    'get_settings',
    'ProcessingLimits',
    'TimeoutConstants',
    'ValidationThresholds',
    'AspectRatios',
    'Job',
    'JobStatus',
    'JobResult',
    # Infrastructure
    'celery_app',
    'RedisJobStore',
    'FileLogger',
    # API
    'MicroservicesClient',
    # Services
    'VideoBuilder',
    'SubtitleGenerator',
    'ShortsCache',
    'get_blacklist',
    # Shared
    'Event',
    'EventType',
    'EventPublisher',
    'ErrorCode',
    'EnhancedMakeVideoException',
    'MakeVideoException',
    'QueryValidator',
    'DomainJobProcessor',
    'process_job_with_domain',
    # Domain
    'JobStage',
    'JobProcessor',
    'StageContext',
]

