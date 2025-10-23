# 🏛️ Architecture Documentation

**Complete technical documentation - mirrors `src/` structure**

---

## 📚 Overview

This section documents **each code module** following **Clean Architecture**.

The structure of this documentation **mirrors exactly** the structure of `src/`:

```
src/domain/                  → docs/architecture/domain/
src/application/             → docs/architecture/application/
src/infrastructure/youtube/  → docs/architecture/infrastructure/youtube/
src/presentation/            → docs/architecture/presentation/
```

---

## 🎯 Clean Architecture - 4 Layers

### 1. [Domain Layer](./domain/) (Core)

**Responsibility**: Pure business rules

**Contains**:
- Entities (Transcription, VideoFile)
- Value Objects (TranscriptionSegment, YouTubeURL)
- Interfaces (contracts)
- Exceptions

**Rule**: Depends on NOTHING

---

### 2. [Application Layer](./application/) (Use Cases)

**Responsibility**: Application logic orchestration

**Contains**:
- Use Cases (TranscribeVideo, CleanupFiles)
- DTOs (Data Transfer Objects)

**Depends on**: Domain (interfaces)

---

### 3. [Infrastructure Layer](./infrastructure/) (Implementations)

**Responsibility**: Concrete implementations

**Main modules**:
- **[YouTube](./infrastructure/youtube/)** - v3.0 Resilience System
- **[Whisper](./infrastructure/whisper/)** - v2.0 Parallel Transcription
- **[Storage](./infrastructure/storage/)** - File management
- **[Cache](./infrastructure/cache/)** - Transcription cache
- **[Monitoring](./infrastructure/monitoring/)** - Prometheus metrics
- **[Validators](./infrastructure/validators/)** - Audio validation
- **[Utils](./infrastructure/utils/)** - FFmpeg, Circuit Breaker

**Depends on**: Domain (interfaces)

---

### 4. [Presentation Layer](./presentation/) (API)

**Responsibility**: Controllers (FastAPI)

**Contains**:
- Routes (endpoints)
- Middlewares (logging, Prometheus)
- Dependency Injection

**Depends on**: Application (Use Cases)

---

### 5. [Config](./config/)

**Responsibility**: Settings and env vars validation

---

## 🚀 Main Modules

### YouTube Resilience v3.0

System with 5 layers of protection:

- **[Downloader](./infrastructure/youtube/downloader.md)** - Orchestrator (Facade)
- **[DownloadConfig](./infrastructure/youtube/download-config.md)** - Centralized settings
- **[DownloadStrategies](./infrastructure/youtube/download-strategies.md)** - 7 strategies
- **[RateLimiter](./infrastructure/youtube/rate-limiter.md)** - Rate limiting + Circuit Breaker
- **[UserAgentRotator](./infrastructure/youtube/user-agent-rotator.md)** - 17 User-Agents
- **[ProxyManager](./infrastructure/youtube/proxy-manager.md)** - Tor SOCKS5
- **[Metrics](./infrastructure/youtube/metrics.md)** - 26 Prometheus metrics

📖 [Complete documentation](./infrastructure/youtube/)

---

### Whisper Parallel v2.0

Parallel transcription system:

- **[TranscriptionService](./infrastructure/whisper/transcription-service.md)** - Core (single)
- **[ParallelTranscriptionService](./infrastructure/whisper/parallel-transcription-service.md)** - Parallel workers
- **[ModelCache](./infrastructure/whisper/model-cache.md)** - Singleton cache
- **[PersistentWorkerPool](./infrastructure/whisper/persistent-worker-pool.md)** - Worker pool
- **[TranscriptionFactory](./infrastructure/whisper/transcription-factory.md)** - Factory pattern

📖 [Complete documentation](./infrastructure/whisper/)

---

## 📊 Navigation

### By Layer

| Layer | Documentation | Code |
|--------|--------------|--------|
| Domain | [docs](./domain/) | [src/domain/](../../src/domain/) |
| Application | [docs](./application/) | [src/application/](../../src/application/) |
| Infrastructure | [docs](./infrastructure/) | [src/infrastructure/](../../src/infrastructure/) |
| Presentation | [docs](./presentation/) | [src/presentation/](../../src/presentation/) |
| Config | [docs](./config/) | [src/config/](../../src/config/) |

### By Module

| Module | Version | Documentation |
|--------|--------|--------------|
| YouTube | v3.0 | [docs](./infrastructure/youtube/) |
| Whisper | v2.0 | [docs](./infrastructure/whisper/) |
| Storage | v2.0 | [docs](./infrastructure/storage/) |
| Cache | v2.0 | [docs](./infrastructure/cache/) |
| Monitoring | v3.0 | [docs](./infrastructure/monitoring/) |

---

## 🔍 How to Use This Documentation

### I'm new to the project

1. Read [Domain Layer](./domain/) - Understand the core
2. Read [Application Layer](./application/) - Understand Use Cases
3. Choose a module (YouTube or Whisper) and explore

### I want to understand a specific module

1. Go to `architecture/infrastructure/<module>/`
2. Read the module's `README.md`
3. Read individual files (e.g., `downloader.md`)

### I want to modify the code

1. Find the Python file (e.g., `src/infrastructure/youtube/downloader.py`)
2. Read the corresponding documentation (`architecture/infrastructure/youtube/downloader.md`)
3. Understand dependencies ("Relationships" section)
4. Make the changes
5. Update the corresponding documentation

---

## 📖 Documentation Pattern

Each module file follows this pattern:

```markdown
# ModuleName

**Path**: `src/layer/module.py`

## Overview
Responsibility, layer, version

## Purpose
What it does and why

## Architecture
Dependencies, applied patterns

## Public Interface
Methods, parameters, exceptions

## Execution Flow
Text diagram

## Emitted Metrics
(if applicable)

## Usage Example
Functional code

## Relationships
Uses, Used by, Implements

## References
Links to diagrams, other modules
```

---

## 🔗 References

- [Diagrams](../diagrams/) - Visual diagrams
- [Developer Guide](../developer-guide/) - Contribute, test
- [User Guide](../user-guide/) - Use the API

---

**[← Back to main documentation](../README.md)**
