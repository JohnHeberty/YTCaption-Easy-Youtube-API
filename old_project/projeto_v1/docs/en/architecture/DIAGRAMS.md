# YTCaption Architecture Diagrams

## Overview

This document provides comprehensive architectural diagrams for the YTCaption API system using Mermaid notation. These diagrams illustrate the system's layers, components, data flows, and interactions following Domain-Driven Design (DDD) and Clean Architecture principles.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [DDD Layers Architecture](#2-ddd-layers-architecture)
3. [Request Flow - Transcription](#3-request-flow---transcription)
4. [Request Flow - Video Info](#4-request-flow---video-info)
5. [Component Dependencies](#5-component-dependencies)
6. [Worker Pool Architecture](#6-worker-pool-architecture)
7. [Cache Strategy](#7-cache-strategy)
8. [Circuit Breaker Pattern](#8-circuit-breaker-pattern)
9. [Deployment Architecture](#9-deployment-architecture)

---

## 1. System Overview

**High-level system architecture showing external integrations:**

```mermaid
graph TB
    subgraph "External Services"
        YT[YouTube API<br/>yt-dlp]
        PROM[Prometheus<br/>Monitoring]
    end
    
    subgraph "YTCaption API System"
        API[FastAPI Application<br/>:8000]
        WHISPER[Whisper AI<br/>Transcription Engine]
        CACHE[LRU Cache<br/>Transcriptions]
        STORAGE[Local Storage<br/>/temp]
    end
    
    subgraph "Clients"
        WEB[Web Browser]
        MOBILE[Mobile App]
        CLI[CLI Tool]
    end
    
    WEB -->|HTTP POST| API
    MOBILE -->|HTTP POST| API
    CLI -->|HTTP POST| API
    
    API -->|Download| YT
    API -->|Transcribe| WHISPER
    API -->|Cache Check| CACHE
    API -->|Store Files| STORAGE
    API -->|Export Metrics| PROM
    
    style API fill:#4CAF50
    style WHISPER fill:#FF9800
    style YT fill:#FF5252
```

---

## 2. DDD Layers Architecture

**Clean Architecture / DDD layers with dependency direction:**

```mermaid
graph TB
    subgraph "Presentation Layer"
        ROUTES[API Routes<br/>transcription.py<br/>video_info.py<br/>system.py]
        MIDDLEWARE[Middlewares<br/>Logging<br/>Prometheus]
        DEPS[Dependencies<br/>DI Container]
    end
    
    subgraph "Application Layer"
        UC_TRANS[TranscribeYouTubeVideoUseCase]
        UC_CLEAN[CleanupOldFilesUseCase]
        DTOS[DTOs<br/>Request/Response Models]
    end
    
    subgraph "Domain Layer"
        ENTITIES[Entities<br/>Transcription<br/>VideoFile]
        VO[Value Objects<br/>YouTubeURL<br/>TranscriptionSegment]
        INTERFACES[Interfaces<br/>IVideoDownloader<br/>ITranscriptionService<br/>IStorageService]
        EXCEPTIONS[Domain Exceptions]
    end
    
    subgraph "Infrastructure Layer"
        YOUTUBE[YouTubeDownloader]
        WHISPER_IMPL[WhisperTranscriptionService<br/>ParallelTranscriptionService]
        STORAGE_IMPL[LocalStorageService]
        CACHE_IMPL[TranscriptionCache]
        VALIDATORS[AudioValidator]
        CIRCUIT[CircuitBreaker]
    end
    
    ROUTES --> UC_TRANS
    ROUTES --> UC_CLEAN
    ROUTES --> DTOS
    MIDDLEWARE --> ROUTES
    DEPS --> UC_TRANS
    
    UC_TRANS --> INTERFACES
    UC_TRANS --> ENTITIES
    UC_TRANS --> DTOS
    
    INTERFACES -.implements.-> YOUTUBE
    INTERFACES -.implements.-> WHISPER_IMPL
    INTERFACES -.implements.-> STORAGE_IMPL
    
    YOUTUBE --> CIRCUIT
    WHISPER_IMPL --> CACHE_IMPL
    WHISPER_IMPL --> VALIDATORS
    
    style INTERFACES fill:#2196F3
    style UC_TRANS fill:#4CAF50
    style WHISPER_IMPL fill:#FF9800
```

---

## 3. Request Flow - Transcription

**Complete flow for POST /api/v1/transcribe:**

```mermaid
sequenceDiagram
    participant Client
    participant Middleware as Logging Middleware
    participant Route as Transcription Route
    participant UseCase as TranscribeVideoUseCase
    participant Cache as TranscriptionCache
    participant Downloader as YouTubeDownloader
    participant Validator as AudioValidator
    participant Whisper as WhisperService
    participant Storage as LocalStorage
    
    Client->>Middleware: POST /api/v1/transcribe<br/>{youtube_url, language}
    Middleware->>Middleware: Generate Request ID (UUID)
    Middleware->>Route: Forward Request
    
    Route->>Route: Validate YouTube URL
    Route->>UseCase: execute(url, language)
    
    UseCase->>Cache: check(youtube_url, model)
    alt Cache Hit
        Cache-->>UseCase: Return cached transcription
        UseCase-->>Route: TranscriptionResult
        Route-->>Client: 200 OK + Transcription
    else Cache Miss
        Cache-->>UseCase: None
        
        UseCase->>Downloader: download_audio(url)
        Downloader->>Downloader: Circuit Breaker Check
        alt Circuit OPEN
            Downloader-->>UseCase: CircuitBreakerOpenError
            UseCase-->>Route: 503 Service Unavailable
        else Circuit CLOSED
            Downloader-->>UseCase: audio_file_path
            
            UseCase->>Validator: validate_audio(file_path)
            alt Invalid Audio
                Validator-->>UseCase: AudioValidationError
                UseCase-->>Route: 400 Bad Request
            else Valid Audio
                Validator-->>UseCase: OK
                
                UseCase->>Whisper: transcribe(audio_path, language)
                Whisper->>Whisper: Load Model (cached)
                Whisper->>Whisper: Process Audio
                Whisper-->>UseCase: Transcription
                
                UseCase->>Cache: store(result)
                UseCase->>Storage: cleanup_temp_files()
                
                UseCase-->>Route: TranscriptionResult
                Route-->>Client: 200 OK + Transcription
            end
        end
    end
```

---

## 4. Request Flow - Video Info

**Flow for POST /api/v1/video/info (metadata only):**

```mermaid
sequenceDiagram
    participant Client
    participant Route as VideoInfo Route
    participant Downloader as YouTubeDownloader
    participant Circuit as CircuitBreaker
    
    Client->>Route: POST /api/v1/video/info<br/>{youtube_url}
    Route->>Route: Validate YouTube URL
    
    Route->>Circuit: check_state()
    alt Circuit OPEN
        Circuit-->>Route: CircuitBreakerOpenError
        Route-->>Client: 503 Service Unavailable
    else Circuit CLOSED
        Route->>Downloader: get_video_info_with_language(url)
        
        Downloader->>Downloader: Fetch metadata (yt-dlp)
        Downloader->>Downloader: Detect language
        Downloader->>Downloader: List subtitles
        Downloader->>Downloader: Generate recommendations
        
        Downloader-->>Route: VideoInfoDTO<br/>(title, duration, subtitles,<br/>language, recommendations)
        
        Route->>Route: Generate warnings<br/>(duration, subtitles)
        
        Route-->>Client: 200 OK + Video Info
    end
```

---

## 5. Component Dependencies

**Dependency graph showing relationships:**

```mermaid
graph LR
    subgraph "Presentation"
        API[API Routes]
    end
    
    subgraph "Application"
        UC[Use Cases]
    end
    
    subgraph "Domain"
        INT[Interfaces]
    end
    
    subgraph "Infrastructure"
        YT[YouTubeDownloader]
        WS[WhisperService]
        ST[StorageService]
        CA[TranscriptionCache]
        AV[AudioValidator]
        CB[CircuitBreaker]
        FF[FFmpegOptimizer]
    end
    
    API --> UC
    UC --> INT
    
    INT -.-> YT
    INT -.-> WS
    INT -.-> ST
    
    YT --> CB
    WS --> CA
    WS --> AV
    WS --> FF
    ST --> FF
    
    style INT fill:#2196F3
    style UC fill:#4CAF50
```

---

## 6. Worker Pool Architecture

**Parallel transcription with persistent worker pool:**

```mermaid
graph TB
    subgraph "Main Process"
        API[FastAPI App<br/>Main Thread]
        SERVICE[ParallelTranscriptionService<br/>Singleton]
    end
    
    subgraph "Worker Pool (Persistent)"
        W1[Worker 1<br/>Process]
        W2[Worker 2<br/>Process]
        W3[Worker 3<br/>Process]
        W4[Worker 4<br/>Process]
    end
    
    subgraph "Tasks"
        Q[Task Queue<br/>Audio Chunks]
    end
    
    API -->|Request 1| SERVICE
    API -->|Request 2| SERVICE
    API -->|Request 3| SERVICE
    
    SERVICE -->|Split Audio| Q
    
    Q -->|Chunk 1| W1
    Q -->|Chunk 2| W2
    Q -->|Chunk 3| W3
    Q -->|Chunk 4| W4
    
    W1 -->|Result 1| SERVICE
    W2 -->|Result 2| SERVICE
    W3 -->|Result 3| SERVICE
    W4 -->|Result 4| SERVICE
    
    SERVICE -->|Merge Results| API
    
    style SERVICE fill:#FF9800
    style W1 fill:#4CAF50
    style W2 fill:#4CAF50
    style W3 fill:#4CAF50
    style W4 fill:#4CAF50
```

---

## 7. Cache Strategy

**Multi-level caching architecture:**

```mermaid
graph TB
    REQUEST[Incoming Request] --> CHECK_TRANS_CACHE{Transcription<br/>Cache Hit?}
    
    CHECK_TRANS_CACHE -->|Yes| RETURN_CACHED[Return Cached<br/>Transcription]
    CHECK_TRANS_CACHE -->|No| CHECK_MODEL{Model<br/>Loaded?}
    
    CHECK_MODEL -->|Yes| USE_CACHED_MODEL[Use Cached Model]
    CHECK_MODEL -->|No| LOAD_MODEL[Load Whisper Model]
    
    LOAD_MODEL --> MODEL_CACHE[Model Cache<br/>Store Model]
    MODEL_CACHE --> TRANSCRIBE[Transcribe Audio]
    USE_CACHED_MODEL --> TRANSCRIBE
    
    TRANSCRIBE --> STORE_TRANS[Store in<br/>Transcription Cache]
    STORE_TRANS --> RETURN_RESULT[Return Result]
    
    RETURN_CACHED --> END[Response]
    RETURN_RESULT --> END
    
    style CHECK_TRANS_CACHE fill:#FFC107
    style CHECK_MODEL fill:#FFC107
    style MODEL_CACHE fill:#4CAF50
    style STORE_TRANS fill:#4CAF50
```

---

## 8. Circuit Breaker Pattern

**YouTube API protection with circuit breaker:**

```mermaid
stateDiagram-v2
    [*] --> CLOSED: Initial State
    
    CLOSED --> OPEN: Failure Threshold<br/>Reached (5 failures)
    CLOSED --> CLOSED: Successful Request
    
    OPEN --> HALF_OPEN: Timeout Elapsed<br/>(60 seconds)
    OPEN --> OPEN: Request Rejected<br/>(Fast Fail)
    
    HALF_OPEN --> CLOSED: Test Request<br/>Succeeds
    HALF_OPEN --> OPEN: Test Request<br/>Fails
    
    note right of CLOSED
        All requests allowed
        Track failures
    end note
    
    note right of OPEN
        All requests rejected
        Return 503 immediately
        Wait for timeout
    end note
    
    note right of HALF_OPEN
        Single test request
        Decide next state
    end note
```

---

## 9. Deployment Architecture

**Production deployment with Docker and monitoring:**

```mermaid
graph TB
    subgraph "Load Balancer"
        NGINX[Nginx<br/>:80/443]
    end
    
    subgraph "Application Cluster"
        API1[YTCaption API<br/>Instance 1<br/>:8000]
        API2[YTCaption API<br/>Instance 2<br/>:8001]
        API3[YTCaption API<br/>Instance 3<br/>:8002]
    end
    
    subgraph "Storage"
        VOLUME[Shared Volume<br/>/temp]
    end
    
    subgraph "Monitoring Stack"
        PROM[Prometheus<br/>:9090]
        GRAF[Grafana<br/>:3000]
        ALERT[Alertmanager<br/>:9093]
    end
    
    subgraph "Logging"
        LOKI[Loki<br/>:3100]
    end
    
    CLIENT[Clients] -->|HTTPS| NGINX
    
    NGINX -->|Round Robin| API1
    NGINX -->|Round Robin| API2
    NGINX -->|Round Robin| API3
    
    API1 --> VOLUME
    API2 --> VOLUME
    API3 --> VOLUME
    
    API1 -->|/metrics| PROM
    API2 -->|/metrics| PROM
    API3 -->|/metrics| PROM
    
    API1 -->|Logs| LOKI
    API2 -->|Logs| LOKI
    API3 -->|Logs| LOKI
    
    PROM --> GRAF
    PROM --> ALERT
    LOKI --> GRAF
    
    style NGINX fill:#4CAF50
    style API1 fill:#2196F3
    style API2 fill:#2196F3
    style API3 fill:#2196F3
    style PROM fill:#FF5722
    style GRAF fill:#FF9800
```

---

## Diagram Conventions

### Color Coding

| Color | Meaning |
|-------|---------|
| 🟢 Green (#4CAF50) | Application/Service components |
| 🔵 Blue (#2196F3) | Interfaces/Abstractions |
| 🟠 Orange (#FF9800) | Processing/Computation |
| 🔴 Red (#FF5252) | External Services |
| 🟡 Yellow (#FFC107) | Decision Points/Caching |

### Arrow Types

| Arrow | Meaning |
|-------|---------|
| `-->` | Direct dependency |
| `-.->` | Implementation |
| `==>` | Data flow |
| `->>` | Async/Message passing |

---

## How to Render Diagrams

### Option 1: GitHub/GitLab (Native Support)

Mermaid diagrams render automatically in Markdown files on GitHub and GitLab.

### Option 2: VS Code Extension

Install **Markdown Preview Mermaid Support** extension:
```bash
code --install-extension bierner.markdown-mermaid
```

### Option 3: Online Editor

Visit [Mermaid Live Editor](https://mermaid.live/):
- Copy diagram code
- Paste in editor
- Export as SVG/PNG

### Option 4: CLI Tool

```bash
npm install -g @mermaid-js/mermaid-cli

# Generate PNG
mmdc -i diagram.mmd -o diagram.png

# Generate SVG
mmdc -i diagram.mmd -o diagram.svg
```

---

## Related Documentation

- **System Overview**: `README.md` (Project introduction)
- **Architecture Guide**: `docs-en/09-ARCHITECTURE.md` (Detailed architecture explanation)
- **DDD Layers**: All module documentation in `docs-en/architecture/`
- **API Routes**: `docs-en/architecture/presentation/routes/`
- **Infrastructure**: `docs-en/architecture/infrastructure/`

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2.2 | 2024 | Added Circuit Breaker, Worker Pool, Cache Strategy diagrams |
| v2.0 | 2024 | Added DDD layers, deployment architecture |
| v1.0 | 2023 | Initial system overview and request flow diagrams |
